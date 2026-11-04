# PF1007L / AiMOR `20260519`: macOS root ADB report

One AEEZO/AiMOR PF1007L was rooted from macOS using the SD-card FEL entry
and mainline U-Boot route documented in
[`allwinner-a33-mainline-uboot.md`](allwinner-a33-mainline-uboot.md).
This report records the unit-specific observations; it is not a standalone
flash recipe. Follow that guide from the beginning and stop on any mismatch.

## Unit and result

```text
About-screen model: PF1007L
About-screen firmware: YHK.F-null-A33-1001-D1024-PF1007L-FL-AIMOR-SO.0.20260519   (as read; other 20260519 units show FL-AIMOR-OS)
Frame ID: omitted
Android model / product / device: AEEZO / astar_m86_8723cs / astar-m86_8723cs
Android: 6.0.1, SDK 23, armeabi-v7a
eMMC: 30,777,344 sectors (15,758,000,128 bytes)
Host: macOS
FEL: AWUSBFEX soc=00001667(A33)
Stock USB: adb devices showed no device
After guarded boot patch: adb devices listed the frame; adb shell id returned uid=0(root)
```

The firmware label was read from Settings → About. The Android product properties
and the FEL SoC query support identifying this unit as an A33 PF1007L. The `AEEZO`
Android model property by itself is not a board identification.

## What worked on this unit

1. A 64 GB SDXC card was formatted as MBR/FAT32 (`FRAMEBOOT`) using an external
   USB card reader. The macOS FEL-card script backed up the first 4 MiB and wrote
   the verified 8 KiB upstream Allwinner FEL stub at byte offset 8 KiB. The script
   read the prefix back and confirmed that only those 8 KiB changed.
2. With the prepared card inserted and the frame power-cycled, `sunxi-fel version`
   identified an A33 (`soc=00001667`). The display staying black in FEL was expected.
3. The host loaded the repository's warm-up SPL and mainline U-Boot through FEL.
   U-Boot exposed the eMMC as a read-only USB mass-storage device.
4. The complete eMMC was backed up. The guarded `verify` command confirmed that
   the eMMC matched that backup plus exactly the planned boot-image patch.
5. After a cold boot with the FEL card removed, Android appeared and USB ADB
   returned `uid=0(root)` directly; no `su` command or vendor test-app password
   was needed.

Use the commands and checks in the mainline U-Boot guide for each of these steps.
In particular, identify the SD card and eMMC afresh by size and read-only state;
never reuse a disk number, sector offset, boot image or backup from another frame.

## Other observations

- Tapping the model entry five times opened AiMOR's “Open test app” password
  prompt. The password was not known at the time (other units use `YHK88888888`,
  [#135](https://github.com/wesbos/photo-frame-dashboard/issues/135)), and that screen was not needed for the successful
  root route.
  On a later `20260519` unit (same boot image, `9a6e2456`), `YHK88888888` opened the test app,
  and switching its debugging control from IS CLOSED to is open gave root USB ADB with no boot patch. It came back after a reboot.
  See the [firmware table](pf1007l-start-here.md#known-firmware-and-units).
- During startup a brief screen offered a “debug mode” action with a countdown.
  Its role in the successful route was not established; do not assume it is needed.
- The frame had previously been disconnected from Wi-Fi during the recovery work.
- The 64 GB card worked for the FEL stub route on this unit. This does not establish
  that every PF1007L accepts every SDXC card or partition layout.

## Limits and safety

This is one unit on one firmware build. PF1007L units sharing the model or firmware
can differ in eMMC size, boot contents, USB configuration and whether ADB is already
enabled. The exact firmware suffix recorded here also differs from some other
`20260519` reports; compare the full string and inspect the device before choosing
any write procedure.

Keep the complete eMMC image, card-prefix backup, device serials, Frame ID and
other identifiers private. Do not publish them in an issue or pull request. Follow
the repository's [backup and verification rules](../README.md#rules-we-learned-the-hard-way)
and the [AiMOR remote-root-shell security notes](aimor-remote-root-shell.md).
