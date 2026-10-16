# XORO CPF 10PF 10.1" (Allwinner A133, Android 10, Uhale)

A record of **one unit**, read over ADB on 2026-10-14 and set up between 2026-10-14 and 2026-10-16.
Frames sold under the same name can use different boards and firmware. Check the identity values
below before running anything that writes to the frame.

It is the same platform as the [LOOFII C-3](allwinner-a133-loofii-c3.md): A133, Android 10 `eng`,
32-bit userspace and an identical eMMC layout. Treat that page as the closest reference, but note
the differences below (1 GB RAM, Realtek Wi-Fi, microSD slot, no light sensor).

End result: a native Android dashboard (Kotlin and Jetpack Compose, no WebView) running as Device
Owner in lock task mode, Uhale disabled, a per-UID firewall, and ADB over Wi-Fi from one host only.
The code and setup scripts are in [eusonlito/Planify-Dashboard](https://github.com/eusonlito/Planify-Dashboard).
The stock Android stays; nothing was flashed except the boot logo (see below).

**Tested on:** one unit, bought from [Amazon Spain B0G2MJBR3M](https://www.amazon.es/dp/B0G2MJBR3M),
from a Linux host (Ubuntu 26.04, platform-tools 37.0.0) over USB-C and then over Wi-Fi ADB.

## Identity

| Field | Value seen on this unit |
| --- | --- |
| Product | XORO CPF 10PF, 10.1". Imported by MAS Elektronik AG |
| `ro.product.brand` / `ro.product.model` | `Allwinner` / `CPF10PF` |
| USB | `1f3a:1001 Allwinner Technology CPF10PF` (ADB and MTP) |
| SoC | Allwinner **A133** (`ro.hardware` = `sun50iw10p1`, platform `ceres`, board `exdroid`), 4× Cortex-A53 |
| GPU | PowerVR **GE8300** |
| RAM | **1 GB** (`MemTotal` 985816 kB, about 435 MB free at idle), zram 722 MB, `ro.config.low_ram=true` |
| Storage | 32 GB eMMC (`mmcblk0` = 31,268,536,320 bytes), `/data` 26 GB |
| Display | Panel is **1200×1920 portrait**, rotated by SurfaceFlinger (`ORIENTATION_90`), so apps see **1920×1200 landscape (16:10)**. The listing says 1920×1080. Density 320, 60.3 Hz |
| Touch | `gslX680` (I²C) |
| Sensors | Mi3da accelerometer only. **No light or presence sensor** |
| Wi-Fi | Realtek **RTL8189FS** (`8189fs`), **2.4 GHz only, no WPA3** |
| RTC | `sunxi-rtc`, but it **does not keep the time**: after a boot without network the clock showed the build date |
| Ports | microSD, USB-A 2.0 (host), USB-C (device: ADB/MTP), DC in, power switch, reset pinhole, volume |
| Power | DC adapter, no battery. The manual lists two adapters (5 V ⎓ 2 A or 12 V ⎓ 1.5 A); check the label on yours |

## Stock software

| Field | Value seen on this unit |
| --- | --- |
| Android | 10 (API 29, `QP1A.191105.004`), security patch 2021-01-05 |
| Fingerprint | `Allwinner/uhale/uhale:10/QP1A.191105.004/eng.ctk.20260130.093021:eng/test-keys` |
| Kernel | 4.9.170 arm64 |
| Userspace | **32-bit only** (`zygote32`, abilist `armeabi-v7a,armeabi`). A GSI would need `arm32_binder64` (not tried) |
| Bootloader | U-Boot 2018.05 |
| Treble | Enabled, VNDK 29, dynamic partitions (`super` 2 GiB), not A/B |
| AVB | `device_state=locked`, but vbmeta flags = 1 (hashtree disabled) |
| SELinux | Permissive |
| WebView | `com.android.webview` 74.0.3729.186 |
| Home app | Uhale, `com.zeasn.frame` 4.3.1 |

## ADB and root

- **ADB is on out of the box over USB-C**, and `adbd` runs as root (`ro.secure=0`,
  `ro.debuggable=1`). It worked at once, with no authorization prompt on the screen, although
  `ro.adb.secure=1` (one computer tested; not checked whether another key would be rejected).
- `/system/xbin/su` is **setuid root and executable by any app** (`-rwsr-sr-x root shell`).
  Any installed app can become root. If you keep the stock build, restrict it, for example
  `chown root:shell` and `chmod 4750` so only the ADB shell can use it (undo: `chmod 6755`).
- No network ADB listener by default.

## Vendor software

- **Uhale** (`com.zeasn.frame` 4.3.1, `/product/app/Uhale`) is the Home app and runs with the
  **system UID**. It includes Firebase Crashlytics and Analytics. It is from the app family in the
  [Quokka report](https://go.quokka.io/hubfs/App-Intel/Technical_Uhale-Digital-Picture-Frame-Security-Assessment.pdf).
  On this unit, which had never been online, there were **no indicators** from that report:
  no `/data/data/com.zeasn.frame/files/.honor`, no `com.app.mz.*` packages and no
  `com.zeasn.cook.CookService`.
- **`com.example`** (`/product/app/TS8ProdutionTest`): a factory test app, system UID and
  `persistent`, so Android starts it even when it is disabled. It has services that collect logcat
  and kmsg and a `FileUploader` that sends them to a `REPORT_UPLOAD_URL` read from
  `hxzl_service.properties` (that file is not on the frame). Removed for user 0 with
  `pm uninstall -k --user 0 com.example` (undo: `cmd package install-existing com.example`).
- Allwinner tools: `com.softwinner.dragonaging`, `dragonfire`, `fireplayer`,
  `com.allwinner.batterytest`, and `awlogd`/`kmsgd` writing logs to `/data/media/awlog/`.
- No separate FOTA agent (the LOOFII has one). Updates go through Uhale.

Disable Uhale before the frame goes online. Undo:

```sh
adb shell pm enable com.zeasn.frame
adb shell cmd package set-home-activity com.zeasn.frame/.base.ui.boot.BootTipsActivity
```

## eMMC layout and backup

The layout is **identical** to the LOOFII C-3, including a `super` of exactly 2,147,483,648 bytes:
`bootloader` (p1, 32 MiB FAT), `env`, `boot`, `super`, `misc`, `recovery`, `cache` (768 MiB),
`vbmeta`, `vbmeta_system`, `vbmeta_vendor`, `metadata`, `private`, `frp`, `empty`, `dtbo`,
`media_data`, `UDISK` (= `/data`, p17).

Backup before any write: everything before `/data` (GPT, boot0/U-Boot and all partitions, about
3 GiB), the backup GPT and the `boot0`/`boot1` hardware partitions, with `dd` over root ADB. The
SHA-256 of each piece was compared with the device.

### Do not mount the `bootloader` partition on the frame

Its FAT16 declares **262144 sectors (128 MB)**, but the partition is only **65536 sectors
(32 MB)**, and `env` comes right after it. If you mount it on the frame and write to it, a file can
land past the end of the partition and overwrite `env` or `boot`.

To change the boot logo, read the whole partition, edit it on the computer with mtools, check that
the last cluster of `bootlogo.bmp` ends before sector 65536 and that `fsck.vfat` reports nothing
new (the volume label warning is there from the factory), then write it back with `dd` and read it
back to compare. The logo is a 24-bit BMP of **1200×1920 (portrait)**, the way the panel scans.

## Things that bit

### Wi-Fi: no WPA3

With a router in WPA2/WPA3 mixed mode, Android 10 saves the network as WPA3 (SAE) and the driver
rejects the association at once (`Association request to the driver failed` in logcat). Add the
network by hand with security **WPA/WPA2-Personal**, or set the router to WPA2.

If it is already saved as SAE, fix `/data/misc/wifi/WifiConfigStore.xml` with the framework
stopped (`adb shell stop`): `ConfigKey` `"<ssid>"SAE` → `"<ssid>"WPA_PSK`, `AllowedKeyMgmt`
`num="2">0001` → `num="1">02`, and `RequirePMF` → `false`. Then `adb shell start`.

The driver does not pass the signal to Android (RSSI is always -127), and with location off Android
hides the SSID. Both can be read from `/proc/net/rtl8189fs/wlan0/rx_signal` and `ap_info`.

### Kernel suspend is broken

Over USB this never shows, because USB keeps the system awake. On Wi-Fi only, the first night with
the screen off:

- suspend failed on the accelerometer (`mir3da`, `3-0027`, errno 43);
- touch (`gslX680`) stopped responding (`gsl_ts_read set data address fail!`);
- `android.system.suspend@1.0-service` aborted (`ubsan: sub-overflow`, `eng` build);
- system_server restarted on wake.

Fix: a kernel wakelock from a boot script. The screen still turns off, but the system never
suspends:

```sh
echo my-frame > /sys/power/wake_lock     # undo: echo my-frame > /sys/power/wake_unlock
```

If touch is already stuck, it comes back without a reboot:

```sh
adb shell su 0 sh -c "rmmod gslX680new; insmod /vendor/modules/gslX680new.ko"
```

Check `success` and `fail` in `/sys/kernel/debug/suspend_stats` to confirm there are no suspends.

### Other

- **Touch does not wake the screen** once it is off (`lockNow()`); the power button does. For a
  night mode that you can tap, keep the screen on with a black window at minimum brightness
  (`screenBrightness` 1/255 is still readable here).
- **Clock:** the RTC does not keep the time, so until NTP arrives the frame shows the build date
  (2026-01-30). Don't trust the time, or schedule the screen, before the first sync.
- **Time zone** ships as `Europe/Amsterdam`.
- The ISRG Root X1 CA is in the system store, so Let's Encrypt certificates validate without
  extra roots.

## What was set up (all over ADB, reversible)

- Device Owner (`dpm set-device-owner`, no accounts on the device) and lock task with only
  Android Settings allowed, for Wi-Fi.
- Vendor apps disabled with `pm disable-user` (Uhale, Allwinner tools), `com.example` removed for
  user 0, Allwinner persistent logs off.
- A boot script in `/system/etc` with an `init` `.rc` (`adb remount` works): the wakelock above,
  `su` restricted to the ADB shell, and an outbound firewall by UID, based on
  [`scripts/a133/templates/firewall.sh`](../scripts/a133/templates/firewall.sh): only the dashboard
  app reaches the internet; everything else gets the LAN, DNS and NTP only. Inbound only allows
  ADB on 5555 from one host IP.
- Custom boot logo and boot animation (the only write outside `/system` and `/data`; see the
  `bootloader` warning above).

## Not tried on this unit

- U-Boot fastboot (`adb reboot bootloader`) and FEL through the reset pinhole. They work on the
  LOOFII C-3; the pinhole could be wired differently here.
- Booting from microSD.
- A GSI, a WebView swap or a web dashboard: the dashboard is native, so the stock WebView 74 was
  left alone.
