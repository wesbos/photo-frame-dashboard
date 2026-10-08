# Offline boot-chain analysis

Examined the valid first 32 MiB backup and the complete `uboot`, `dtbo`, `vbmeta`, and `misc` partitions on 2026-09-14. Raw images and extracted binaries stay in ignored directories. Nothing in this analysis writes to the calendar.

## Reusable offline checks

Run the dependency-free [inspection script](../scripts/inspect-backup.py) with Python 3:

```sh
python3 scripts/inspect-backup.py backups/gpt-primary.img --kind gpt
python3 scripts/inspect-backup.py backups/uboot.img --kind fit
python3 scripts/inspect-backup.py backups/boot-INCOMPLETE-CC.img --kind raw
```

The script reads files only and produces JSON. Use an explicit `--kind` when the expected format is known; automatic detection cannot distinguish an unknown format from a damaged header. GPT checks cover primary-header and partition-array CRC32, partition bounds, and overlaps; they do not validate a backup GPT or partition payloads. FIT checks verify component SHA-256 hashes, not signatures. Raw mode only scans for filler and never reports format integrity success.

All modes flag runs of aligned, entirely `0xCC` 4 KiB blocks; `--cc-block-size` changes this granularity. Such a run is suspicious rather than universal proof of corruption. Absence of filler does not prove completeness. A final partial block is not included in this check. Exit status is 0 for completed checks with no detected problem, 1 for invalid structure/hash/CRC or suspicious filler, and 2 for input/argument errors.

Validation on these local images: the primary GPT and U-Boot FIT pass; incomplete boot fails with a filler run starting at 7 MiB; incomplete recovery fails with the whole 128 MiB flagged. Truncated GPT and FIT fixtures, a changed GPT header byte, a changed GPT partition-array byte, and a changed FIT payload byte all fail as expected. Temporary corrupted fixtures were not saved as backups.

For a future validated full-disk gzip backup produced by `backup-flash.py`, [extract-partitions.py](../scripts/extract-partitions.py) extracts `boot`, `recovery`, and `super` without expanding the entire disk:

```sh
python3 scripts/extract-partitions.py backups/full-flash.img.gz --output-dir backups/extracted
```

Add `--probe-manifest backups/patched-reader.json` to compare saved independent reads against their exact byte ranges in the source while streaming. The script first verifies each saved probe's size and SHA-256, then requires every sampled byte to match. The extraction manifest records those comparisons.

This command requires the adjacent backup manifest and a new output directory. It reads the embedded primary GPT, checks partition bounds, streams selected ranges into temporary files, and consumes the complete gzip stream to verify its raw SHA-256 and size against the manifest before publishing `.img` outputs. A partition manifest records offsets, lengths, and SHA-256 hashes. It preserves the original compressed backup. Matching hashes establish consistency with that backup, not manufacturer authenticity or independent read agreement. Failed runs leave `.partial` files, which must not be used as validated images.

The extraction workflow has been checked with synthetic good images, bad GPT CRCs, incorrect source hashes, truncated gzip streams, invalid extraction bounds, and existing output directories. Those tests can be repeated with `python3 scripts/test-extract-partitions.py`; they use no device data or USB connection.

## Findings

| Item | Confirmed contents |
| --- | --- |
| U-Boot version | `U-Boot 2017.09 (Mar 11 2025 - 20:56:32 +0000)` |
| U-Boot board configuration | `evb_rk3568`; DT compatible `rockchip,rk3568-evb`, `rockchip,rk3568` |
| U-Boot model string | `Rockchip RK3568 Evaluation Board` |
| UART console | UART2 at `0xfe660000`; default baud rate **1,500,000** |
| U-Boot input/output defaults | `stdin=serial,usbkbd`; `stdout=serial,vidconsole`; `stderr=serial,vidconsole` |
| Boot delay default | `bootdelay=0` |
| Android verified-boot metadata | Unsigned, empty AVB metadata with verification-disabled flag set |
| FIT integrity | All nine component SHA-256 hashes match the extracted data |
| FIT signatures | A signature configuration exists, but has no signature `value` |

The generic evaluation-board name identifies the software configuration. It does not identify the commercial PCB revision, RAM type, or Wi-Fi module. Similarly, compiled default environment strings do not establish the current runtime environment.

The UART baud rate is a useful lead for the earlier unsuccessful serial attempt. A connection attempted only at 115,200 would not match this firmware default. The dump does not establish pad voltage, pin assignment, or whether a usable prompt can be interrupted with zero boot delay.

## AVB and FIT details

The `vbmeta` header contains:

```text
magic: AVB0
required libavb version: 1.0
authentication block size: 0
auxiliary block size: 0
algorithm type: 0 (NONE)
rollback index: 0
flags: 2
rollback index location: 0
release string: avbtool 1.1.0
```

Flag 2 is `AVB_VBMETA_IMAGE_FLAGS_VERIFICATION_DISABLED` in [AOSP's header definition](https://android.googlesource.com/platform/external/avb/+/refs/heads/main/libavb/avb_vbmeta_image.h). There are no descriptors, public key, or authentication data in this metadata image. This is evidence about the installed metadata, not a measurement of hardware fuses or a live fastboot unlock state.

The U-Boot FIT bundles U-Boot, six ARM Trusted Firmware segments, OP-TEE, and a U-Boot device tree. Each has a SHA-256 hash, and all nine hashes were independently recomputed successfully. The configuration includes `algo = "sha256,rsa2048"`, `key-name-hint = "dev"`, and `sign-images`, but no signature bytes. Hash integrity should not be confused with signature authentication; [U-Boot documents the distinction](https://docs.u-boot.org/en/latest/usage/fit/signature.html).

The `trust` partition is entirely zero-filled. That alone is not a missing-firmware problem: the FIT already contains ATF and OP-TEE.

## Boot routes present in the firmware

The default command is:

```text
boot_android ${devtype} ${devnum};boot_fit;bootrkp;run distro_bootcmd;
```

Embedded help and command strings include Android fastboot, USB mass storage (`ums`), Rockusb, boot-ROM download (`rbrom`), and RAM-image boot commands. These are candidate routes if a U-Boot command interface becomes accessible. Strings alone do not prove that a given USB mode is reachable from the current loader session or that fastboot accepts temporary boot images.

The small Android DT overlay changes boot-device arguments and reboot-mode values:

| Mode | Value |
| --- | --- |
| normal | `0x5242c300` |
| loader | `0x5242c301` |
| recovery | `0x5242c303` |
| fastboot | `0x5242c303` |
| bootloader | `0x5242c309` |
| charge | `0x5242c30b` |

In this overlay, `fastboot` and `recovery` share a value. Do not assume these labels are interchangeable with host-tool reset subcommands: the tool, protocol, and bootloader interpret their own values.

The first 2,048 bytes of `misc`, where the ordinary Android bootloader message resides, are all zero. No recovery command was inferred from that region. Other data in `misc` was kept private.

## What this enables next

The installed metadata is encouraging for a future temporary diagnostic boot. It does not yet establish a working shell route. Obtain a complete boot/recovery backup first, inspect its real ramdisk and Android device tree, and determine whether a RAM-only boot interface is reachable. The existing `boot-INCOMPLETE-CC.img` and `recovery-INCOMPLETE-CC.img` cannot answer those questions: bytes beyond the 32 MiB flash boundary are loader-generated filler.

If USB-only access cannot provide a temporary boot interface, the confirmed 1,500,000-baud UART configuration gives a concrete setting for revisiting serial access. No bootloader, metadata, partition, or persistent environment modification was performed for this analysis.
