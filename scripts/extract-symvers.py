#!/usr/bin/env python3
"""Rebuild vmlinux Module.symvers from the stock boot image's raw arm64 kernel.

Linux 4.19 with HAVE_ARCH_PREL32_RELOCATIONS stores each export as two
self-relative int32 offsets (value, name); __kcrctab holds one absolute uint32
CRC per export in the same order (MODULE_REL_CRCS is not set). Section bounds
come from the live device's /proc/kallsyms. No device access is performed.
"""

from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
BOOT = ROOT / "backups/extracted/boot.img"
OUTPUT = ROOT / "diagnostics/tools/usb-wifi-build/Module.symvers.stock"

TEXT = 0xFFFFFF8008080000
SECTIONS = {
    "EXPORT_SYMBOL": (0xFFFFFF8009796FE0, 0xFFFFFF80097A2E90, 0xFFFFFF80097ADBD8, 0xFFFFFF80097B3B30),
    "EXPORT_SYMBOL_GPL": (0xFFFFFF80097A2E90, 0xFFFFFF80097ADBD8, 0xFFFFFF80097B3B30, 0xFFFFFF80097B91D4),
}


def main():
    boot = BOOT.read_bytes()
    if boot[:8] != b"ANDROID!":
        sys.exit("not an Android boot image")
    kernel_size, page_size = struct.unpack_from("<I", boot, 8)[0], struct.unpack_from("<I", boot, 36)[0]
    image = boot[page_size:page_size + kernel_size]
    if image[56:60] != b"ARMd":
        sys.exit("kernel is not a raw arm64 Image")

    def offset(address):
        return address - TEXT

    def cstring(address):
        start = offset(address)
        return image[start:image.index(b"\0", start)].decode()

    lines = []
    for kind, (sym_start, sym_stop, crc_start, crc_stop) in SECTIONS.items():
        count = (sym_stop - sym_start) // 8
        if count != (crc_stop - crc_start) // 4:
            sys.exit(f"{kind}: ksymtab/kcrctab count mismatch")
        for i in range(count):
            entry = sym_start + i * 8
            _, name_rel = struct.unpack_from("<ii", image, offset(entry))
            name = cstring(entry + 4 + name_rel)
            crc = struct.unpack_from("<I", image, offset(crc_start + i * 4))[0]
            lines.append(f"0x{crc:08x}\t{name}\tvmlinux\t{kind}")
        print(kind, count)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
