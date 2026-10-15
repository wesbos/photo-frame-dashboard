# Frameo "Digital Photo Frame 114K" (Allwinner A33 `astar_xr819`, Android 6.0.1)

Record of one unit, tested on 2026-10-14. Host: macOS 27 on Apple silicon. Observations are kept
separate from guesses. The serial, MAC address and IP address are left out.

**Short version:** USB ADB works, but only through a powered USB hub. The shipped `/system/bin/su`
gives UID 0 with `su 0 <cmd>`, but without the capabilities to set the clock or remount `/system`.
WebView 106 is preinstalled, so the [kiosk](../dashboard/kiosk/README.md) runs as is.
`setprop persist.adb.tcp.port 5555` keeps ADB on Wi-Fi across reboots, and the key check is
enforced over Wi-Fi. Nothing was written to `/system` or the boot partition.

**Same board family as the [Frameo 102K](frameo-102k-a33.md) and the [Uhale 114KZ](uhale-114kz.md).**
The fingerprint (`astar_xr819`, build date `20231010`) is identical to the Uhale 114KZ's, and the
firmware string shares its `114119_HK9365_SWM0810` prefix. The brand property is `ALONG`, as on the
102K, and the partition starts match the 102K's. The box and label name the maker as Shenzhen
Kejinming; no build property mentions Kejinming. Check the fingerprint before following any of these pages.

## Identity

| Item | Observed value |
| --- | --- |
| Sold as | Frameo "Digital Photo Frame 114K" (Shenzhen Kejinming). Listing not recorded |
| `adb devices -l` | `product:Digital Photo Frame model:Digital_Photo_Frame device:Digital Photo Frame` |
| Brand / manufacturer | `ro.product.brand=ALONG`, `ro.product.manufacturer=Allwinner` |
| Firmware | `ro.build.display.id=114119_HK9365_SWM0810_frameo_v1.29.13_20260114` |
| Fingerprint | `Allwinner/astar_xr819/astar-xr819:6.0.1/MOB30R/20231010:eng/test-keys`. `ro.build.type` is `user` |
| SoC | Allwinner A33 (`ro.board.platform=astar`, `ro.hardware=sun8i`), board `exdroid` |
| Kernel | Linux 3.4.39, `#398 SMP PREEMPT`, built 2026-01-14 |
| Android | 6.0.1, security patch 2016-07-05 |
| Display | 1280x800, density 160, `ro.sf.rotation=90` |
| RAM | 1,026,980 kB. `ro.config.low_ram=true` and `ro.config.512m=true` are set anyway (effect not tested; there is no `/system/etc/lowmem_package_filter.xml`) |
| eMMC | 61,341,696 sectors (the same count as the Uhale 114KZ); `/data` 26.8 GB |
| Wi-Fi | XR819 (`xradio_wlan`, `xradio_core`). Works |
| Frameo | `net.frameo.frame` v1.29.13 (60080), in `/system/priv-app/Manufacturertest` |
| WebView | `com.android.webview` 106.0.5249.126 in `/system/app/webview` |
| SELinux | Permissive |
| Time zone | `persist.sys.timezone` and `ro.frameo.default.timezone` are `America/New_York` in `/system/build.prop` |

## Hardware

- **Sensors:** `mir3da` accelerometer (used for auto-rotate) and a "Temperature sensor" that is
  the SoC thermal sensor (`sunxi-ths`). No light, proximity or motion sensor.
- **Cameras:** none. The camera HAL (`V4L2Camera Module`) loads but reports 0 devices, and there is
  no `/dev/video*`.
- **Input:** `gslX680` touch, `axp22-supplyer` (power key), `headset`, `sunxi-ths`, `mir3da`.
- **Power:** no battery (`dumpsys battery`: present false). **No RTC battery:** after a power cut the
  clock starts at 1969-12-31. The SoC RTC (`sunxi-rtc`) keeps time across a warm `adb reboot`.
- USB Ethernet modules are loaded (`asix`, `cdc_ether`, `mcs7830`, `qf9700`); not tested.

