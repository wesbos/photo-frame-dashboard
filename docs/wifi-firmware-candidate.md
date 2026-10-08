# AP6256 firmware candidate and test boundary

## Evidence collected 2026-09-14

The running calendar is D156, Android 12, firmware build skylightOS-D156-user-release-keys-20250311.212629, bcmdhd 101.10.361.22. The loaded Wi-Fi firmware is 7.45.96.125 (2022-01-20). Native scans abort independently of the Skylight app.

A newer same-family firmware was downloaded for offline comparison from the hardware vendor Orange Pi's repository, pinned at commit `db5e86200ae592c467c4cfa50ec0c66cbc40b158`:

- [Firmware binary](https://github.com/orangepi-xunlong/firmware/blob/db5e86200ae592c467c4cfa50ec0c66cbc40b158/fw_bcm43456c5_ag.bin): 629,584 bytes, SHA-256 `a603124ff862a33263df0cd461722f95c9346ba4f63c5e0024033c328d903a5e`, embedded version 7.45.96.203 (2024-04-16), Ucode 1043.20745.
- Stock live binary: 606,190 bytes, SHA-256 `4e0d27ab7486d419f2e2c2ef473dad775df9a046428cf0bd2c46fbd80c5c7da9`, embedded version 7.45.96.125, Ucode 1043.20735.
- [Orange Pi NVRAM](https://github.com/orangepi-xunlong/firmware/blob/db5e86200ae592c467c4cfa50ec0c66cbc40b158/nvram_ap6256.txt): 2,732 bytes, SHA-256 `588430b4c2c167ca035f17da7478bec3d4922487152610d385d5ccb8f7c0a75f`. Parsing non-comment key/value settings found **no differences** from the stock 2,874-byte nvram_ap6256.txt. This is semantic settings equality, not byte equality.

The repository history attributes the current binary to commit f27567bc2bb765d617ca5468ca96ae4f2bbe56c7 (2024-10-09), titled “Update ap6256 firmware”; it supplies no specific scan-abort fix in that message. The embedded feature string adds apf4 in the candidate. Matching chip-family names and NVRAM settings make it worth testing; neither proves driver ABI compatibility, a particular bug fix, or Skylight support. No Skylight-specific system image was found. Candidate binaries and private captures are ignored under diagnostics/wifi-next.

## Why this is not an ordinary app update

The firmware is loaded by bcmdhd from /vendor/etc/firmware. An ordinary app cannot replace it or access root-only driver logging controls. Live dhd_console_ms remains root-owned. Android debugfs is disabled. Existing temporary recovery boot attempts did not yield a usable root shell; do not repeat the hung RAM-boot route without serial evidence.

## Proposed controlled test, not executed

First establish root diagnostics through a separately reviewed boot path. See debug-ramdisk-research.md. A normal-boot ramdisk modification is a persistent boot-partition write; it could fail to boot. The complete main-flash backup is verified, but writing/restoring that partition has not been tested. Do not describe recovery as guaranteed.

With a working root shell, first capture a stock scan with firmware console logging enabled and restore logging afterward. Only if this evidence justifies it, stage the candidate file outside vendor, retain stock NVRAM/config/country settings, and use a reversible runtime firmware-path override or bind mount. Inspect driver reload behavior before cycling Wi-Fi. Verify the candidate version actually loaded, then collect a single non-overlapping scan and the abort/status logs. Restore the stock path/mount and logging, and verify the stock version reloads. No regulatory, calibration or board data changes are proposed.

No candidate firmware was installed, no driver was replaced, and no boot image was flashed during this comparison. The activated Skylight USB Test app remains the working workaround.

## Offline debug-boot candidate prepared

`scripts/build-debug-boot.py` produced a full 64 MiB candidate at ignored diagnostics/debug-boot-candidate/boot.img, SHA-256 `f6e2c27c89a3db7835089fa8037909dc5e7eb62745eb90471fabab58b49821b3`. A separate host byte-scope check confirmed that changes are confined to the existing ramdisk allocation, ramdisk-size header field and Android image-ID field. Gzip extraction passed. Kernel, device-tree/resource components and the entire unreferenced tail remain at their original offsets. The ramdisk adds only force_debuggable and adb_debug.prop; existing records and authentication settings are preserved.

This is a reviewable candidate, not proof of bootability or root access. It has not been uploaded or flashed. The owner priority is general Android use; Skylight activation is no longer the reason to pursue root. Root would permit native Wi-Fi console tracing and the controlled firmware comparison described above.

## Diagnostic boot test outcome

The owner authorized a persistent diagnostic boot test. Candidate flash was acknowledged, but its reboot returned to fastboot instead of Android. The original boot image was restored; normal Android completed boot, Lawnchair remains default, and USB internet again passed HTTP204. Root access was not obtained. The newer radio firmware remains an offline candidate and has not been installed. See debug-ramdisk-research.md for the recorded test limitations.
