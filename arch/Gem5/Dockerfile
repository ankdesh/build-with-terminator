# Use Ubuntu 24.04 as base image
FROM ubuntu:24.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    m4 \
    scons \
    zlib1g \
    zlib1g-dev \
    libprotobuf-dev \
    protobuf-compiler \
    libprotoc-dev \
    libgoogle-perftools-dev \
    python3-dev \
    python3-pip \
    python3-venv \
    libboost-all-dev \
    libhdf5-serial-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /gem5

# Clone Gem5 repository
RUN git clone https://github.com/gem5/gem5.git .

# Build Gem5 for RISC-V
RUN scons build/RISCV/gem5.opt -j$(nproc)

# Default command
CMD ["build/RISCV/gem5.opt"]
