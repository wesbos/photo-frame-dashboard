# PF1007L January firmware, smaller eMMC: macOS (Apple silicon) unit report

This USB-C-only PF1007L on January `20260113` firmware reached root ADB over USB with
[Route U](allwinner-a33-mainline-uboot.md), then ran the Home HQ kiosk as its Home app on
WebView 106 with the [boot fixes](pf1007l-boot-fixes.md) installed. Compared with the
[larger-eMMC January macOS report](pf1007l-macos-20260113-report.md):

- the **repository build read this smaller eMMC** with no extra patch: no no-HS patch, no 12 MHz
  cap. The warm-up SPL was run first on every load;
- the `ums` disk **disappeared twice during the backup**, both times between two segments of
  `backup-resume`. The [START STOP correction](patches/pf1007l-v2025.10-start-stop.patch)
  stopped it;
- with Wi-Fi on, the first boot from a laptop port **went dark about 30 s in**. `WIFI_DEFER` from
  the boot fixes stopped it.

Other January units with no boot patch: #129 (root USB ADB already on) and #125 (the test app's
hidden debugging control). This unit did not try the #125 route.

Observed on 2026-10-15 from an Apple silicon Mac (macOS 26.5.2), Docker Desktop 29.5.3,
Android platform-tools 37.0.1. Compared against repository main at `e97c50b`. One unit;
check each value on your own.

## Unit report

```text
About model / firmware: PF1007L
  YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113
AiMOR version: 6.0.78
Ports: USB-C only (no DC jack)
Cable and port that gave USB data: USB-A to USB-C data cable, then a generic USB-A to micro-USB
  adapter, then a RAVPower micro-USB to USB-C adapter, into a USB-C port on the Mac. No hub
T3 USB IDs seen / adb devices output: 1f3a:1000 "Android" (vendor "USB Developer"), 480 Mb/s; adb devices empty
T3b network ADB result (port 5555): skipped (owner kept the frame offline until AiMOR was disabled)
T4 sunxi-fel version output: AWUSBFEX soc=00001667(A33) 00000001 ver=0001 44 08 scratchpad=00007e00
T5 check-dump stage / chunks: skipped (Route U)
eMMC size in sectors: 30,535,680
Boot partition start sector: 172032
Boot image SHA-256 (sector 172032, 31,028 sectors):
  d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4
Route used and result: Route U, repository build at e97c50b (warm-up SPL first), then the same build
  plus the START STOP correction. Root ADB over USB (1f3a:1002, uid=0)
Host OS: macOS 26.5.2, Apple silicon (arm64)
First failed step and its exact output: section 4, emmc-macos.py backup-resume:
  STOP: [Errno 2] No such file or directory: '/dev/rdisk6' during segment 1 (backup).
```

## Route U, in order

