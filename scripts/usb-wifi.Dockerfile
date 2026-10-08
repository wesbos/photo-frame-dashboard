# Build environment for Skylight D156 (Rockchip 4.19.232) out-of-tree USB Wi-Fi modules.
FROM ubuntu:22.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      bc bison build-essential ca-certificates clang-12 cpio flex kmod libelf-dev libssl-dev \
      lld-12 llvm-12 python3 xz-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
