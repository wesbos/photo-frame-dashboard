# Frameo 10.1" "102K" (ALONG, Allwinner A33 `astar_xr819`, Android 6.0.1)

Record of one unit, tested on 2026-10-14. Host: macOS 27 on an Apple M2 Pro MacBook Pro.
Observations are kept separate from guesses. The serial, MAC addresses and eMMC CID are left
out; they stay in the owner's ignored `backups/` folder.

**Short version:** USB ADB is on out of the box and connected with no prompt and no key on
file. The shipped `/system/bin/su` gives UID 0 with `su 0 <cmd>`. WebView 106 is preinstalled, so
the [kiosk](../dashboard/kiosk/README.md) runs as is. No boot patch, FEL, SD card or Wi-Fi was
needed, and nothing was written to `/system` or the boot partition.

**Same name, different board.** This frame reports `product:102K model:Digital_Photo_Frame`. The
Rockchip RK3326 [Frameo "Digital Photo Frame 102k" (KJM)](frameo-rk3326-s101.md) has the same
model name and is sold under the same 102k name. Check the fingerprint before you follow either
page.

## Identity

| Item | Observed value |
| --- | --- |
| Listing | [Amazon.ca B088NHSVJN](https://www.amazon.ca/dp/B088NHSVJN), "Frameo 10.1 Inch WiFi Digital Picture Frame, 1280x800 HD IPS Touch Screen Photo Frame Electronic, 32GB Memory, Auto-Rotate, Wall Mountable". Listings may change hardware |
| `adb devices -l` | `product:102K model:Digital_Photo_Frame device:102K` |
| Brand / manufacturer | `ro.product.brand=ALONG`, `ro.product.manufacturer=Allwinner` |
| Firmware | `ro.build.display.id=102K-MS33-HK9365-frameo_V1.29.13_NOPMU_20260113` |
| Fingerprint | `Allwinner/astar_xr819/astar-xr819:6.0.1/MOB30R/20260113:eng/test-keys`. `ro.build.type` is `user` even though the fingerprint says `eng` |
| SoC | Allwinner A33 (`ro.board.platform=astar`, `ro.hardware=sun8i`, `ro.sys.cputype=QuadCore-A33`), Cortex-A7 (`CPU part 0xc07`), 32-bit ARMv7 |
| Board | `ro.product.board=exdroid` |
| Kernel | Linux 3.4.39, `#109 SMP PREEMPT`, built 2026-01-13 |
| Android | 6.0.1, API 23, security patch 2018-08-05 |
| Display / GPU | 1280x800, density 160, `ro.sf.rotation=90`. SurfaceFlinger: `ARM, Mali-400 MP, OpenGL ES 2.0` |
| RAM / swap | 1,027,036 kB; zram swap 327,676 kB |
| Storage | eMMC `mmcblk0`, 61,079,552 sectors (30,539,776 KiB); `/data` 26.7 GB |
| Wi-Fi | `xradio_wlan` / `xradio_core` modules (XR819, as the platform name says). Never used: the frame was never put on a network |
| Power | No `/sys/class/power_supply` entries. `dumpsys battery`: AC powered, no battery present. The build name says `NOPMU` |
| Sensors / input | `mir3da` accelerometer, SoC temperature sensor, `gslX680new` touch. USB Ethernet modules (`asix`, `cdc_ether`, `mcs7830`, `qf9700`) are loaded; not tested |
| Frameo | `net.frameo.frame` v1.29.13 (60080), in `/system/priv-app/Manufacturertest` |
| WebView | `com.android.webview` 106.0.5249.126 in `/system/app/webview` |
| SELinux | Permissive |
| Time zone | `ro.frameo.default.timezone` and `persist.sys.timezone` are `America/New_York` in `/system/build.prop` |

### Closest relatives in this repo

- [Uhale 114KZ](uhale-114kz.md): the same `astar_xr819` fingerprint family and `HK9365` in the
  firmware string. That unit had no usable USB ADB and needed a boot patch.
- [Pastigio / SOMY ZC002](pastigio-zc002.md): the same `astar_xr819` platform, and `MS33` in this
  firmware string (the Pastigio PCB is `MS33-V2.0`). The partition starts below are the same as
  the SOMY ZC002's, through `/data` at sector 4268032. The kernel size (10,165,848 bytes) and the
  stock `sepolicy` SHA-256 (`e538aed0f5a5b93935b897d848ec75477ee5eb8f5bcfd42ff16ce5579ce01e49`)
  match the Pastigio's stock values. `/sbin/adbd` does not (see [Boot image](#boot-image)), and
  ZC002 units stay `unauthorized` over USB while this one doesn't.

Guess, not verified: the ADB difference from the ZC002 is in this build's `adbd`.

## USB

| Host side | Cable | Result |
| --- | --- | --- |
| Mac, first attempt | Not recorded | Nothing enumerated |
| USB-A port on a USB hub on the Mac | USB-A to USB-C | Enumerates as `1f3a:1001`, manufacturer `USB Developer`, product `Android`, 480 Mb/s. `adb devices` showed `device` at once |

The owner replugged between the two attempts. What changed was not recorded, so this unit does
not show whether USB-C to USB-C fails here. The USB-A to USB-C cable through a hub is the one that
worked.

## ADB

- `/system/build.prop`: `persist.sys.usb.config=adb`, `ro.adb.secure=1`,
  `persist.service.adb.enable=1`. `/default.prop` in the boot ramdisk: `ro.secure=1`,
  `ro.debuggable=0`, `persist.sys.usb.config=none`. At runtime `sys.usb.config=adb` and
  `sys.usb.state=adb`; `settings get global adb_enabled` is `1`.
- `adbd` runs as `shell`, context `u:r:adbd:s0`. `adb shell id` is UID 2000. `adb root` was not
  tried.
- **No ADB key is on file.** There is no `/adb_keys` in the boot ramdisk, and
  `/data/misc/adb/` exists (`system:shell`, mode `2750`) but is empty: no `adb_keys` file.
- `com.android.systemui` ships disabled (listed by `pm list packages -d`; nothing in this session
  disabled it), so there is no status or navigation bar and nowhere for an "Allow USB debugging"
  prompt to appear.
  `dumpsys usb` prints no "USB Debugging State" section.
- Even so, the Mac got `device` at once, and again after a frame reboot, with no key stored
  anywhere. **ADB on this unit appears to skip the key check.** Not tested with a second computer.
  Assume any computer the frame is plugged into gets a root shell.
- No network ADB listener: `service.adb.tcp.port` is empty, and `netstat -ltn` shows no `5555`
  (only the `adb reverse` port, see below). The frame was never on Wi-Fi, so ADB over the network
  is untested.
- The frame booted to Frameo's first-run language screen. Frameo's own ADB toggle was never
  needed or tried.

## Root

- `/system/bin/su` is setuid root (`-rwsr-sr-x root root`, 17,980 bytes). There is no
  `/system/xbin/su` and no `daemonsu`.
- `adb shell su 0 id` gives `uid=0(root)` with context `u:r:shell:s0`. `su -c id` fails with
  `invalid uid/gid '-c'`, so use `su 0 <cmd>` rather than the `su -c` check in the README's phase
  map.
- `su 0` keeps only `CAP_SETUID` and `CAP_SETGID` (`CapBnd: ffffffe0000000c0`, the same bounding
  set as `adbd`), as on the [second Pastigio unit](pastigio-zc002.md#su-0-from-adb-has-no-capabilities)
  and the [Uhale 114KZ](uhale-114kz.md#uid-0-does-not-provide-all-root-capabilities). Root can't
  open files it doesn't own:
  - `su 0 dd` of `misc` (`system:system`, `brw-rw----`) and `frp` (`system:system`, `brw-------`)
    gives `Permission denied`. SELinux is permissive, so this is file ownership, not SELinux.
    `su 1000 dd` (UID `system`) reads both.
  - `su 0 ls /data/misc/adb` gives `Permission denied`; the plain shell user can list it through
    the `shell` group.
- `su 0 pm disable` works. Remounting `/system` read-write was not tried.

`su` is setuid with no manager app and no prompt, so treat every app on this frame as if it has root.

## Partition table

eMMC `mmcblk0`, 512-byte sectors, from `/sys/block/mmcblk0/mmcblk0p*/start` and
`/dev/block/by-name`. `/data` ends exactly at the end of the eMMC.

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
| p1 | UDISK (`/data`, ext4) | 4268032 | 56811520 |

## Boot image

Stock, read before any change and never written.

| Item | Value |
| --- | --- |
| Boot partition (16 MiB) SHA-256 | `c7e99c1d2f41c37320c1ab04baf2784ce398ece39e500faa6b48ee7e2826d5bc` |
| Boot partition MD5 | `a87ed8b311a24e5dee5f7894ca954ac0`, the same as `su 0 md5sum /dev/block/by-name/boot` on the frame |
| Header | `ANDROID!`, page 2048, kernel 10,165,848 bytes, ramdisk 4,734,754 bytes, no second stage, cmdline `vmalloc=384M` |
| Android image (first 14,903,296 bytes) SHA-256 | `8af0c638d514d633e00c1bd9c274dd6c9c07690697bd2d574c32a849e3536b84`. The rest of the partition is zeros |
| `/sbin/adbd` SHA-256 | `aad459e841ce03e7eae0add799ac24089c06d786c20fec1fe9148cc2f61b38e3` (the ZC002's is `b5ec816b…`) |
| `sepolicy` SHA-256 | `e538aed0f5a5b93935b897d848ec75477ee5eb8f5bcfd42ff16ce5579ce01e49`, the same as the ZC002 stock |

In `init.rc`, `adbd` is `disabled` and started by the `sys.usb.config` triggers in
`init.sun8i.usb.rc`.

## Backup

Every partition except userdata and cache was read as root over ADB:

```sh
adb exec-out "su 0 dd if=/dev/block/by-name/<name> bs=1048576" > <name>.img
```

MD5 of boot, bootloader and env matched `su 0 md5sum` on the frame. `misc` and `frp` were missed
(see [Root](#root)); `su 1000 dd` reads them. This is MD5 on three partitions, not the
README's full [backup rule](../README.md#rules-we-learned-the-hard-way). Nothing was written that
needs it: all changes below are in `/data`.

## Software of interest

| Package | Location | Notes |
| --- | --- | --- |
| `net.frameo.frame` v1.29.13 | `/system/priv-app/Manufacturertest` | Frameo, and the only **HOME** activity out of the box |
| `com.adups.fota` 5.28 | `/system/app/FotaUpdate` | Adups FOTA. `/system/build.prop` has `ro.fota.oem=alongA33_6.0`, `ro.fota.device=102K`, `ro.fota.version` = the firmware string |
| `com.along.table` V2.2.8 | `/system/app/AlongTestApk` | Vendor test app |
| `com.along.factorytest` | `/system/app/AlongFactoryTest` | Factory test |
| `com.android.agingtest` | `/system/priv-app/AgingTest` | Aging test |
| `com.softwinner.dragonfire`, `dragonaging`, `dragonphone` | `/system/app` | Allwinner factory test apps |
| `com.softwinner.fireplayer` 2.3.10.33 | `/data/app` | Video player. Guess: copied in on first boot from `/system/preinstall/VideoPlayer` |
| `com.android.systemui` | `/system/priv-app/SystemUI` | Present, disabled out of the box |
| `com.android.inputmethod.latin`, `jp.co.omronsoft.openwnn` | `/system/app` | Keyboards |

## What was set up (approved writes, all in `/data`)

1. Built `dashboard/kiosk` with `build.sh` on macOS (Homebrew `openjdk@17`, `android-commandlinetools`
   with build-tools 34.0.0 and platform 34) and installed it with `adb install -r`. It built and
   installed without problems. This owner's copy has a few local changes (default URL, label, and
   the keyboard flags below).
2. Saved the URL with `am start -n com.wesbos.homehq/.MainActivity --es url <url> --ez home true`,
   then `su 0 pm disable net.frameo.frame` and `su 0 pm disable com.adups.fota`, before the
   frame was ever online. With Frameo disabled the kiosk is the only Home app, since Android 6 has
   no `cmd package set-home-activity`. After a reboot the frame starts straight into the kiosk.
3. `settings put global stay_on_while_plugged_in 7`.

The way back on this unit is USB ADB with `su 0`, which is on from `/system/build.prop`. A check
by hand that the kiosk menu reaches Android Settings was not recorded.

### No Wi-Fi: the page comes over the USB cable

The page is served on the Mac's loopback (`127.0.0.1:7681`) and reaches the frame through
`adb reverse tcp:7681 tcp:7681`. This works. A replug, a frame reboot or an `adb kill-server`
drops the mapping, so a loop on the Mac re-applies it.

### Kiosk notes

- The page is a [ttyd](https://github.com/tsl0922/ttyd) / xterm.js terminal. xterm.js's canvas
  renderer drew garbled glyph fragments on this frame; the DOM renderer
  (`-t rendererType=dom`) is fine. Guess, not verified: the Mali-400 GPU.
- xterm.js focuses a hidden textarea, so the LatinIME keyboard popped up over the dashboard.
  Adding `WindowManager.LayoutParams.FLAG_ALT_FOCUSABLE_IM` to the kiosk window plus
  `setSoftInputMode(SOFT_INPUT_STATE_ALWAYS_HIDDEN)` fixed it. The flag alone left a keyboard
  raised by the previous window on screen. This change is in the owner's local kiosk build, not
  in this repo.

## Undo

| Change | Undo |
| --- | --- |
| Frameo and FOTA disabled | `adb shell su 0 pm enable net.frameo.frame`, `adb shell su 0 pm enable com.adups.fota` |
| Kiosk as Home | `adb shell am start -n com.wesbos.homehq/.MainActivity --ez home false`, or `adb uninstall com.wesbos.homehq` |
| Screen always on | `adb shell settings put global stay_on_while_plugged_in 0` (the value before the change was not recorded) |
| Page over USB | `adb reverse --remove tcp:7681`, and stop the loop on the Mac |

Nothing was written to `/system` or the boot partition.

## Not tested

- A second computer with a fresh ADB key, to confirm there is no key check.
- Wi-Fi, network ADB, and what Frameo or Adups do once online.
- A USB-C to USB-C cable, and why the first plug-in enumerated nothing.
- Remounting `/system` with `su 0`, and whether `su` from an app keeps full capabilities.
- How often this listing ships this board. A unit with the same ASIN from Amazon México was the
  [KJM RK3326 board](frameo-rk3326-s101.md#second-unit-amazon-méxico).
