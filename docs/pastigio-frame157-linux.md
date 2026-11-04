# Linux and Omarchy on the Pastigio FRAME157 (RK3326)

Report from one unit, 2026-10-15 to 2026-10-26, built and flashed from an Apple
silicon Mac. The kernel patches, device tree, boot chain, scripts and logs are in
[lachieh/framarchy](https://github.com/lachieh/framarchy). This page summarises
what works and how the frame boots. Follow that repo for the steps.

**Verified result:** mainline Linux 6.18 and Arch Linux ARM (aarch64) boot by
default, with [Omarchy](https://github.com/basecamp/omarchy) (Hyprland) on the
1920×1080 panel. Touch, Wi-Fi, GPU and CPU frequency scaling work. Only the eMMC
`boot` partition was changed. Stock U-Boot and the other Android partitions
stay in place, and the root filesystem is on a microSD card.

## Identity

The same model as [pastigio-frame157.md](pastigio-frame157.md), with a different
USB ID again.

| Item | Observed value |
| --- | --- |
| About model / Android model | `DPF Frame 157` / `FRAME157` |
| Frameo | v1.29.16 (60080) |
| Board | C-Link `CL-RK3326-DP105F` V1.3 |
| SoC / RAM / storage | Rockchip RK3326 (4× Cortex-A35, ARMv8) / 1 GB / 32 GB eMMC |
| Android ADB USB ID | `2211:0012` |
| Display path | DSI → Lontium LT8911EXB bridge (i2c-2 `0x29`) → eDP panel |
| Touch | Silead GSL3676 at i2c-1 `0x40` |
| Wi-Fi | Rockchip RK915 SDIO |
| Debug UART | UART2, 1,500,000 baud, on labelled GND/RX/TX pads |

The board also has an **UPDATE** button, which enters Rockchip Loader mode when
held while connecting power.

## How it boots

Stock U-Boot refuses a mainline device tree, and mainline Linux hangs on the
vendor one. A mainline U-Boot in between solves both:

```text
BootROM → stock idbloader/TF-A → stock U-Boot (unchanged)
  → eMMC "boot" partition: mainline U-Boot, packaged as an arm64 kernel image
    with the stock DTB
  → microSD extlinux.conf
  → Linux 6.18 with a FRAME157 device tree, root filesystem on microSD
```

The chain-loading U-Boot has no PMIC or regulator drivers and no saved
environment, so it cannot change a voltage rail or write the eMMC.

## What it needed

- **A new DRM bridge driver for the LT8911EXB.** There is none in mainline. The
  bridge only locks to burst-mode DSI with LP commands, as in the stock panel
  node (`dsi,flags = 0x803`). The driver has a test-pattern option to check the
  eDP side on its own.
- **Reserved secure RAM.** Stock TF-A/OP-TEE use `0x08400000`–`0x0a200000`.
  Mainline U-Boot reports all RAM to Linux, so the device tree must reserve that
  range. Without it, the frame showed SD I/O errors, bus errors and hangs a few
  seconds into boot.
- **Touch firmware.** The Silead firmware was extracted from the stock kernel.
  Touch is calibrated to 1784×1160, with both axes inverted.
- **Wi-Fi.** The out-of-tree [rei512/rk915](https://github.com/rei512/rk915)
  driver, plus an MMC quirks patch.
- **CPU limit.** CPU speed is capped at 1,008 MHz like stock Android. Under load
  it reached 85 °C at 1,296 MHz and 73 °C capped.
- **USB-A to USB-C data cable.** USB-C to USB-C did not enumerate, as on the
  other FRAME157 units.

## Backup and undo

- Loader-mode reads past 32 MiB returned `0xCC` filler on this unit too (see
  [loader-research.md](loader-research.md)). The restore source was a
  per-partition backup over root ADB, each image checked against a hash taken on
  the frame.
- Only the eMMC `boot` partition holds the chain loader. To return to Android,
  write the backed-up `boot` image from Loader mode. The framarchy scripts check
  the GPT and refuse images larger than the partition.
- An early test wrote an image larger than `boot` with plain
  `rkdeveloptool wlx`, which does not check sizes. A later check against the
  backup found the following partitions intact, but use a writer that checks
  the size.

## Not done yet

- The system still runs from microSD. It has not been moved to the eMMC.
- Audio, the accelerometer and the RTC are not covered yet.
