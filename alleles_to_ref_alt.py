#!/usr/bin/env python3
"""
alleles_to_ref_alt.py

Convert a SNP table from
    #CHROM  POS  ID  allele1  allele2
to
    #CHROM  POS  ID  REF  ALT
by determining which of allele1/allele2 matches the reference base.

Reference genome is expected as per-chromosome FASTA files (chrN.fa)
with matching .fai indices, in a single directory.

Requires: pysam.
"""

import argparse
import logging
import os
import sys

import pysam


REQUIRED_HEADER = ["#CHROM", "POS", "ID", "allele1", "allele2"]
OUTPUT_HEADER = ["#CHROM", "POS", "ID", "REF", "ALT"]
VALID_NUCLEOTIDES = set("ACGTN")


def parse_args():
    parser = argparse.ArgumentParser(
        prog="alleles_to_ref_alt.py",
        description="Determine REF/ALT from allele1/allele2 against a reference FASTA.",
    )
    parser.add_argument("--input", "-i", required=True, help="Input TSV file.")
    parser.add_argument("--output", "-o", required=True, help="Output TSV file.")
    parser.add_argument("--reference-dir", "-r", required=True,
                        help="Directory with per-chromosome FASTA files (chrN.fa).")
    parser.add_argument("--log", "-l", default=None, help="Optional log file.")
    return parser.parse_args()


def setup_logging(log_path):
    logger = logging.getLogger("alleles_to_ref_alt")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)
    if log_path:
        d = os.path.dirname(os.path.abspath(log_path))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def check_files(input_path, reference_dir, logger):
    if not os.path.isfile(input_path):
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)
    if not os.path.isdir(reference_dir):
        logger.error("Reference directory not found: %s", reference_dir)
        sys.exit(1)


def validate_header(fh, logger):
    line = fh.readline()
    if not line:
        logger.error("Input file is empty.")
        sys.exit(1)
    header = line.rstrip("\r\n").split("\t")
    if header != REQUIRED_HEADER:
        logger.error("Unexpected header: %s", header)
        logger.error("Expected: %s", REQUIRED_HEADER)
        sys.exit(1)
    logger.info("Header validated.")


def get_fasta(chrom, reference_dir, cache, logger):
    """Open chrN.fa on demand and cache the Fastafile object."""
    if chrom in cache:
        return cache[chrom]

    path = os.path.join(reference_dir, f"{chrom}.fa")
    if not os.path.isfile(path):
        logger.warning("Reference FASTA not found for %s: %s", chrom, path)
        cache[chrom] = None
        return None
    if not os.path.isfile(path + ".fai"):
        logger.warning("FASTA index missing: %s.fai", path)
        cache[chrom] = None
        return None

    try:
        cache[chrom] = pysam.Fastafile(path)
        logger.info("Opened reference: %s", path)
    except Exception as exc:
        logger.warning("Failed to open %s: %s", path, exc)
        cache[chrom] = None
    return cache[chrom]


def convert_record(chrom, pos, allele1, allele2, fasta):
    """Return (ref, alt) or None if the record cannot be resolved."""
    ref_base = fasta.fetch(chrom, pos - 1, pos).upper()
    if not ref_base:
        return None
    a1, a2 = allele1.upper(), allele2.upper()
    if ref_base == a1 and ref_base != a2:
        return allele1, allele2
    if ref_base == a2 and ref_base != a1:
        return allele2, allele1
    return None


def main():
    args = parse_args()
    logger = setup_logging(args.log)

    logger.info("Started")
    logger.info("Input:         %s", args.input)
    logger.info("Output:        %s", args.output)
    logger.info("Reference dir: %s", args.reference_dir)

    check_files(args.input, args.reference_dir, logger)

    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    fasta_cache = {}
    total = written = skipped = 0

    with open(args.input, "r", encoding="utf-8", newline=None) as fin, \
         open(args.output, "w", encoding="utf-8", newline="\n") as fout:

        validate_header(fin, logger)
        fout.write("\t".join(OUTPUT_HEADER) + "\n")

        for lineno, line in enumerate(fin, start=2):
            line = line.rstrip("\r\n")
            if not line:
                continue
            total += 1
            fields = line.split("\t")

            if len(fields) != 5:
                logger.warning("Line %d: expected 5 fields, got %d", lineno, len(fields))
                skipped += 1
                continue

            chrom, pos_str, sid, a1, a2 = fields

            try:
                pos = int(pos_str)
            except ValueError:
                logger.warning("Line %d: POS not an integer (%s)", lineno, pos_str)
                skipped += 1
                continue

            if a1.upper() not in VALID_NUCLEOTIDES or a2.upper() not in VALID_NUCLEOTIDES:
                logger.warning("Line %d: invalid alleles %s/%s", lineno, a1, a2)
                skipped += 1
                continue

            fasta = get_fasta(chrom, args.reference_dir, fasta_cache, logger)
            if fasta is None:
                skipped += 1
                continue

            try:
                result = convert_record(chrom, pos, a1, a2, fasta)
            except Exception as exc:
                logger.warning("Line %d: fetch failed (%s)", lineno, exc)
                skipped += 1
                continue

            if result is None:
                logger.warning("Line %d: no reference match at %s:%d (a1=%s a2=%s)",
                               lineno, chrom, pos, a1, a2)
                skipped += 1
                continue

            ref, alt = result
            fout.write(f"{chrom}\t{pos}\t{sid}\t{ref}\t{alt}\n")
            written += 1

    for f in fasta_cache.values():
        if f is not None:
            f.close()

    logger.info("Finished: total=%d written=%d skipped=%d", total, written, skipped)


if __name__ == "__main__":
    main()
