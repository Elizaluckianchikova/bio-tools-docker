# bio-tools-docker

bio-tools-docker
A reproducible Docker environment for BAM/CRAM/VCF processing. The image is built on Ubuntu 22.04 and contains pinned, source-compiled versions of samtools, htslib, libdeflate, bcftools, and vcftools, plus the Python wrapper pysam.

Each specialized tool is compiled from its own upstream repository and installed into a versioned directory under /soft, with the release date encoded in the folder name as brYYMMDD. No specialized package is installed via apt or bioconda.

Repository layout
text
.
├── Dockerfile
├── README.md
└── .github/
    └── workflows/
        └── build.yml
What's inside
Tool	Version	Release date	Install path
libdeflate	1.26	2026-08-22	/soft/libdeflate-1.26-br260822
htslib	1.24	2026-07-09	/soft/htslib-1.24-br260709
samtools	1.24	2026-07-09	/soft/samtools-1.24-br260709
bcftools	1.24	2026-07-09	/soft/bcftools-1.24-br260709
vcftools	0.1.17	2025-05-15	/soft/vcftools-0.1.17-br250515
pysam	0.24.0	2026-04-27	installed via pip
Building the image
From the repository root:

bash
docker build -t task10-bioinfo:latest .
The build parallelizes across all available CPU cores (make -j$(nproc), cmake --build --parallel $(nproc)). On a four-core machine, a clean build takes roughly five to ten minutes.

To rebuild without the layer cache:

bash
docker build --no-cache -t task10-bioinfo:latest .
Running the container
Start an interactive shell:

bash
docker run --rm -it task10-bioinfo:latest
You will land in bash, working directory /work, with every tool on PATH.

To mount a local directory with your data:

bash
docker run --rm -it -v "$(pwd)":/work task10-bioinfo:latest
On Windows PowerShell, use ${PWD} instead of $(pwd):

powershell
docker run --rm -it -v "${PWD}:/work" task10-bioinfo:latest
Checking the installation
Inside the container:

bash
samtools --version
bcftools --version
vcftools --version
python3 -c "import pysam; print('pysam', pysam.__version__)"
Expected output:

samtools 1.24

bcftools 1.24

VCFtools (0.1.17)

pysam 0.24.0

The same tools are also reachable through dedicated environment variables:

bash
$SAMTOOLS --version
$BCFTOOLS --version
$VCFTOOLS --version
Environment variables
Variable	Value
SOFT	/soft
LIBDEFLATE	/soft/libdeflate-1.26-br260822
HTSLIB	/soft/htslib-1.24-br260709
SAMTOOLS	/soft/samtools-1.24-br260709/bin/samtools
BCFTOOLS	/soft/bcftools-1.24-br260709/bin/bcftools
VCFTOOLS	/soft/vcftools-0.1.17-br250515/bin/vcftools
PATH includes the bin directory of every specialized tool. LD_LIBRARY_PATH points to the lib directories of libdeflate and htslib, so that samtools, bcftools, and pysam resolve their shared libraries at runtime.

How the image is built
Base image — official ubuntu:22.04.

Common packages — compilers, zlib, bzip2, liblzma, libcurl, openssl, autotools, cmake, and python3 — installed in a single apt-get layer, then the apt cache and package lists are removed.

Specialized tools are compiled from source, each in its own Docker layer, each installed under /soft/<tool>-<version>-br<YYMMDD>.

Build order follows the dependency chain: libdeflate first, then htslib, then samtools and bcftools. After installing libdeflate and htslib, the corresponding lib directories are registered with ldconfig, so the runtime linker finds them without additional configuration.

samtools and bcftools are configured with explicit --with-htslib, CPPFLAGS, and LDFLAGS, so the configure step locates both headers and shared libraries.

vcftools is built from the GitHub tag v0.1.17 via autotools.

Parallelism — every build step runs with -j$(nproc) or --parallel $(nproc).

Cleanup — tarballs and temporary source trees are removed inside the same layer that creates them.

Smoke check — the last RUN step verifies that samtools, bcftools, vcftools, and pysam all execute without errors.

A note on pysam
pysam is installed through pip as a regular Python package. It is a Python binding over htslib rather than a standalone tool, which is why a pip install is acceptable here. If a strictly source-built pysam is required, replace the pip line with:

dockerfile
RUN python3 -m pip install --no-cache-dir --no-binary pysam pysam==0.24.0
Testing without a local Docker installation
If Docker Desktop cannot be used locally — for example, because WSL 2 is unavailable or the host does not meet Docker's hardware requirements — the image can still be built and verified in the cloud.

GitHub Codespaces
On the repository page, click Code → Codespaces → Create codespace on main. The environment already has Docker installed. Inside the Codespaces terminal:

bash
docker build -t task10-bioinfo:latest .
docker run --rm task10-bioinfo:latest samtools --version
docker run --rm task10-bioinfo:latest bcftools --version
docker run --rm task10-bioinfo:latest vcftools --version
All work happens on GitHub's servers; the local machine only needs a browser.

GitHub Actions
The repository ships a workflow at .github/workflows/build.yml that builds the image and runs smoke tests on every push and pull request. Results are visible under the Actions tab.

yaml
name: Build Docker image

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v7

      - name: Show repository contents
        run: |
          echo "Repository root:"
          ls -la

      - name: Build Docker image
        run: docker build --progress=plain -t task10-bioinfo:latest .

      - name: Check samtools
        run: docker run --rm task10-bioinfo:latest samtools --version

      - name: Check bcftools
        run: docker run --rm task10-bioinfo:latest bcftools --version

      - name: Check vcftools
        run: docker run --rm task10-bioinfo:latest vcftools --version

      - name: Check pysam
        run: docker run --rm task10-bioinfo:latest python3 -c "import pysam; print('pysam', pysam.__version__)"

      - name: Check environment variables
        run: |
          docker run --rm task10-bioinfo:latest bash -c 'echo "SOFT=$SOFT"'
          docker run --rm task10-bioinfo:latest bash -c 'echo "SAMTOOLS=$SAMTOOLS"'
          docker run --rm task10-bioinfo:latest bash -c 'echo "BCFTOOLS=$BCFTOOLS"'
          docker run --rm task10-bioinfo:latest bash -c 'echo "VCFTOOLS=$VCFTOOLS"'
A green checkmark on the Actions tab is portable proof that the Dockerfile builds cleanly and every required tool runs as expected. The workflow can also be triggered manually from the Actions tab via workflow_dispatch.

Git history
Commits are organized to reflect the build stages:

text
init repository
add Docker build environment
add libdeflate and htslib
add samtools and bcftools
add vcftools
add GitHub Actions workflow
License
This repository is provided for educational purposes. Each bundled tool retains its upstream license:

samtools, bcftools, htslib — MIT / Modified BSD

libdeflate — MIT

vcftools — LGPL v3

pysam — MIT
