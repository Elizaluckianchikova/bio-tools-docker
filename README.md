# bio-tools-docker

A reproducible environment for BAM/CRAM/VCF processing and SNP allele conversion. The repository contains two independent components:

1. **A Docker image** built on Ubuntu 22.04 with pinned, source-compiled versions of `samtools`, `htslib`, `libdeflate`, `bcftools`, and `vcftools`, plus the Python wrapper `pysam`.
2. **A Python script** (`alleles_to_ref_alt.py`) that converts allele1/allele2 SNP records into REF/ALT form using `pysam.Fastafile` and the GRCh38.d1.vd1 reference genome.

Both components are self-contained and can be used separately, but they are designed to work together inside the same container.

---

## Repository layout

```
.
├── Dockerfile
├── README.md
└── scripts/
    ├── alleles_to_ref_alt.py
    └── preprocess_FP_SNPs.sh
```

The `scripts/` directory holds the Python converter and the GRAF preprocessing helper. Both are copied into the image at `/opt/task10/`.

---

## Part 1 — Docker image

### What's inside

| Tool | Version | Release date | Install path |
|---|---|---|---|
| libdeflate | 1.26 | 2026-08-22 | `/soft/libdeflate-1.26-br260822` |
| htslib | 1.24 | 2026-07-09 | `/soft/htslib-1.24-br260709` |
| samtools | 1.24 | 2026-07-09 | `/soft/samtools-1.24-br260709` |
| bcftools | 1.24 | 2026-07-09 | `/soft/bcftools-1.24-br260709` |
| vcftools | 0.1.17 | 2026-05-15 | `/soft/vcftools-0.1.17-br260515` |
| pysam | 0.24.0 | 2026-04-27 | installed via pip |

Each specialized tool is compiled from its own upstream repository and installed into a versioned directory under `/soft`, with the release date encoded as `brYYMMDD`. No specialized package is installed via `apt` or `bioconda`.

`pysam` is added on top of the compiled `htslib` and is used by the Python script in Part 2.

### Building the image

From the repository root:

```bash
docker build --build-arg JOBS=$(nproc) -t task10-bioinfo:latest .
```

The build parallelizes across all available CPU cores. On a four-core machine, a full clean build takes roughly five to ten minutes. Passing `JOBS` explicitly is optional — the Dockerfile falls back to `$(nproc)` when the argument is not set.

To rebuild without the layer cache:

```bash
docker build --no-cache -t task10-bioinfo:latest .
```

### Running the container

Start an interactive shell with the reference genome mounted read-only and the working directory mounted read-write:

```bash
docker run --rm -it \
  -v /mnt/data/ref/GRCh38.d1.vd1_mainChr/sepChrs:/ref/GRCh38.d1.vd1_mainChr/sepChrs:ro \
  -v "$(pwd)":/work \
  task10-bioinfo:latest
```

On Windows PowerShell, use `${PWD}` instead of `$(pwd)`:

```powershell
docker run --rm -it `
  -v "C:\path\to\ref:/ref/GRCh38.d1.vd1_mainChr/sepChrs:ro" `
  -v "${PWD}:/work" `
  task10-bioinfo:latest
```

You will land in `bash`, working directory `/work`, with every tool on `PATH`.

### Checking the installation

Inside the container:

```bash
samtools --version
bcftools --version
vcftools --version
python3 -c "import pysam; print('pysam', pysam.__version__)"
```

Expected output:

- `samtools 1.24`
- `bcftools 1.24`
- `VCFtools (0.1.17)`
- `pysam 0.24.0`

The same tools are also reachable through dedicated environment variables:

```bash
$SAMTOOLS --version
$BCFTOOLS --version
$VCFTOOLS --version
```

### Environment variables

| Variable | Value |
|---|---|
| `SOFT` | `/soft` |
| `LIBDEFLATE` | `/soft/libdeflate-1.26-br260822` |
| `HTSLIB` | `/soft/htslib-1.24-br260709` |
| `SAMTOOLS` | `/soft/samtools-1.24-br260709/bin/samtools` |
| `BCFTOOLS` | `/soft/bcftools-1.24-br260709/bin/bcftools` |
| `VCFTOOLS` | `/soft/vcftools-0.1.17-br250515/bin/vcftools` |

`PATH` includes the `bin` directory of every specialized tool. `LD_LIBRARY_PATH` points to the `lib` directories of `libdeflate` and `htslib`, so that `samtools`, `bcftools`, and `pysam` resolve their shared libraries at runtime.

### How the image is built

- **Base image** — official `ubuntu:22.04`.
- **Common packages** — compilers, `zlib`, `bzip2`, `liblzma`, `libcurl`, `openssl`, `autotools`, `cmake`, `python3` — installed in a single `apt-get` layer, then the apt cache and package lists are removed.
- **Specialized tools** are compiled from source, each in its own Docker layer, each installed under `/soft/<tool>-<version>-br<YYMMDD>`.
- **Build order** follows the dependency chain: `libdeflate` first, then `htslib`, then `samtools` and `bcftools`. `htslib` is linked against `libdeflate` through explicit `CPPFLAGS` and `LDFLAGS`; `samtools` and `bcftools` are linked against the installed `htslib`.
- **vcftools** is built from the GitHub tag `v0.1.17` via autotools.
- **Parallelism** — every build step runs with `-j$(nproc)` or `--parallel $(nproc)`.
- **Cleanup** — tarballs and temporary source trees are removed inside the same layer that creates them.
- **Smoke check** — the last `RUN` step verifies that `samtools`, `bcftools`, `vcftools`, and `pysam` all execute without errors.

### A note on pysam

`pysam` is installed through `pip` as a regular Python package. It is a Python binding over `htslib` rather than a standalone tool, which is why a pip install is acceptable here. If a strictly source-built `pysam` is required, replace the pip line with:

```dockerfile
RUN python3 -m pip install --no-cache-dir --no-binary pysam pysam==0.24.0
```

---

## Part 2 — Python REF/ALT converter

The script `scripts/alleles_to_ref_alt.py` reads a TSV of SNP records with `allele1`/`allele2` columns and rewrites them with `REF`/`ALT` columns determined against a reference FASTA. It uses `pysam.Fastafile` and requires an indexed FASTA (`.fai` next to the `.fa`).

### Usage

```bash
python3 /opt/task10/alleles_to_ref_alt.py \
  --input  data/FP_SNPs_10k_GB38_twoAllelsFormat.tsv \
  --output data/FP_SNPs_10k_GB38_REF_ALT.tsv \
  --reference /ref/GRCh38.d1.vd1_mainChr/sepChrs/chr1.fa \
  --log    logs/alleles_to_ref_alt.log