| Step | Result |
| --- | --- |
| FEL card | `fel-card-macos.py backup` then `write` on a 32 GB card in a USB reader. Partition at sector 8192, readback verified |
| FEL | `1f3a:efe8` at 12 Mb/s, screen dark, `sunxi-fel version` answered |
| Load 1 (repository build) | `sunxi-fel spl sunxi-spl-warmup.bin`, `version` answered, then `uboot` + `ums-readonly.scr`. No `ERROR -7`. Both disks appeared as `1f3a:1010`: UMS disk 1 = eMMC, 15,634,268,160 bytes, `Media Read-Only: Yes`. Stable for more than 90 s |
| Backup run 1 | `backup-resume`: segment 1 of 15 read twice and saved, then the disk was gone before segment 2 |
| Load 2, backup run 2 | Same build. Segments 2 and 3 saved, then the disk was gone before segment 4 |
| Load 3 | Repository build plus the START STOP correction (applied with `git apply --unidiff-zero` to a copy of the source tree, built with `build-uboot.sh`'s Docker steps). SPL ends `0x458a` / `0x45ba`, as in the repository build |
| Backup run 3 | Segments 4 to 15 saved; image verified. About 56 min of `ums` with no drop |
| T6 | Partition starts env 139264, boot 172032, system 237568, recovery 2400256. Boot image `d71c313d…`, `ANDROID!`, 2048-byte page, 15,886,336 bytes |
| Boot patch | `boot-patch.py`: ramdisk `[192004, 203060)`, header `[172032, 172034)`, the same ranges as the guide. `write-boot.scr` with the START STOP build; `verify-resume`: "the eMMC equals the backup plus exactly the planned boot patch" |
| Android | Card removed: `1f3a:1002`, `adb -d shell id` = `uid=0(root)`, SDK 23, SELinux `Disabled` |

The USB-property check before the write: no `/data/property/persist.sys.usb.config` in the userdata
backup, and `build.prop` sets `persist.sys.usb.config=mass_storage`. That is the case the patch is
built for; ADB came up on the first boot.

### The `ums` drops

| | Run 1 | Run 2 |
| --- | --- | --- |
| U-Boot started | 09:33 | 09:59:07 |
| Disk gone | about 09:42 to 09:43 (not logged to the second) | 10:06:35 |
| Time after U-Boot started | about 9.5 min | 7.5 min |
| Where in the run | between segment 1 and segment 2 | between segment 3 and segment 4 |

- Observed: a 2-second `ioreg` log in run 2 showed the frame leave the USB tree completely: no
  `1f3a:1010`, no FEL device. `sunxi-fel version` then answered nothing. The frame was plugged
  directly into the Mac, with no hub. The macOS system log had nothing at that moment.
- Observed: both drops came in the second or so between one segment's file check and the next
  segment's first read, not during a read.
- Observed: with the START STOP correction, no drop in the remaining 12 segments, the boot write
  or the 21-minute `verify-resume`.
- Guess: macOS sent START STOP UNIT while the disk was briefly idle, as in
  [the May macOS report](pf1007l-macos-20260529-report.md#ums-disappeared-after-about-30-seconds).
  No USB trace was captured. On that unit the disk went at about 30 s; here it lasted minutes.

## After root

| Step | Result |
| --- | --- |
| Stock WebView | `44.0.2403.119`. Tar of `/system/app/webview` taken twice, identical |
| Rootless Launcher 3.9.1 | Installed. The owner reached Settings → Apps on the panel. There is no navigation bar; Settings' own back arrow works, but nothing leaves Settings |
| Disabled | `com.efercro.os.aimor`, `com.DeviceTest`, `com.yhk.qeota` (`/system/priv-app/frame_ota`, version `API_10-usaFrame-P-L_Yes-20240603`). `enabled="2"` in `package-restrictions.xml` within 5 s; kept after a reboot |
| WebView 106 | By [section 6](allwinner-a33-pf1007l.md#6-upgrade-webview-before-using-the-kiosk). `106.0.5249.126` after a reboot; no WebView `dlopen` errors |
| Home HQ | Built with JDK 17 and build-tools 34.0.0; `test-navigation.py` passed. The local demo over `adb reverse` rendered |
| Navigation service | `accessibility_enabled` read back `0` right after `settings put … 1`. With the `WRITE_SECURE_SETTINGS` grant, Home HQ logged `Re-enabled navigation service` at each start and the floating Back and Dashboard buttons worked. This is the January reset that [the kiosk README](../dashboard/kiosk/README.md#frames-without-home-or-back-buttons) says had not been tested on a January unit |
| Two-finger hold | Failed the first few times just after install (on one try, the dimming came in slowly and went away with no menu), then worked every time |
| Hosted demo | `net_error -202` on `*.workers.dev` (chain to GTS Root R4). The stock store has no GlobalSign Root CA (`5ad8a5d6.0`) and no `f013ecaf.0`, `5acf816d.0` or `6187b673.0`, as on the May unit in the [Route U notes](allwinner-a33-mainline-uboot.md). Adding GTS Root R1, GTS Root R4 and ISRG Root X1 (hashes from the [Uhale guide](si006-uhale.md)) fixed it |
| Home app | The Android 6 chooser's Just once / Always buttons apply only to the app at the top (the last one chosen). Tapping Home HQ lower in the list opened it once. Opening the chooser again put Home HQ at the top, and **Always** saved `always="true"` |

## Reboot and Wi-Fi start

- Observed: `adb reboot` worked three times with Wi-Fi off. The fourth, with Wi-Fi on, hung: black
  screen, no USB device. A power cycle was needed, as [the Route U notes](allwinner-a33-mainline-uboot.md) warn.
- Observed: the next boot, from the Mac's USB port with Wi-Fi on, showed the boot animation and
  then a black screen, again with no USB device.
- Recovery: a host loop ran `adb -d shell svc wifi disable` as soon as ADB answered (32 s
  uptime). That boot completed into Home HQ.
- [Boot fixes](pf1007l-boot-fixes.md) with `WIFI_DEFER=1`, `POWER_FIX=0`,
  `NTP_SERVER=time.google.com`, MAC from the serial number. `install.sh check` and `apply` passed on
  January firmware (the guide was tested on May). After a power cycle with Wi-Fi on, from the
  same Mac port: Home HQ in focus, `Wi-Fi started at uptime 42.86s`, the configured MAC, the right
  clock. `install.sh verify` passed.
- Guess: the dark boot was the Wi-Fi start brownout in the boot-fixes table. Power came from a
  laptop port through two adapters with a micro-USB link in the middle (see the cable line above),
  which may have made it worse. One boot each way; not a measured rate. Supply voltage was not
  measured.
