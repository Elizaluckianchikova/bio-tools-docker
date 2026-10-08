# FP_SNPs: preprocessing and REF/ALT reconstruction

This document describes how the FP SNP panel from GRAF 2.4 is preprocessed into a VCF-like TSV and how the reference and alternative alleles are reconstructed for each SNP using the GRCh38.d1.vd1 human reference genome.

## Source data

The FP SNP panel originates from the GRAF software package (version 2.4), described in:

> Yu et al. *Quickly identifying identical and closely related subjects in large databases using genotype data.*
> https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5469481/

The panel contains 10,000 autosomal unlinked biallelic SNPs selected for fingerprinting and population structure analysis, plus 1,000 X-chromosome SNPs for sex determination.

The original archive `GrafPkg.tar.gz` was no longer available from the NCBI download page at the time of writing (HTTP 404). The equivalent PLINK-format data was taken from the GRAF repository on GitHub:

```
https://github.com/ncbi/graf
```

The file used for preprocessing is `data/G1000FpGeno.bim`. It contains 10,000 autosomal SNPs with GRCh37 (hg19) coordinates. X-chromosome records are not present in this file, so no additional filtering by chromosome is needed at the preprocessing stage.

## Preprocessing to `FP_SNPs_10k_GB38_twoAllelsFormat.tsv`

The `.bim` file uses the standard PLINK column order:

```
CHR  SNP_ID  CM  BP(hg19)  A1  A2
```

The target format expected by the REF/ALT converter is:

```
#CHROM  POS  ID  allele1  allele2
```

with GRCh38 coordinates. The conversion has two parts.

### Lift-over from GRCh37 to GRCh38

Coordinates in the `.bim` file are in GRCh37. They must be lifted to GRCh38 using the UCSC chain file `hg19ToHg38.over.chain`, available at:

```
http://hgdownload.cse.ucsc.edu/goldenPath/hg19/liftOver/hg19ToHg38.over.chain.gz
```

The lift-over is performed with `pyliftover`:

```python
from pyliftover import LiftOver

lo = LiftOver("hg19ToHg38.over.chain")

with open("data/G1000FpGeno.bim") as fin, \
     open("data/FP_SNPs_10k_GB38_twoAllelsFormat.tsv", "w") as fout:

    fout.write("#CHROM\tPOS\tID\tallele1\tallele2\n")
    total = converted = lost = 0

    for line in fin:
        parts = line.rstrip("\n").split("\t")
        if len(parts) != 6:
            continue
        total += 1
        chrom, rsid, _cm, pos37, a1, a2 = parts
        if chrom == "23":
            continue
        hit = lo.convert_coordinate("chr" + chrom, int(pos37))
        if not hit:
            lost += 1
            continue
        new_chrom, new_pos = hit[0][0], hit[0][1]
        fout.write(f"{new_chrom}\t{new_pos}\t{rsid}\t{a1}\t{a2}\n")
        converted += 1

print(f"total={total} converted={converted} lost={lost}")
```

Output:

```
total=10000 converted=10000 lost=0
```

All 10,000 SNPs were successfully lifted from GRCh37 to GRCh38. The `chr` prefix is added during lift-over; the SNP ID is taken from the original `rs` identifier.

### Output file

`data/FP_SNPs_10k_GB38_twoAllelsFormat.tsv` — 10,000 records plus a header, five tab-separated columns:

```
#CHROM  POS  ID  allele1  allele2
```

The distribution of records across chromosomes matches the original panel: chr1 — 810, chr2 — 864, …, chr22 — 138.

## Reference genome

The reference genome is GRCh38.d1.vd1 from GDC:

```
https://gdc.cancer.gov/about-data/data-harmonization-and-generation/gdc-reference-files
```

It is split into per-chromosome FASTA files with matching `.fai` indices:

```
/ref/GRCh38.d1.vd1_mainChr/sepChrs/
  chr1.fa   chr1.fa.fai
  ...
  chr22.fa  chr22.fa.fai
  chrX.fa   chrX.fa.fai
  chrY.fa   chrY.fa.fai
  chrM.fa   chrM.fa.fai
```

The reference genome is **not** included in this repository. It is expected on the host machine at `/mnt/data/ref/GRCh38.d1.vd1_mainChr/sepChrs/` and is mounted into the container at `/ref/GRCh38.d1.vd1_mainChr/sepChrs/`.

## REF/ALT reconstruction

The script `alleles_to_ref_alt.py` reads each SNP from `FP_SNPs_10k_GB38_twoAllelsFormat.tsv`, fetches the reference base at the given position with `pysam.Fastafile`, and determines which of `allele1` / `allele2` matches the reference:

