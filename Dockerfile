FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV SOFT=/soft
ENV LD_LIBRARY_PATH=${SOFT}/libdeflate-1.26-br260822/lib:${SOFT}/htslib-1.24-br260709/lib

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    wget \
    git \
    autoconf \
    automake \
    libtool \
    pkg-config \
    cmake \
    make \
    gcc \
    g++ \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    libncurses5-dev \
    libperl-dev \
    libboost-all-dev \
    python3 \
    python3-pip \
    python3-dev \
    && mkdir -p ${SOFT} \
    && rm -rf /var/lib/apt/lists/*

# libdeflate 1.26, release 2026-08-22
RUN cd /tmp \
    && git clone --depth 1 --branch v1.26 https://github.com/ebiggers/libdeflate.git libdeflate-src \
    && cmake -S libdeflate-src -B libdeflate-src/build \
       -DCMAKE_BUILD_TYPE=Release \
       -DCMAKE_INSTALL_PREFIX=${SOFT}/libdeflate-1.26-br260822 \
    && cmake --build libdeflate-src/build --parallel "$(nproc)" \
    && cmake --install libdeflate-src/build \
    && echo "${SOFT}/libdeflate-1.26-br260822/lib" > /etc/ld.so.conf.d/libdeflate.conf \
    && ldconfig \
    && rm -rf /tmp/libdeflate-src

# htslib 1.24, release 2026-07-09
RUN cd /tmp \
    && curl -fsSL https://github.com/samtools/htslib/releases/download/1.24/htslib-1.24.tar.bz2 -o htslib.tar.bz2 \
    && tar -xjf htslib.tar.bz2 \
    && cd htslib-1.24 \
    && ./configure --prefix=${SOFT}/htslib-1.24-br260709 \
       CPPFLAGS="-I${SOFT}/libdeflate-1.26-br260822/include" \
       LDFLAGS="-L${SOFT}/libdeflate-1.26-br260822/lib" \
    && make -j"$(nproc)" \
    && make install \
    && echo "${SOFT}/htslib-1.24-br260709/lib" > /etc/ld.so.conf.d/htslib.conf \
    && ldconfig \
    && rm -rf /tmp/htslib.tar.bz2 /tmp/htslib-1.24

# samtools 1.24, release 2026-07-09
RUN cd /tmp \
    && curl -fsSL https://github.com/samtools/samtools/releases/download/1.24/samtools-1.24.tar.bz2 -o samtools.tar.bz2 \
    && tar -xjf samtools.tar.bz2 \
    && cd samtools-1.24 \
    && ./configure --prefix=${SOFT}/samtools-1.24-br260709 \
       --with-htslib=${SOFT}/htslib-1.24-br260709 \
       CPPFLAGS="-I${SOFT}/htslib-1.24-br260709/include" \
       LDFLAGS="-L${SOFT}/htslib-1.24-br260709/lib" \
    && make -j"$(nproc)" \
    && make install \
    && rm -rf /tmp/samtools.tar.bz2 /tmp/samtools-1.24

# bcftools 1.24, release 2026-07-09
RUN cd /tmp \
    && curl -fsSL https://github.com/samtools/bcftools/releases/download/1.24/bcftools-1.24.tar.bz2 -o bcftools.tar.bz2 \
    && tar -xjf bcftools.tar.bz2 \
    && cd bcftools-1.24 \
    && ./configure --prefix=${SOFT}/bcftools-1.24-br260709 \
       --with-htslib=${SOFT}/htslib-1.24-br260709 \
       CPPFLAGS="-I${SOFT}/htslib-1.24-br260709/include" \
       LDFLAGS="-L${SOFT}/htslib-1.24-br260709/lib" \
    && make -j"$(nproc)" \
    && make install \
    && rm -rf /tmp/bcftools.tar.bz2 /tmp/bcftools-1.24

# vcftools 0.1.17, release 2025-05-15
RUN cd /tmp \
    && git clone --depth 1 --branch v0.1.17 https://github.com/vcftools/vcftools.git vcftools-src \
    && cd vcftools-src \
    && ./autogen.sh \
    && ./configure --prefix=${SOFT}/vcftools-0.1.17-br250515 \
    && make -j"$(nproc)" \
    && make install \
    && rm -rf /tmp/vcftools-src

# pysam 0.24.0, release 2026-04-27
RUN python3 -m pip install --no-cache-dir pysam==0.24.0

ENV PATH=${SOFT}/libdeflate-1.26-br260822/bin:${SOFT}/htslib-1.24-br260709/bin:${SOFT}/samtools-1.24-br260709/bin:${SOFT}/bcftools-1.24-br260709/bin:${SOFT}/vcftools-0.1.17-br250515/bin:${PATH}

ENV LIBDEFLATE=${SOFT}/libdeflate-1.26-br260822
ENV HTSLIB=${SOFT}/htslib-1.24-br260709
ENV SAMTOOLS=${SOFT}/samtools-1.24-br260709/bin/samtools
ENV BCFTOOLS=${SOFT}/bcftools-1.24-br260709/bin/bcftools
ENV VCFTOOLS=${SOFT}/vcftools-0.1.17-br250515/bin/vcftools

# --- Task 3: copy the Python script into the image ---
COPY alleles_to_ref_alt.py /opt/task10/alleles_to_ref_alt.py
RUN chmod +x /opt/task10/alleles_to_ref_alt.py

WORKDIR /work

RUN ${SAMTOOLS} --version \
    && ${BCFTOOLS} --version \
    && ${VCFTOOLS} --version \
    && python3 -c "import pysam; print('pysam', pysam.__version__)" \
    && python3 /opt/task10/alleles_to_ref_alt.py --help

CMD ["/bin/bash"]
