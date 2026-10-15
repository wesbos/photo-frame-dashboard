# PF1007L January firmware: root USB ADB already on, full setup over USB

One USB-C-only PF1007L on January `20260113` firmware already had **root USB ADB** the first
time it reached a computer. No SD card, FEL, boot patch or network step was used. Everything
after that, including a full-eMMC backup, the launcher, WebView 106 and the Home HQ kiosk, was
done over the USB cable from Windows 11.

Observed on 2026-10-14 and 2026-10-15. One unit; check each value on your own.

## How ADB came to be on is not known

On first connection the unit enumerated as `1f3a:1002` with
`persist.sys.usb.config=mass_storage,adb` in `/data/property`, overriding `mass_storage` in
`/system/build.prop`. That is the same state that
[PR #125](https://github.com/wesbos/photo-frame-dashboard/pull/125) reached on another January
unit by switching a hidden test-app control from "is closed" to "is open". Whether that control
was switched on this unit, and by whom (for example at the factory), is not known. So this is
**not** evidence that January firmware ships with ADB on. Run [T3](pf1007l-start-here.md#t3-usb-data-test) before anything else.

Because the setting lives in `/data`, an AiMOR factory reset would likely clear it.

## The bundled cable was charge-only

The A-to-C cable in the box powered the frame (the screen came on) but Windows logged **no USB
device at all**, not even an enumeration failure, on two USB-A ports directly on the laptop.
An Android phone on the same cable also did not enumerate, which shows the cable has no data
lines. A different A-to-C data cable showed the frame at once. This matches
[#12](https://github.com/wesbos/photo-frame-dashboard/issues/12) and the
[May recovery-write report](pf1007l-macos-20260529-recovery-boot-write.md).

## Unit report

```text
About model / firmware: PF1007L / YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113
AiMOR version: 6.0.78
Ports (DC jack, or USB-C only): USB-C only
Cable and port that gave USB data (or none): A-to-C data cable, laptop USB-A port, no hub. The bundled cable was charge-only
T3 USB IDs seen / adb devices output: 1f3a:1002 (mass storage + ADB); device, product astar_m86_8723cs, model AEEZO
T3b network ADB result (port 5555): skipped (frame kept off Wi-Fi)
T4 sunxi-fel version output (or skipped): skipped
T5 check-dump stage / chunks (or skipped): skipped
eMMC size in sectors: 30,777,344
Boot partition start sector: 172032 (mmcblk0p6)
Boot image SHA-256 (sector 172032, 31,028 sectors): d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4
Route used and result: none needed; adb shell id returned uid=0(root) (ro.secure=0, ro.adb.secure=0, ro.debuggable=1)
Host OS: Windows 11 (10.0.26200) with Ubuntu on WSL 2; Windows platform-tools 37.0.1 adb.exe called from WSL
First failed step and its exact output: none
```

Fingerprint: `AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260113:eng/test-keys`.
SELinux `Disabled`; `su` present at `/system/xbin/su`.

## Full-eMMC backup over ADB

The whole eMMC (`/dev/block/mmcblk0`, 15,758,000,128 bytes) and both hardware boot areas
(`mmcblk0boot0`/`boot1`, 4 MiB each) were read in 256 MiB chunks with
`adb exec-out '/sbin/busybox dd ... 2>/dev/null'`. For each chunk:

- the byte count had to be exact;
- the host SHA-256 of the streamed bytes had to match a **second, independent read** hashed on
  the frame by `/sbin/busybox sha256sum`;
- a chunk of all `0xCC` filler was rejected.

The chunks were joined, hashed, compressed with gzip and verified by decompressing. It took
about 55 minutes (about 53 s per chunk), with no dropouts. `busybox dd` was used throughout
because stock `dd` can return 0 bytes past 2 GiB
([PF1007L guide](allwinner-a33-pf1007l.md#4-back-up-before-modifying-android)).

## Setup after access

Followed [sections 5 to 7 of the PF1007L guide](allwinner-a33-pf1007l.md#5-install-a-launcher-and-optional-firefox-fallback)
with the pinned APKs listed there:

- Rootless Launcher 3.9.1 and the kiosk installed; Home switched to Rootless. The owner opened
  Android Settings → Apps from Rootless by hand **before** AiMOR was disabled.
- `com.efercro.os.aimor`, `com.yhk.qeota` (`/system/priv-app/frame_ota`, version
  `API_10-usaFrame-P-L_Yes-20240603`) and `com.DeviceTest` disabled. All three showed
  `enabled="2"` in `package-restrictions.xml` within about 4 s and stayed disabled after reboot.
- WebView 44.0.2403.119 replaced with 106.0.5249.126 (APK plus three `lib/arm/*.so`); the stock
  tree, including `oat/arm/webview.odex`, was kept at `/system/homehq-stock-webview`.
  `/system` had 405,820 KiB free beforehand.
- The kiosk loaded the dashboard over `adb reverse tcp:4173`. Kiosk PSS was about 66 MB.
  The owner confirmed touch and page switching on the panel.

Two things to check when scripting the WebView step on this firmware:

- `toybox df -k /system` prints the numbers on a **separate line** from the header. A parser
  that read the header failed its free-space guard (safely, before any change).
- `cp -r` from `/data/local/tmp` produced **world-writable** files and directories
  (`rwxrwxrwx` / `rw-rw-rw-`), and `find ... -exec chmod ... {} +` did not fix them. Set each
  mode with an explicit path (`chmod 0755 /system/app/webview ...`, `chmod 0644 .../webview.apk`)
  and list the tree before rebooting.

## Building the kiosk from WSL

`dashboard/kiosk/build.sh` ran under WSL with Temurin JDK 21, command-line tools, build-tools
36.1.0 and platform android-34 (the script's own note about `d8` from build-tools 34 and newer
JDKs). The WSL install had no `zip`; installing it, or any `zip -qj` equivalent, is needed.