- if `allele1` matches the reference and `allele2` does not → REF = `allele1`, ALT = `allele2`;
- if `allele2` matches the reference and `allele1` does not → REF = `allele2`, ALT = `allele1`;
- if neither allele matches the reference → the record is reported in the log and skipped;
- if both alleles match the reference → the record is treated as unresolvable and skipped.

The script opens the per-chromosome FASTA file on demand and caches the `Fastafile` object, so each chromosome is opened once.

### Usage

Inside the container, the script is available at `/opt/task10/alleles_to_ref_alt.py`:

```bash
python3 /opt/task10/alleles_to_ref_alt.py \
  --input  FP_SNPs_10k_GB38_twoAllelsFormat.tsv \
  --output FP_SNPs_10k_GB38_REF_ALT.tsv \
  --reference-dir /ref/GRCh38.d1.vd1_mainChr/sepChrs \
  --log    logs/alleles_to_ref_alt.log
```

Command-line arguments:

| Argument | Description |
|---|---|
| `--input`, `-i` | Input TSV with columns `#CHROM POS ID allele1 allele2`. |
| `--output`, `-o` | Output TSV with columns `#CHROM POS ID REF ALT`. |
| `--reference-dir`, `-r` | Directory containing `chrN.fa` and matching `.fai` files. |
| `--log`, `-l` | Optional path to a log file. |
| `--help`, `-h` | Print usage and exit. |

The script:

- validates the header of the input file and exits with an error if it does not match;
- accepts key-value arguments rather than positional ones;
- handles LF, CRLF, and CR line endings;
- validates positions and nucleotide characters;
- logs every skipped record with its line number and reason;
- writes a timestamped message at every step of the run;
- exits with a non-zero status on fatal input or reference errors.

## Results

The script was run on the full panel of 10,000 autosomal SNPs with the GRCh38.d1.vd1 reference genome.

```
total=10000 written=9916 skipped=84
```

- **Written to output:** 9,916 records (99.16 %)
- **Skipped:** 84 records (0.84 %)

Breakdown of skipped records:

- **79 records** had `allele1 = 0` and `allele2 = 0` in the source `.bim` file. This is the PLINK convention for a missing genotype; such records carry no allele information and cannot be assigned a REF/ALT pair.
- **5 records** did not match the reference base at the given position: neither `allele1` nor `allele2` corresponded to the nucleotide in GRCh38.d1.vd1. Each such record is listed in the log with chromosome, position, and both alleles.

No records were lost due to technical errors — there were no read failures, no missing FASTA files, and no missing `.fai` indices.

### Output file

`data/FP_SNPs_10k_GB38_REF_ALT.tsv` — 9,916 records plus a header, five tab-separated columns:

```
#CHROM  POS  ID  REF  ALT
```

Example rows:

```
chr1   1220751   rs2887286  T  C
chr1   1275912   rs6685064  C  T
chr1   2352457   rs2840528  A  G
...
chr22  50577409  rs3213445  T  C
```

The distribution of records across chromosomes in the output file matches the input distribution, minus the skipped records. No rows have `REF == ALT`.

### Log file

`logs/alleles_to_ref_alt.log` — full timestamped log of the run. Example:

```
2026-10-08 18:16:07 [INFO] Started
2026-10-08 18:16:07 [INFO] Input:         FP_SNPs_10k_GB38_twoAllelsFormat.tsv
2026-10-08 18:16:07 [INFO] Output:        FP_SNPs_10k_GB38_REF_ALT.tsv
2026-10-08 18:16:07 [INFO] Reference dir: ref
2026-10-08 18:16:07 [INFO] Header validated.
2026-10-08 18:16:07 [INFO] Opened reference: ref/chr1.fa
2026-10-08 18:16:07 [WARNING] Line 80: invalid alleles 0/0
...
2026-10-08 18:16:08 [INFO] Finished: total=10000 written=9916 skipped=84
```

## Repository contents

```
alleles_to_ref_alt.py                        # the converter
Task3.ipynb                                  # Colab notebook with the full pipeline
FP_SNPs_README.md                            # this document
Dockerfile                                   # Docker image definition
data/G1000FpGeno.bim                         # original PLINK .bim (GRCh37)
data/FP_SNPs_10k_GB38_twoAllelsFormat.tsv    # lifted to GRCh38, preprocessed
data/FP_SNPs_10k_GB38_REF_ALT.tsv            # output of the converter
logs/alleles_to_ref_alt.log                  # timestamped run log
```

The reference genome is not tracked in the repository; it is mounted into the container at runtime.
