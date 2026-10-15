# Frameo 10.1" "101K" (ALONG, Allwinner A33 `astar_xr819`, Android 6.0.1)

Record of one unit, tested on 2026-10-15. Host: macOS 27 on an Apple M4 Mac mini.
Observations are kept separate from guesses. The serial, MAC addresses and eMMC CID are left
out; they stay in the owner's ignored `backups/` and `diagnostics/` folders.

**Short version:** Frameo's About screen lists the hardware as `101k`. ADB Access in Frameo's
Beta Program, then an authorisation prompt over USB. The shipped `/system/bin/su` gives UID 0 with
`su 0 <cmd>`. `setprop persist.adb.tcp.port 5555` as root keeps network ADB on across a power
cycle, so after one USB session the frame was used over Wi-Fi only. WebView 106 is preinstalled.
No boot patch, FEL or SD card was needed, and nothing was written to `/system` or the boot
partition. Adups FOTA and Frameo were then disabled, the kiosk set as Home, and ISRG Root X1 added
to the *user* trust store so WebView 106 accepts current Let's Encrypt chains.

**The hard part was power, not access.** The frame has one USB-C port for both power and data, and
restarted in a loop when powered from the Mac through a USB-C to USB-A adapter. See [USB and
power](#usb-and-power).

## Identity

| Item | Observed value |
| --- | --- |
| Frameo About | Hardware `101k`, Frameo `v1.29.13 (60080)` |
| `adb devices -l` | `product:Digital Photo Frame model:Digital_Photo_Frame device:Digital Photo Frame` |
| Brand / manufacturer | `ro.product.brand=ALONG`, `ro.product.manufacturer=Allwinner` |
| Firmware | `ro.build.display.id=114119_HK9365_SWM0810_frameo_v1.29.13_20260114` |
| Fingerprint | `Allwinner/astar_xr819/astar-xr819:6.0.1/MOB30R/20231010:eng/test-keys`. `ro.build.type` is `user` |
| FOTA identity | `ro.fota.oem=alongA33_6.0`, `ro.fota.platform=AW_A33_6.0`, `ro.fota.device=Digital Photo Frame`, `ro.fota.version` = the firmware string |
| SoC | Allwinner A33 (`ro.board.platform=astar`, `ro.hardware=sun8i`, `ro.sys.cputype=QuadCore-A33`), Cortex-A7 (`CPU part 0xc07`), 32-bit ARMv7 |
| Board | `ro.product.board=exdroid` |
| Kernel | Linux 3.4.39, `#398 SMP PREEMPT`, built 2026-01-14 |
| Android | 6.0.1, API 23, security patch 2016-07-05 |
| Display / GPU | 1280x800, density 160, `ro.sf.rotation=90`. `ARM, Mali-400 MP, OpenGL ES 2.0` |
| RAM | 1,026,980 kB |
| Storage | eMMC `mmcblk0`, 60,620,800 sectors; `/data` 26.4 GB |
| Wi-Fi | XR819 (`xradio_wlan`, `xradio_core`, `xradio_mac` modules). Round-trip times of 100–470 ms on a home network; network ADB reads ran at roughly 200 KB/s |
| Power | `dumpsys battery`: AC powered, no battery present |
| Sensors / input | `mir3da` and `mc32x0` accelerometer modules, `gslX680new` touch. USB Ethernet modules (`asix`, `cdc_ether`, `mcs7830`, `qf9700`) are loaded; not tested |
| Frameo | `net.frameo.frame` v1.29.13, in `/system/priv-app/Manufacturertest` |
| Vendor updater | `com.adups.fota` |
| WebView | `com.android.webview` 106.0.5249.126 |
| SELinux | Permissive |
| Time zone | `ro.frameo.default.timezone=America/New_York`; `persist.sys.timezone` became `Europe/London` after Frameo setup |

### Closest relatives in this repo

- Frameo 114K, in open PR [wesbos/photo-frame-dashboard#122](https://github.com/wesbos/photo-frame-dashboard/pull/122)
  (not merged when this was written): **the same firmware string and fingerprint.** That unit's eMMC
  is larger (61,341,696 sectors), it showed no ADB prompt (this one did), and it needed a powered hub
  for USB. Its findings on `su` capabilities, `pm disable` persistence and the Wi-Fi key check
  probably apply here too; they were not all repeated on this unit.
- [Uhale 114KZ](uhale-114kz.md): the firmware string starts with the same
  `114119_HK9365_..._SWM0810` and has the same date (`20260114`), with Uhale in place of Frameo.
  That unit was unstable on USB data (a suspected power limit, as here) and needed a boot ramdisk
  patch for network ADB. On this unit, root `setprop` was enough.
- [Frameo 102K (A33)](frameo-102k-a33.md): the same `astar_xr819` fingerprint family, brand, Frameo
  version, WebView and `su` behaviour. Its firmware string starts with `102K-MS33-HK9365`. The
  partition layout matches except for the size of `UDISK`.

## USB and power

- One USB-C port (power and data) and one USB-A host port. The USB-A port is a host port and can't
  be used to reach ADB.
- **USB-C to USB-C (Mac mini to frame): no power and no data.** Guess: the frame's USB-C port has no
  CC pull-down resistors, so a USB-C source never turns on VBUS.
- **USB-A to USB-C cable through a USB-C to USB-A adapter on the Mac mini: data works, but the
  frame flickered and restarted in a loop.** `adb devices` showed `unauthorized` in the short
  windows when it was up.
- A Steam Deck dock with no charger on its PD input made it worse (the frame stayed up for less
  time).
- What worked: a different USB-A to USB-C cable, through the same adapter on the Mac. The frame's
  Wi-Fi was off at the time. It stayed up long enough to authorise the host key and run the
  commands below. Guess: the second cable dropped less voltage.
- After `persist.adb.tcp.port` was set, USB was no longer needed: the frame runs from its own
  adapter and is reached over Wi-Fi.

## ADB

- Frameo → Settings → About → Beta Program → ADB Access turns on USB ADB.
- `ro.adb.secure=1`. The "Allow USB debugging?" prompt appeared on screen once the frame stayed
  powered long enough; "Always allow" was ticked.
- Before any change, `service.adb.tcp.port` and `persist.adb.tcp.port` were empty and port 5555
  was closed on the network (`adb connect` gave `Connection refused`).
- `su 0 setprop persist.adb.tcp.port 5555`, then `adb tcpip 5555`. `adb connect <frame-ip>:5555`
  worked at once.
- **After a power cycle on the frame's own adapter with no USB** (uptime 79 s),
  `service.adb.tcp.port` was empty, `persist.adb.tcp.port` was `5555`, and `adb connect` worked. So
  `adbd` on this build reads `persist.adb.tcp.port` at start.
- Network ADB still checks the host key (`ro.adb.secure=1`); only the authorised computer was
  tested. Guess: other computers get the prompt, which this frame can show.
- `persist.sys.usb.config=mtp,adb`; at runtime `sys.usb.config=adb`.

## Root

- `/system/bin/su` is setuid root (`-rwsr-sr-x root root`, 17,920 bytes). No `/system/xbin/su`.
- `su 0 id` gives `uid=0(root)`, context `u:r:shell:s0`, over USB and over network ADB.
  `su -c id` fails with `invalid uid/gid '-c'`.
- As on the [102K](frameo-102k-a33.md#root), use `su 1000` to read `misc` and `frp`, which are
  owned by `system`.

`su` is setuid with no manager app and no prompt, so treat every app on this frame as if it has root.

## Partition table

eMMC `mmcblk0`, 512-byte sectors, from `/sys/block/mmcblk0/mmcblk0p*/{start,size}` and
`/dev/block/by-name`.

| Partition | Name | Start | Size (sectors) |
| --- | --- | --- | --- |
| p2 | bootloader | 73728 | 65536 |
| p5 | env | 139264 | 32768 |
| p6 | boot | 172032 | 32768 |
| p7 | system | 204800 | 2097152 |
| p8 | misc | 2301952 | 32768 |
| p9 | recovery | 2334720 | 65536 |
| p10 | cache | 2400256 | 1572864 |
| p11 | metadata | 3973120 | 32768 |
| p12 | private | 4005888 | 32768 |
| p13 | frp | 4038656 | 1024 |
| p14 | empty | 4039680 | 31744 |
| p15 | alog | 4071424 | 163840 |
| p16 | media_data | 4235264 | 32768 |
| p1 | UDISK (`/data`) | 4268032 | 56352768 |

All rows except `UDISK` match the [102K](frameo-102k-a33.md#partition-table). This unit's eMMC is
smaller (60,620,800 sectors), and `UDISK` is shorter by the difference.

## Boot image

Stock, read before any change and never written. **Identical to the 114K's** in PR #122.

| Item | Value |
| --- | --- |
| Header | `ANDROID!`, page 2048, kernel 10,221,792 bytes, ramdisk 4,650,744 bytes, no second stage |
| Android image (first 14,876,672 bytes) SHA-256 | `4d503349ea948ebfd91573c1de2d646b82c63ab403eac590c420e3125d01bb1b`. The rest of the partition is zeros |
| Boot partition (16 MiB) SHA-256 | `85fdb88071e045e053c44600bd922119945d3c222f0daa1c9f2f1c341d4ec023` |

## Backup

Every partition except `UDISK` and `cache`, plus raw eMMC from sector 0 for 36 MiB, was read over
network ADB (about 200–400 KB/s; 1.25 GiB took about an hour):

```sh
adb exec-out "su 0 dd if=/dev/block/by-name/<name> bs=1048576 2>/dev/null" > <name>.img   # su 1000 for misc and frp
```

Every image passed: exact size (`/sys/block/mmcblk0/<part>/size` × 512), an MD5 match with
`md5sum` on the frame, no 1 MiB block that is all `0xCC`, fresh re-reads of `boot`, `bootloader`
and `env` with the same SHA-256, and gzip copies that pass `gzip -t` and decompress to the same
SHA-256. No read needed a retry.

A first attempt stopped partway through `bootloader` when the read was interrupted; the partial file
was deleted. A short read is caught by the size check.

## Vendor apps

- `su 0 pm disable com.adups.fota` and later `su 0 pm disable net.frameo.frame`. Both show
  `enabled="2" enabledCaller="shell:0"` in `/data/system/users/0/package-restrictions.xml` (read with
  `su 1000`). Both stayed disabled across two reboots, and four hours after the last one neither
  had a process or an alarm (`ps`, `dumpsys alarm`). The 114K in PR #122 lost its first `pm disable`
  to an early reboot; checking that file before rebooting avoids that.
- Before Frameo was disabled it kept running behind the kiosk: it set `screen_brightness` back to
  15 and held its own 22:00 sleep-schedule alarm (`StandbyBroadcastReceiver`).
- SystemUI ships disabled (no navigation bar).

## Kiosk as Home

The repo's [kiosk](../dashboard/kiosk/README.md) installed and ran with the owner's URL. With
Frameo still enabled, pressing Home showed a chooser between Frameo and Home HQ; the owner picked
Home HQ and **Always**. After Frameo was disabled, Home still opened Home HQ, and after a power
cycle the dashboard was on screen about 58 s after boot. The navigation service needed
`pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS` and the owner enabling it
in Accessibility; the owner checked by hand that its Dashboard button returns from Android Settings.

## HTTPS: Let's Encrypt root in the user store

The dashboard is served from `workers.dev` and fetches ESPN over HTTPS. WebView 106 rejected
both with `net_error -202` (`ERR_CERT_AUTHORITY_INVALID`): the `workers.dev` chain was
YE1 → Root YE → ISRG Root X2 → ISRG Root X1, and Android 6's store has no ISRG root.

The [BIUFRAME guide](biuframe-setup-guide.md) adds the roots to `/system`. Here they were added to
the **user** store instead, which needs no `/system` write.

| Item | Value |
| --- | --- |
| Source | <https://letsencrypt.org/certs/isrgrootx1.pem> |
| SHA-256 fingerprint | `96:BC:EC:06:26:49:76:F3:74:60:77:9A:CF:28:C5:A7:CF:E8:A3:C0:AA:E1:1A:8F:FC:EE:05:C0:BD:DF:08:C6` (matches letsencrypt.org and the macOS system store) |
| File name | `6187b673.0` (`openssl x509 -noout -subject_hash_old`) |
| Path | `/data/misc/user/0/cacerts-added/6187b673.0`, `system:system 0644` |
| Folder | `cacerts-added` did not exist; created as `system`, `0755` |

`/data/misc/user/0` belongs to `system`, so `su 1000` is used for it (`su 0` gets `Permission
denied` listing the folder). Apps that target API 23 or lower trust the user store by default, and
the repo's kiosk targets 23 (`dashboard/kiosk/build.sh`). After a kiosk force-stop the dashboard
loaded with no X509 errors in `logcat`. Undo: `su 1000 rm` the file (and `rmdir` the folder), then
force-stop the kiosk. ISRG Root X2 was not added; X1 was enough for these sites.

## Backlight

Android's brightness setting can't go below 20 of 255 here, so the panel is never dark. The sunxi
display driver's `/sys/class/disp/disp/attr/lcdbl` (`root:root 0664`) can be written as root:

```sh
adb shell su 0 sh -c "'echo 0 > /sys/class/disp/disp/attr/lcdbl'"     # backlight off
adb shell su 0 sh -c "'echo 255 > /sys/class/disp/disp/attr/lcdbl'"   # back on
```

`0` turns the backlight fully off while the touch screen keeps working, so a tap can turn it back
on. The owner's local kiosk build uses this for a night mode (not part of this repo). Guess, not
verified: Android doesn't read `lcdbl` back, so the next brightness change from Android overwrites it.

## Changes made (approved, all in `/data`)

| Change | Undo |
| --- | --- |
| `su 0 setprop persist.adb.tcp.port 5555` | `su 0 setprop persist.adb.tcp.port ""`, then reboot |
| `su 0 pm disable com.adups.fota` | `su 0 pm enable com.adups.fota` |
| Kiosk installed, set as Home (chooser, **Always**) | `adb uninstall com.wesbos.homehq` |
| `pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS` | `pm revoke` the same |
| `settings put system screen_brightness 255` (was 15) | Set it back in Settings |
| ISRG Root X1 in `/data/misc/user/0/cacerts-added/6187b673.0` | `su 1000 rm` it, force-stop the kiosk |
| `su 0 pm disable net.frameo.frame` | `su 0 pm enable net.frameo.frame` (Frameo's sleep schedule and brightness come back) |

`adb tcpip 5555` only lasts until the next reboot.

## Not tested

- Whether `su 0` here lacks `CAP_SYS_ADMIN`/`CAP_SYS_TIME` as on the 102K and 114K.
- Whether another computer can connect over the network without the prompt.
- Whether a powered hub fixes the USB restarts (none was available).
