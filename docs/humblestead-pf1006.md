# Humblestead PF1006: investigation report

**ADB access is unconfirmed. SD boot has not been tested on this unit.**
This report covers one unit investigated on 2026-10-15 and 2026-10-16.
No frame storage capture, frame backup or root access is available.

## Unit and observations

| Item | Evidence |
| --- | --- |
| Retail listing | [Humblestead, Amazon US B0BJDR9G3X](https://www.amazon.com/dp/B0BJDR9G3X). Advertised: 10.1-inch display, 1280 × 800 resolution, 32 GB storage. |
| About model | `PF1006`, reported by the owner. |
| About firmware | `YHK.F-null-A33-1001-D1024-PF1006-46-DL-OS-AM.0.20240910`, transcribed by the owner. |
| AiMOR version | `6.0.26`. The startup screen also showed `V6.0.26`. |
| Setup | The owner completed setup and opened System Settings → About. |
| Ports | The owner reports an SD card slot and no visible USB connector. The slot type and complete port inventory are unverified. |
| Host computer | Apple silicon Mac, macOS 26.6.2. Android platform-tools 37.0.1 installed through Homebrew. |
| Network ADB | `adb connect <frame-ip>:5555` returned `Connection refused`. `adb devices -l` listed no devices. |
| USB ADB | Not tested. No usable connector identified. |
| Processor | Allwinner A33 inferred from the firmware string. No chip query, shell output or board inspection confirms it. |
| Android, RAM, storage | Unverified. AiMOR's version is not the Android version. `D1024` and the advertised capacity are not measurements. |
| Partition map, boot hash, root | Unknown. No frame storage read or shell access yet. |

The network test shows that ADB was unavailable on TCP port 5555 at that time.
It does not show whether `adbd` is installed or whether a setting can start ADB.

## Other boards and firmware

The [PF1007L SD procedure](allwinner-a33-sdcard-adb-wifi.md) applies to a different model and firmware.
Its DRAM settings, eMMC wiring, device numbers, partition offsets and boot hashes are unverified on this PF1006.
Do not use its apply or restore scripts on this unit.
Do not change its hash checks or copy its partition offsets into a new writer.
Even a storage-read program needs compatible memory and controller settings.

The manufacturer's 2022 [model filing](https://fccid.io/2AW9M-PORTRAIT/Letter/Model-Difference-5791964)
lists PF1006 and PF1006PLUS under FCC ID `2AW9M-PORTRAIT`.
The [internal photographs](https://apps.fcc.gov/eas/GetApplicationAttachment.html?id=5791961)
show an Allwinner processor, an AXP223 power-management chip and four Samsung K4B2G1646F memory packages.
That board has USB-A and mini-USB connectors.
These photographs do not establish the hardware in this unit.

The [draft PF1006 V43 report (#151)](https://github.com/wesbos/photo-frame-dashboard/pull/151)
describes a board with USB and different firmware.
It did not use this SD probe and does not validate this build profile.

## Experimental probe

The [PF1006 probe guide](../scripts/pf1006-probe/README.md) explains the tools and the card procedure.
The probe reads the first 4 MiB of internal storage twice.
It saves a capture: a status file and a binary copy of those bytes.
The verifier compares the run ID, file size, read hashes and SD readback result.
It also rejects known filler data.
This small capture cannot replace a complete frame backup.

The build blocks non-SD storage writes and erases.
It restricts persistent eMMC settings and requires at least 256 MiB of detected RAM.
It still applies another board's power, memory and controller settings.
The guide lists these settings and their limits.

## Completed work

- On 2026-10-15, the image cross-built on the Mac with GCC 16.2.0 and binutils 2.47.
  The ARM image passed the independent SPL checksum and script CRC checks.
  At that time, 43 Python tests and both C block-API tests passed.
  These results apply to that build and test revision.
- On 2026-10-16, the card helper prepared the original build on a SanDisk Ultra PLUS SDXC UHS-I 64 GB card.
  Its measured capacity was 63,864,569,856 bytes.
  The MBR/FAT32 partition started at 16 MiB.
  Bootloader and script readback passed.
  The saved 4 MiB card-prefix backup passed verification.
  This backup contains the card state after formatting.
  The helper ejected the card successfully.
- On 2026-10-16, the revised native build completed.
  All 56 Python tests passed: 31 card-helper tests and 25 verifier tests.
  Both C block-API test variants passed.
  The revised build passed current-source, artifact and approved image hash checks.
  The helper prepared it on the same card that day.
  Saved records confirm 512-byte sectors and the FAT32 partition at 16 MiB.
  The saved 4 MiB post-format backup passed size and hash checks.
  The helper completion log confirms bootloader/script readback and successful eject.
  After eject, verification checked the saved build, state, backup and completion log.

These records establish host validation and card preparation.
They do not establish frame compatibility.

## Next steps

1. Confirm the frame's card slot, external ports and power connector.
2. Review the exact build under the [repository rules](../README.md#rules-we-learned-the-hard-way) before the first frame test.
3. Collect the result after one approved frame boot.
   A dark screen does not show that the probe succeeded.
4. If storage reads are consistent, determine this unit's partition map.
5. Make a verified frame backup before a persistent change.
   Verification requires byte counts, SHA-256 hashes, independent reads, filler checks and a second backup copy.
   A 2 GiB prefix is also not a complete frame backup.
6. Inspect this unit's boot image and Android startup configuration offline.
   This establishes how `adbd` starts and whether it supports host-key authentication.
7. Develop a patch and restore procedure only after the layout and original image are verified.
8. Before claiming support, verify ADB access and shell identity after a cold boot.
9. Record the Android properties and write/readback results.
10. Before claiming authenticated network ADB, confirm that a different host key cannot connect.

No PF1006 patch or frame restore procedure is available in this report.
Keep failed test results with future success records.
Publish firmware strings and boot-image hashes only after removing private data.
Keep dumps, whole-device hashes, vendor APKs, credentials, serials and network identifiers private.
