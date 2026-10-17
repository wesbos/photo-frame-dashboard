# PF1007L January firmware, larger eMMC: macOS (Apple silicon) unit report

One USB-C-only PF1007L, January `20260113` firmware, rooted with Route U from a macOS host on
2026-10-17. Same firmware and eMMC size as the
[January macOS (Intel) report](pf1007l-macos-20260113-report.md), and the same fix: the stock
8-bit U-Boot never exposed the eMMC; the [no-HS patch](patches/pf1007l-v2025.10-no-mmc-hs.patch)
plus the [START STOP correction](patches/pf1007l-v2025.10-start-stop.patch) did. Unlike that unit,
this one did **not** need the warm-up SPL, and the failure looked different: no USB device at all,
not an SD-only `ums`.

Everything below is from one unit. Observations and guesses are kept separate.

## Unit report

```text
About model / firmware: PF1007L
  YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113
AiMOR version: 6.0.78
Ports: USB-C only (no DC jack)
Cable and port that gave USB data: USB-A to USB-C cable into the USB 2.0 half of a
  Genesys Logic USB 3 hub (05e3:0610 / 05e3:0626) on a USB-C-only Mac. A first attempt with the
  cable that came with the frame, through a USB-C to USB-A adapter, showed no device at all
T3 USB IDs seen / adb devices output: 1f3a:1000 "Android", 480 Mb/s; adb devices empty
T3b network ADB result (port 5555): skipped (owner kept the frame offline)
T4 sunxi-fel version output: AWUSBFEX soc=00001667(A33) 00000001 ver=0001 44 08 scratchpad=00007e00
T5 check-dump stage / chunks: skipped (Route U)
eMMC size in sectors: 30,777,344
Boot partition start sector: 172032
Boot image SHA-256 (sector 172032, 31,028 sectors):
  d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4
Route used and result: Route U with the no-HS patch and the START STOP correction (no warm-up SPL
  needed). Root ADB over USB (1f3a:1002, uid=0)
Host OS: macOS 27.2, Apple M1 Pro
First failed step and its exact output: section 4 with the repository build (8-bit eMMC):
  sunxi-fel printed "Starting U-Boot (0x4A000000)." and exited 0, then no USB device of any
  kind appeared for about 3 minutes (no 1f3a, no UMS disk)
```

## What happened, in order

| Attempt | Build and script | Result |
| --- | --- | --- |
| 1 | Repository build at `e97c50b` (8-bit eMMC), `ums-readonly.scr` (`ums 0 mmc 0,1`) | DRAM trained on the first cold start; U-Boot uploaded and started. No USB device appeared in about 3 minutes of checks |
| 2 (diagnostic) | Same build, a one-line script `ums 0 mmc 0` (SD card only) | `1f3a:1010` and the SD card as a read-only disk within 10 s. The USB gadget works; the stall is in the eMMC bring-up |
| 3 | Repository build + no-HS patch (4-bit, 26 MHz, HS caps removed) + START STOP correction, `ums-readonly.scr` | Both disks within 10 s. eMMC: "UMS disk 1", 15,758,000,128 bytes, `Media Read-Only: Yes` |

