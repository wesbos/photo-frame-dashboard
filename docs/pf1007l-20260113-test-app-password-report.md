# PF1007L / January 20260113: the test-app password route (T3d) on macOS

One PF1007L on January `20260113` firmware, inspected from an Apple-silicon Mac on 2026-11-09
with platform-tools 37.0.1. The [T3d](pf1007l-start-here.md#t3d-adb-with-no-additional-tools-required)
password route gave root USB ADB on this unit. Before this report the password was confirmed only
on May `20260519` and `20260529` units. This is one unit; it does not establish the password on
every January frame.

## Result

About → tap **Model Number** until **Open test app** asks for a password → `YHK88888888` →
**IS CLOSED** to **is open** gave root USB ADB. No SD card, no FEL, no boot write, and the route
itself used no network. After the switch:

- `adb shell id` returned `uid=0(root)` without `su`
- `persist.sys.usb.config=mass_storage,adb`, `ro.adb.secure=0`, SELinux `Disabled`
- root USB ADB came back after power-cycles

The USB product ID before and after the switch was not recorded.

## Device profile

| Field | Observed result |
| --- | --- |
| Firmware (About) | `YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113` |
| AiMOR | `6.0.78` |
| Factory test app | `com.DeviceTest`, `YHKSign_20250303` |
| Build fingerprint | `AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260113:eng/test-keys` |
| Android | 6.0.1 |
| Display | 1280 x 800, density 160 |
| RAM | `MemTotal: 1026980 kB` |
| eMMC | 30,777,344 sectors (the larger eMMC) |
| Boot partition | `mmcblk0p6`, start 172032, 65,536 sectors |
| Boot SHA-256, first 31,028 sectors | `d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4` (the January hash) |
| Ports (owner) | USB-C only |
| Host | Apple-silicon Mac, platform-tools 37.0.1 |

## USB and power

- The first cable and port showed no `1f3a` device at all.
- Through a bus-powered Realtek "USB2.1 Hub" (`0bda:5411`) the frame browned out: the screen went
  black, it enumerated briefly as FEL (`1f3a:efe8`), then disappeared from USB.
- It booted normally on a wall charger, and from a direct Mac port through a USB-C-to-USB-A
  adapter with an A-to-C data cable. USB ADB worked from the direct port.

This matches the [power notes](pf1007l-start-here.md#the-usb-a-to-usb-c-rule): use a direct port
or a powered hub.

## Network state before lock-down

The frame had already joined the owner's Wi-Fi before this session, and AiMOR had an
`ESTABLISHED` connection to `:7806` when T8 started, as on #119. `wpa_supplicant.conf` also held a
factory network, `3F-WPA3` (#172 reported a factory network too).

## Backup

A full eMMC backup over USB ADB with `/sbin/busybox dd`, 59 chunks of 256 MiB, about 43 minutes.
Every chunk's host SHA-256 matched a second read hashed on the frame, all on the first try. The
gzip readback matched. This is the same method as the
[second marker-route unit](pf1007l-20260113-marker-file-report.md#a-full-backup-over-usb-adb-no-truncation).
The image was read from running Android, so `/data` may have changed between chunks.

## T8 lock-down

Rootless Launcher installed, then `com.efercro.os.aimor`, `com.yhk.qeota` and `com.DeviceTest`
disabled. `package-restrictions.xml` showed `enabled="2"` for all three and kept it across a
power-cycle. All saved Wi-Fi networks, including `3F-WPA3`, were removed. After the power-cycle,
`netstat` showed no connection to `:7806`.

Root USB ADB was still there after the power-cycle that followed disabling `com.DeviceTest`
(the `netstat` check above ran over it), so on this unit the access did not need the test app
to stay enabled.

## After setup

- **WebView 106.0.5249.126**: the swap in
  [section 6 of the PF1007L guide](allwinner-a33-pf1007l.md#6-upgrade-webview-before-using-the-kiosk)
  worked unchanged.
- **Kiosk as Home**: the owner's kiosk app was chosen in Android 6's Home chooser with **Always**.
- **Clock and time zone**: offline, the clock read 1969 and the time zone was `America/Belize`,
  not the `America/New_York` noted for other units.
- **CA roots**: unlike the May unit in
  ["Then set it up"](pf1007l-start-here.md#then-set-it-up), this unit's stock store has
  **GlobalSign Root CA** as `/system/etc/security/cacerts/b0f3e76e.0` (SHA-256
  `EB:D4:10:40:E4:BB:3E:C7:42:C9:E3:81:D3:1E:F2:A4:1A:48:B6:68:5C:96:E7:CE:F3:C1:DF:6C:D4:33:1C:99`,
  expires 2028-01-28). The owner's `*.workers.dev` dashboard (chain WE1 → GTS Root R4, cross-signed
  by GlobalSign Root CA) loaded with no CA changes.

Android names system CA files by OpenSSL's **old-style** subject hash
(`openssl x509 -subject_hash_old`). For GlobalSign Root CA that is `b0f3e76e`; `5ad8a5d6` is the
new-style hash of the same certificate. A check that looks only for `5ad8a5d6.0` will report it
missing even when it is present. Earlier reports that list `5ad8a5d6.0` as absent may be worth
re-checking for `b0f3e76e.0`; this was not tested on those units.

## Summary

```text
About model / firmware: PF1007L / YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113
AiMOR version: 6.0.78
Ports (DC jack, or USB-C only): USB-C only
Cable and port that gave USB data (or none): A-to-C data cable, USB-C-to-USB-A adapter, direct Mac port. First cable/port: no 1f3a device. Bus-powered Realtek USB2.1 hub (0bda:5411): brown-out, brief 1f3a:efe8, then gone
T3 USB IDs seen / adb devices output: product IDs not recorded; after T3d, device, uid=0(root)
T3b network ADB result (port 5555): not recorded
T4 sunxi-fel version output (or skipped): skipped
T5 check-dump stage / chunks (or skipped): skipped
eMMC size in sectors: 30777344
Boot partition start sector: 172032; partition length 65536 sectors
Boot image SHA-256 (sector 172032, 31,028 sectors): d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4
Route used and result: T3d test-app password YHK88888888 -> IS CLOSED to is open -> root USB ADB, no SD card, no boot write; persisted across power-cycles
Host OS: macOS, Apple silicon, platform-tools 37.0.1
First failed step and its exact output: none; full verified eMMC backup over ADB (59 x 256 MiB busybox dd chunks), T8 lock-down, WebView 106, kiosk as Home
```