## USB

| Host side | Cable | Result |
| --- | --- | --- |
| Mac USB port directly | USB-A to USB-C | The Mac can't power the frame; no usable connection |
| Anker 332 USB-C hub, with a charger on its PD-IN port | USB-A to USB-C data cable | Enumerates as `1f3a:1001`. `adb devices` shows `device` |

`dumpsys battery` reports `USB powered: true` through the hub. Guess, not verified: like the
[Uhale 114KZ](uhale-114kz.md#usb-configuration-and-power-problem), this board draws more than a
bare Mac port gives it, and the hub's charger fills the gap.

USB ADB was turned on with Frameo's own toggle: Settings → About → Beta Program → ADB Access.
With the hub setup above, the Mac connected at once, with no prompt on screen (SystemUI ships
disabled, so no prompt could appear). Afterwards `/data/misc/adb/adb_keys` held exactly one key,
the Mac's. Guess, not verified: Frameo's toggle, or this build's `adbd`, accepts the first USB host
and saves its key. A second computer over USB was not tried; over Wi-Fi a new key is refused (see
[Persistent ADB over Wi-Fi](#persistent-adb-over-wi-fi)).

## ADB and root

- `/system/build.prop`: `ro.adb.secure=1`, `persist.sys.usb.config=adb,mtp`,
  `persist.service.adb.enable=1`. `/default.prop`: `ro.secure=1`, `ro.debuggable=0`.
  At runtime `persist.sys.usb.config` read `mtp,adb` and `sys.usb.config=adb`.
- `adbd` runs as `shell`. `adb root` is blocked. `service.adb.tcp.port` and
  `persist.adb.tcp.port` are empty out of the box, so nothing listens on 5555.
  `adb tcpip 5555` works until the next reboot.
- `/system/bin/su` is setuid root (17,920 bytes). `su 0 id` gives `uid=0(root)`, context `u:r:shell:s0`.
  `su -c` is not supported.
- **`su 0` keeps only `CAP_SETUID` and `CAP_SETGID`** (`CapEff: ffffffe0000000c0`), as on the
  [102K](frameo-102k-a33.md#root) and the [Uhale 114KZ](uhale-114kz.md#uid-0-does-not-provide-all-root-capabilities). In practice:
  - `date -s` can't work (no `CAP_SYS_TIME`), and `/system` can't be remounted (no `CAP_SYS_ADMIN`).
  - Root can't read files it doesn't own. `su 0 dd` of `misc` and `frp` fails; `su 1000 dd` reads them.
    `su 0` also can't read `/data/system/users/0/package-restrictions.xml`; `su 1000` can.
  - `su 0 pm disable` and `su 0 setprop persist.*` work.

### Persistent ADB over Wi-Fi

```sh
adb shell su 0 setprop persist.adb.tcp.port 5555     # undo: setprop persist.adb.tcp.port "" and reboot
```

The value is stored in `/data/property/persist.adb.tcp.port`. After an `adb reboot` and after a
30-second power cut, `adb connect <frame-ip>:5555` gave `device` without `adb tcpip`, about 50 s
after power-on. `adbd` listens on `0.0.0.0:5555` and USB ADB keeps working.

**The key check is enforced over Wi-Fi.** A second adb server with a freshly generated key that the
frame had never seen got `failed to authenticate` / `unauthorized`. The authorized Mac connected
normally. This differs from the [Joyhong](joyhong-jt101f-i02.md#adb-and-root) and the
[102K](frameo-102k-a33.md#adb), where the key check appeared to be off.

Once, right after a reboot, a Wi-Fi ADB shell failed with `error: closed` while the TCP connection
was established. `adb disconnect` then `adb connect` fixed it.

## Clock

Android's own `NetworkTimeUpdateService` does the job; no boot script is needed. With
`auto_time=1`, it polls about once a minute until it succeeds (the `...NetworkTimeUpdateService.action.POLL`
alarm in `dumpsys alarm`), then every 24 hours. After a power cut, the logs start at `12-31 19:00`, and
`UsageStatsService: Time changed` appeared about 42 s after boot.

On this unit the frame sits behind a firewall that allows only UDP 123 out. Each poll showed up
in conntrack (`su 0 cat /proc/net/nf_conntrack`) as a request to port 123 marked `[UNREPLIED]`,
which showed the frame was trying and the network was dropping it. The cause was the firewall's
rule order (a UniFi zone policy: the block rule had a lower ID than the allow rule, although the
table listed the allow first). After the rules were reordered, the clock synced within a minute.

Notes for frames that can't reach an NTP server:

- `su 0 date -s` won't work here (see [ADB and root](#adb-and-root)). The repo's
  [`frame-timesync.sh`](../scripts/pf1007l-boot/device/frame-timesync.sh) also won't work unchanged:
  this build's toybox `nc` has no `-u` (UDP) option, and there is no `/system/xbin/nc`.
- Guess, not tested: `su 0 service call alarm 2 i64 <epoch-ms>` (AlarmManager `setTime`) should
  work, because the permission check happens in `system_server` and UID 0 passes it.

## Software of interest

| Package | Location | Notes |
| --- | --- | --- |
| `net.frameo.frame` v1.29.13 | `/system/priv-app/Manufacturertest` | Frameo, and the default **HOME** app. No `INSTALL_PACKAGES`. Offline it keeps trying `connect.frameo.biz` and Crashlytics |
| `com.adups.fota` 5.28 | `/system/app/FotaUpdate` | Adups FOTA. Holds `RECOVERY` and `REBOOT`, starts at boot, has an FCM push service. `ro.fota.oem=alongA33_6.0` |
| `com.softwinner.dragonfire` | `/system/app/DragonFire` | Allwinner factory test. Holds `INSTALL_PACKAGES`, `DELETE_PACKAGES` and `REBOOT` |
| `com.softwinner.dragonaging`, `dragonphone`, `com.along.factorytest`, `com.android.agingtest` | `/system/app`, `/system/priv-app` | Factory and aging tests |
| `com.android.launcher` (Launcher2) | `/system/priv-app/Launcher2` | **Not a Home app on this build.** Its `com.android.launcher2.Launcher` intent filter is only `MAIN` + `MONKEY` (no `HOME`), so the kiosk's **Open launcher** falls back to Android Settings |
| `com.android.browser` | `/system/app/Browser` | Stock browser |
| `com.android.systemui` | `/system/priv-app/SystemUI` | Present, disabled out of the box |

## Partition table

eMMC `mmcblk0`, 512-byte sectors, from `/sys/block/mmcblk0/mmcblk0p*/start`. The starts are the same
as the [102K](frameo-102k-a33.md#partition-table)'s, and `/data` is larger, as the eMMC is.

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
| p1 | UDISK (`/data`) | 4268032 | 57073664 |

## Boot image

Stock, read before any change and never written.

| Item | Value |
| --- | --- |
| Header | `ANDROID!`, page 2048, kernel 10,221,792 bytes, ramdisk 4,650,744 bytes, no second stage, empty cmdline |
| Android image (first 14,876,672 bytes) SHA-256 | `4d503349ea948ebfd91573c1de2d646b82c63ab403eac590c420e3125d01bb1b`. The rest of the partition is zeros |
| Boot partition (16 MiB) SHA-256 | `85fdb88071e045e053c44600bd922119945d3c222f0daa1c9f2f1c341d4ec023` |
| 31,028 sectors from 172032 SHA-256 | `d4dd5fdb9b673a03f0545543937832019349e2b00405db9b046747d3416213f9` |

## Backup

Every partition except `UDISK` and `cache`, plus raw eMMC sectors 0 to 73,727, was read over USB ADB:

```sh
adb exec-out "su 0 dd if=/dev/block/by-name/<name> bs=1048576" > <name>.img   # su 1000 for misc and frp
```

Every image's MD5 matched `md5sum` on the frame. Fresh re-reads of `boot`, `bootloader` and the first
64 MiB of `system` matched, and no 1 MiB block is all `0xCC`. This is not the README's full eMMC backup:
nothing written in this session needed it, because all changes are in `/data`.

## What was set up (approved writes, all in `/data`)

| Step | Command | Undo |
| --- | --- | --- |
| Persistent Wi-Fi ADB | `su 0 setprop persist.adb.tcp.port 5555` | `su 0 setprop persist.adb.tcp.port ""`, reboot |
| Disable the vendor updater | `su 0 pm disable com.adups.fota` | `su 0 pm enable com.adups.fota` |
| Install the kiosk alongside Frameo | `adb install homehq.apk` (only change: `DEFAULT_URL`) | `adb uninstall com.wesbos.homehq` |
| Navigation buttons | Owner enabled Settings → Accessibility → Home HQ navigation; `pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS` | `pm revoke` the same, turn the service off |
| Offer the kiosk as Home | `am start -n com.wesbos.homehq/.MainActivity --ez home true` | the same with `--ez home false` |
| Disable Frameo | `su 0 pm disable net.frameo.frame` | `su 0 pm enable net.frameo.frame` |

**`pm disable` was lost on the first try.** The package showed `enabled=2` and its process stopped,
but after an `adb reboot` it was enabled and running again, with no entry for it in
`package-restrictions.xml`. The second time, the entry was checked on disk before rebooting
(`su 1000 grep com.adups.fota /data/system/users/0/package-restrictions.xml` →
`enabled="2" enabledCaller="shell:0"`), and it survived the reboot. Guess, not verified: the first
reboot came before PackageManager's delayed write of that file.

### Kiosk

The kiosk was built with `kiosk/build.sh` (Homebrew `openjdk@17`, `android-commandlinetools`,
build-tools 34.0.0, platform 34) without problems. `test-navigation.py` passed. Installing it did not
make it a Home app.

The dashboard is a Home Assistant page over plain HTTP on the LAN, so the 2016 certificate store
did not matter. Home Assistant's login page and dashboard render in WebView 106. With "Keep me
logged in" checked, the login survived `am force-stop com.wesbos.homehq` and a relaunch.
`screencap` captures the WebView. Chromium logs `eglChooseConfig failed with error EGL_BAD_ATTRIBUTE`
at start, with no visible effect.

The owner checked by hand on the panel that the two-finger hold opens the Home HQ menu with
**Open launcher**, **Android settings**, **Wi-Fi settings** and **Reload dashboard**.

The floating **Back** and **Dashboard** buttons from the navigation service worked in Android Settings
(checked by the owner on the panel).

At the first launch the screen was off. Guess, not verified: Frameo's night sleep schedule
(`net.frameo.frame/.feature.sleep_schedule.StandbyBroadcastReceiver` holds an alarm).
`input keyevent KEYCODE_WAKEUP` turned it on.

### Kiosk as Home, Frameo disabled

Out of the box there is no saved Home preference, yet Frameo starts as Home with no chooser:
Frameo was the only Home app, because Launcher2 has no `HOME` category here (see
[Software of interest](#software-of-interest)). Enabling the kiosk's Home alias while Frameo was
enabled changed nothing visible. After `pm disable net.frameo.frame` (checked on disk in
`package-restrictions.xml` first), the Home key went straight to `com.wesbos.homehq/.Home`. No
chooser appeared and no preferred activity was saved, because Home HQ was the only Home app.

After a 30-second power cut the frame booted into the dashboard on its own. Home HQ started about
30 s after power-on, its first loads failed with `ERR_INTERNET_DISCONNECTED`, it retried every 5 s,
logged `Wi-Fi connected, retrying now` about 15 s later, and then showed the dashboard, still logged
in. NTP set the clock, Wi-Fi ADB came back and the navigation service was bound.

## Not tested

- Whether `ro.config.low_ram=true` kills the kiosk when it is in the background.
- Whether a second computer is accepted over USB without a prompt (see [USB](#usb)).
- `service call alarm 2` as a way to set the clock without NTP.
- USB-C to USB-C, and USB Ethernet.