Attempt 1 matches the first row of the
[U-Boot settings table](pf1007l-start-here.md#u-boot-settings-that-fixed-ums-problems): no USB
device after U-Boot starts while an SD-only script enumerates. Its 4-bit 26 MHz fix is part of the
no-HS patch, so this report does not show whether the HS removal was also needed on this unit.
A 4-bit build that keeps HS was not tried.

Guess: the 8-bit high-speed bring-up of the eMMC hangs before `ums` starts, so the gadget never
appears. With no console this was not confirmed.

## Build details

`build-uboot.sh` refuses a source tree with changes other than its own patch, so the no-HS build
was made in a copy, as in the Intel report:

1. Copy `diagnostics/u-boot` (at `e50b1e87` with `pf1007l-uboot.patch` applied) to
   `diagnostics/u-boot-nohs`.
2. `git apply docs/patches/pf1007l-v2025.10-no-mmc-hs.patch`
3. `git apply --unidiff-zero docs/patches/pf1007l-v2025.10-start-stop.patch`
4. The same `docker run` commands as `build-uboot.sh` (main and warm-up builds, `mkimage`) into
   `diagnostics/a33-uboot-nohs-out`, then its SPL-end check.

| Build | SPL code ends at, main / warm-up |
| --- | --- |
| Repository build | `0x458a` / `0x45ba` |
| + no-HS + START STOP | `0x458a` / `0x45ba` |

Host tools: `sunxi-tools` at `d7bbd172` built with Homebrew `libusb`, `dtc` and `pkgconf`; FEL stub
SHA-256 matched. Docker was OrbStack. For the kiosk, the `temurin@17` cask failed without an
administrator password; Homebrew's `openjdk@17` formula worked with `build.sh`.

## Backup, write and verify

- `fel-card-macos.py` accepted a 32 GB microSDHC card in the hub's own card reader (USB,
  external). Its first partition started at sector 8192.
- `emmc-macos.py backup-resume` completed on the first run through the hub: 15 segments, each read
  twice from the disk and once from the file.
- `boot-patch.py` reported ramdisk `[192004, 203060)` and header `[172032, 172034)`, the same ranges
  as the other January units.
- The guarded write used the no-HS U-Boot (not the repository build, which cannot reach this
  eMMC) with the four payloads and `write-boot.scr`, in one `sunxi-fel` call. The eMMC then came
  back alone as "UMS disk 0" under a new disk number.
- `emmc-macos.py verify-resume`: "the eMMC equals the backup plus exactly the planned boot patch."
  Android had not booted between backup and write.
- First boot: `1f3a:1002`, `adb -d shell id` → `uid=0(root)`, fingerprint
  `AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260113:eng/test-keys`,
  `persist.sys.usb.config=mass_storage`.

## Power cycling through a hub

Observed twice: after the owner unplugged and replugged the frame, the Mac still showed the
previous session's U-Boot gadget (`1f3a:1010`) or no Allwinner device, and `sunxi-fel` reported
"FEL device not found". A second unplug of about 10 seconds brought the frame back in FEL each time.
Guess: the first replug was too quick for the frame to lose power. Check `sunxi-fel version` before
every RAM payload; nothing is loaded when it fails.

## After root

Followed sections 5 to 7 of the [PF1007L guide](allwinner-a33-pf1007l.md#5-install-a-launcher-and-optional-firefox-fallback),
the T8 lock-down and the [boot fixes](pf1007l-boot-fixes.md):

- Rootless Launcher 3.9.1 (hash matched) installed and confirmed on the panel before
  `com.efercro.os.aimor`, `com.yhk.qeota` (`API_10-usaFrame-P-L_Yes-20240603`) and `com.DeviceTest`
  (`YHKSign_20250303`) were disabled. `package-restrictions.xml` showed `enabled="2"` for all three
  within 5 s. After a power cycle they stayed disabled, with no processes and no `:7806` connection.
- WebView 106.0.5249.126 swapped into `/system/app/webview` with its three native libraries; the
  stock tree is kept at `/system/homehq-stock-webview`. `/system` had 405,820 KiB free before the
  swap. After a reboot, no `dlopen` errors.
- The three roots from the [Uhale guide](si006-uhale.md#fonts-and-https-photos) were absent and were
  added. Their DER SHA-256 values matched the guide, and the filenames matched
  `openssl x509 -subject_hash_old`. Home HQ on `home-dashboard.wesbos.workers.dev` then rendered
  with its fonts and photo.
- Android 6 has no `cmd`, so `cmd package set-home-activity` failed. Pressing Home
  (`input keyevent KEYCODE_HOME`) after `--ez home true` showed the chooser; the owner picked
  Home HQ → Always.
- Boot fixes: `install.sh check`, `apply`, then `verify` after a power cycle: configured MAC,
  correct clock, Home HQ in focus, `Wi-Fi started at uptime 42.79s`. `POWER_FIX` was left off
  because the frame was still powered from the hub.