```

To see the full argument list:

```bash
python3 /opt/task10/alleles_to_ref_alt.py --help
```

### What the script does

- Validates the input header and required columns.
- Accepts named command-line arguments for input, output, reference, and log.
- Handles CRLF, LF, and CR line endings through universal newline mode.
- Validates positions and nucleotide alleles.
- Checks that the FASTA index exists before opening the file.
- Timestamps every console and file log entry.
- Determines which of `allele1`/`allele2` matches the reference base and assigns REF/ALT accordingly.
- Reports unresolved records instead of silently inventing REF/ALT values.
- Exits with a non-zero status on fatal input or reference errors.

### Reference genome

The GRCh38.d1.vd1 reference is expected split into per-chromosome FASTA files:

```text
/ref/GRCh38.d1.vd1_mainChr/sepChrs/
  chr1.fa  chr1.fa.fai
  ...
  chr22.fa chr22.fa.fai
  chrM.fa  chrM.fa.fai
  chrX.fa  chrX.fa.fai
  chrY.fa  chrY.fa.fai
```

The script accepts one FASTA file per run. For a multi-chromosome dataset, either concatenate the relevant chromosome FASTAs into a single indexed FASTA, or run the script once per chromosome against the matching subset of the input table.

The official GDC reference archive is `GRCh38.d1.vd1.fa.tar.gz`; the GDC page also publishes its MD5 checksum for verification.

**Do not commit the reference genome to this repository.** It is large and should be mounted into the container at runtime, as shown in the `docker run` example above.

### GRAF FP_SNPs preprocessing

The original `FP_SNPs.txt` file is distributed separately as part of GRAF 2.4 and must be preprocessed before the REF/ALT converter can consume it. The repository provides a transparent template:

```bash
bash scripts/preprocess_FP_SNPs.sh data/FP_SNPs.txt \
  data/FP_SNPs_10k_GB38_twoAllelsFormat.tsv
```

The preprocessing is expected to perform:

- removal of GRCh37 coordinates;
- column renaming and reordering;
- adding the `chr` and `rs` prefixes;
- removal of X-chromosome records;
- output under the name `FP_SNPs_10k_GB38_twoAllelsFormat.tsv`.

**Inspect the actual GRAF 2.4 `FP_SNPs.txt` header before running the preprocessing step.** The supplied script is intentionally a template, because the source archive is not part of the assignment materials.

### Files produced during a full run

```text
data/FP_SNPs.txt
data/FP_SNPs_10k_GB38_twoAllelsFormat.tsv
data/FP_SNPs_10k_GB38_REF_ALT.tsv
logs/alleles_to_ref_alt.log
```

The first two are inputs or intermediate files and are not tracked in git. The last two are outputs and are tracked only when they serve as validation artifacts.

---

## Testing without a local Docker installation

If Docker Desktop cannot be used locally — for example, because WSL 2 is unavailable or the host does not meet Docker's hardware requirements — the image can still be built and verified in the cloud.

### GitHub Codespaces

On the repository page, click **Code → Codespaces → Create codespace on main**. The environment already has Docker installed. Inside the Codespaces terminal:

```bash
docker build -t task10-bioinfo:latest .
docker run --rm task10-bioinfo:latest samtools --version
docker run --rm task10-bioinfo:latest bcftools --version
docker run --rm task10-bioinfo:latest vcftools --version
```

All work happens on GitHub's servers; the local machine only needs a browser.

### GitHub Actions

The repository ships a workflow at `.github/workflows/build.yml` that builds the image and runs smoke tests on every push and pull request. Results are visible under the **Actions** tab.

```yaml
name: Build Docker image

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t task10-bioinfo:latest .

      - name: Smoke test
        run: |
          docker run --rm task10-bioinfo:latest samtools --version
          docker run --rm task10-bioinfo:latest bcftools --version
          docker run --rm task10-bioinfo:latest vcftools --version
```

A green checkmark on the Actions tab is portable proof that the Dockerfile builds cleanly and every required tool runs as expected.

---

## Git history

Commits are organized to reflect the two components:

```text
init repository
add Docker build environment
add libdeflate and htslib
add samtools and bcftools
add vcftools
add Python REF/ALT converter
add GRAF preprocessing documentation
add validation results
```

---

## License

This repository is provided for educational purposes. Each bundled tool retains its upstream license:

- samtools, bcftools, htslib — MIT / Modified BSD
- libdeflate — MIT
- vcftools — LGPL v3
- pysam — MIT
