#!/bin/sh
# Build Rockchip's RTL8188EU USB Wi-Fi driver for the Skylight D156 kernel (4.19.232).
#
# Uses the skylight-kbuild image (scripts/usb-wifi.Dockerfile) and a case-sensitive
# Docker volume holding rockchip-linux/kernel develop-4.19. Builds the full kernel
# and modules from the device's own /proc/config.gz plus CONFIG_RTL8188EU=m so the
# resulting Module.symvers can be compared with the stock kernel's CRCs
# (scripts/extract-symvers.py). No device access.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
HOST="$ROOT/diagnostics/tools/usb-wifi-build"

docker run --rm -v skylight-kernel:/work -v "$HOST":/host skylight-kbuild bash -c '
set -eu
cd /work/linux
cp /host/config.stock .config
./scripts/config --module RTL8188EU
# Public rknpu forces -Werror and trips on an option Skylight leaves disabled.
sed -i "/^ccflags-y += -Werror$/d" drivers/rknpu/Makefile
MAKE="make ARCH=arm64 CC=clang-12 LD=ld.lld-12 HOSTCC=gcc LOCALVERSION= KCFLAGS=-Wno-error"
$MAKE olddefconfig
touch .scmversion
$MAKE -j"$(nproc)" Image modules
ko=drivers/net/wireless/rockchip_wlan/rtl8188eu/8188eu.ko
cp Module.symvers /host/Module.symvers.built
cp "$ko" /host/8188eu.ko
modinfo /host/8188eu.ko | grep -E "^(vermagic|alias)" | head -5
sha256sum /host/8188eu.ko
'
