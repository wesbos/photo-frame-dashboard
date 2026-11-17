# Skylight Frame 2 (firmware D104S.V2.20.1)

One unit, tested 2026-11-16 from macOS (Apple silicon). Observations are separate from guesses,
and guesses are marked. This is Skylight's photo frame, not the 15" Skylight Calendar in
[skylight-d156.md](skylight-d156.md) and [next-session.md](next-session.md): different SoC
(RK3126, 32-bit), older Android (5.1.1), and root ADB out of the box. None of the Calendar
scripts apply.

The end state on this unit: Fotoo slideshow from an SMB share on the NAS, starting at boot, the
physical **Menu** button acting as Home, vendor app and updaters disabled. Nothing was flashed.

## Identify it

The label on the back reads "Skylight Frame, Model No: Skylight 2". It has a micro-USB port (data,
used here) and a USB-A port (not tested), and a physical button labeled **Menu**.

Over USB with a micro-USB **data** cable, straight into the Mac:

| Check | Value |
| --- | --- |
| USB | `2207:0010`, product `rk312x`, interfaces: mass storage + ADB (class `ff/42/01`) |
| `ro.build.fingerprint` | `rockchip/rk312x/rk312x:5.1.1/LMY49F/D104S.V2.20.1:userdebug/test-keys` |
| `ro.build.display.id` | `D104S.V2.20.1` |
| Android | 5.1.1 (SDK 22), `userdebug`, `ro.secure=0`, `ro.debuggable=1`, `ro.adb.secure=0`, SELinux permissive |
| SoC | `ro.board.platform=rk312x`, `ro.hardware=rk30board`, `armeabi-v7a` (32-bit only) |
| RAM | 512 MB (`MemTotal` 502568 kB), `ro.config.low_ram=true`, 64 MB zram |
| Display | 1280×800, 160 dpi. Status bar, **no navigation bar** |
| Storage | 7.1 GiB eMMC (`mmcblk0`, `1021c000.rksdmmc`) |
| WebView | `com.android.webview` 39 |
| Wi-Fi | Broadcom (`bcmdhd`, SDIO on `mmc1`) |
| Vendor packages | `com.skylight` 10.21.0 (updated over the air in 2026; `/system/app/Skylight` is 6.6.2), `skylight.watchdog` 3.3.0, `com.adups.fota`, `android.rockchip.update.service` |
| Home app | `com.skylight`. No AOSP launcher is installed |

The 4.8 GiB `user` partition is the vfat volume the frame exposes over USB mass storage and mounts
at `/mnt/internal_sd`. The Skylight app keeps its photos in
`/mnt/internal_sd/Android/data/com.skylight/files/pictures/`.

Partition layout (`/dev/block/platform/1021c000.rksdmmc/by-name/`), start and size in 512-byte
sectors:

| # | Name | Start | Size |
| --- | --- | --- | --- |
| p1 | uboot | 16384 | 8192 |
| p2 | misc | 24576 | 8192 |
| p3 | resource | 32768 | 32768 |
| p4 | kernel | 65536 | 24576 |
| p5 | boot | 90112 | 24576 |
| p6 | recovery | 114688 | 65536 |
| p7 | backup | 180224 | 131072 |
| p8 | cache | 311296 | 262144 |
| p9 | userdata | 573440 | 2088960 |
| p10 | metadata | 2662400 | 32768 |
| p11 | kpanic | 2695168 | 8192 |
| p12 | system | 2703360 | 2097152 |
| p13 | radical_update | 4800512 | 131072 |
| p14 | user | 4866048 | 10076160 |

Partition-image SHA-256 on this unit (to compare with yours):

| Partition | SHA-256 |
| --- | --- |
| uboot | `0ecffea53f5af403fbf6817a393f7c30d10702391f23c1d57255955d6d992398` |
| kernel | `cfadd44a103cbd6d5726fa07b27d7aad2f67ed3930ff96901c486a5beaf7e723` |
| boot | `e2415bbc7f0b5ecd53062c9a2e30576f1e7fbec0b488e46629621189a58b0ae7` |
| recovery | `853a15d4d275d6278d7c180a6263b3fb83d88cfafdb046b4716285499f854cdd` |

## ADB and root

- **USB ADB is on out of the box**, no authorization prompt (`ro.adb.secure=0`): any computer
  plugged in is accepted. `adb devices -l` shows `product:rk312x model:rk312x device:rk312x`.
- **`adb shell` already runs as root** (`uid=0`, context `u:r:su:s0`). `/system/xbin/su` is
  SuperSU (`daemonsu`); `su -c id` and `su 0 id` both work.
- **Network ADB** was not enabled (`persist.adb.tcp.port` and `service.adb.tcp.port` empty).
  Port 5555 was not probed. Don't enable it: with no key check, anyone on the LAN would get root.
- **The Skylight app holds a root session.** `ps` showed `daemonsu:10049`, where 10049 is
  `com.skylight`'s uid. That app updates itself from the vendor's servers.

## Back up first

With root ADB, the whole eMMC can be streamed to the host. Nothing on the frame is written.

```sh
mkdir -p backups/skylight-frame-2 && cd backups/skylight-frame-2
adb shell sync
adb exec-out 'dd if=/dev/block/mmcblk0 bs=1048576 2>/dev/null' \
  | tee >(shasum -a 256 > stream.sha256) >(wc -c > stream.bytes) \
  | gzip -1 > mmcblk0.img.gz
gzip -t mmcblk0.img.gz
```

On this unit it took 28 minutes over USB 2.0 (about 4.5 MB/s) and gave 7,650,410,496 bytes
(`/sys/block/mmcblk0/size` × 512), 745 MB gzipped, no `0xCC` filler. Device-side
`md5 /dev/block/mmcblk0pN` matched the image for uboot, resource, kernel, boot, recovery, backup
and radical_update.

**`system` never hashes the same twice on this firmware, even though it is mounted read-only.**
The stock ramdisk's `/init.connectivity.rc` has:

```
service daemonsu /system/xbin/daemonsu --auto-daemon
   class main
```

It is not `oneshot`. `daemonsu` daemonizes and exits, so init restarts it about every 5 s
(`init.svc.daemonsu` is stuck at `restarting`). Each start briefly mounts `system`: in 30 s the
ext4 mount count went from 5479 to 5485 and `s_kbytes_written` grew. Only the superblock, two
metadata blocks and the journal change; the other 14 of the 16 64 MiB chunks of `system` read
back identically. To check a `system` image, compare the stable chunks and run `e2fsck -fn` on it.
The only error here was `Inode 7, i_size is 96518144, should be 100728832` (the resize inode),
also present when the metadata chunk was read live, so it is in the stock image. State: clean.

Use `adb pull` or `adb exec-out` to hash files. `adb shell cat` goes through a pty on Android 5.1
and turns LF into CRLF.

## What worked

### 1. Take it offline first

The frame was on Wi-Fi when first connected, and the Skylight app and watchdog had updated
themselves two months earlier. `adb shell svc wifi disable` until step 3.

### 2. A launcher

There is no launcher besides Skylight, so install one before disabling it. Lawnchair needs a much
newer Android. KISS from F-Droid works on API 21 and has no native code:

- `https://f-droid.org/repo/fr.neamar.kiss_224.apk` (3.26.0), SHA-256
  `da6ab0b1219ad3b5ee573698523fb15d60a918083e0843f94a03c1b12e1098c9`, matching F-Droid's signed
  `index-v1.jar`. That index is signed with SHA-1, so `jarsigner` reports it unsigned unless
  `jdk.jar.disabledAlgorithms` is cleared for the check.

```sh
adb install fr.neamar.kiss_224.apk
```

### 3. Disable the vendor apps

None of the four has the `PERSISTENT` flag, so plain `pm disable` was enough (no restart loop,
unlike Adups FOTA on the [Akimart](akimart-zn-dp1002.md)):

```sh
for p in skylight.watchdog com.skylight com.adups.fota android.rockchip.update.service; do
  adb shell pm disable $p
done
```

With Skylight disabled, HOME resolves to KISS alone, with no chooser. Turning Wi-Fi back on
(`svc wifi enable`) reconnected to the saved network: on this Android 5.1 build, disabling
`com.skylight` did **not** remove its Wi-Fi networks (compare step 1 of the D156 kiosk setup).
A reboot kept all four disabled with no processes.

### 4. Fotoo with an SMB share

[Fotoo](https://play.google.com/store/apps/details?id=com.bo.fotoo) 2.6.5 (`com.bo.fotoo`,
versionCode 16005) needs API 21. There is no Play Store on the frame, and APKMirror doesn't carry
it. APKPure serves an XAPK per architecture; the default download had only an `arm64_v8a` split,
which won't install on this 32-bit frame and lacks `libfotoo_smb.so`. The `armeabi-v7a` XAPK
works. In both, every APK is signed by `O=Bopp Studio` (certificate SHA-256
`96d198c850786664f7a798d51be00088fbcbea134d06f093c78e97ca950779eb`) with a valid Google Play
source stamp; check with `apksigner verify --print-certs`. The base APK was byte-identical in both
XAPKs.

| File | SHA-256 |
| --- | --- |
| `com.bo.fotoo.apk` | `1927c07664669566a87f01e14521cef907adff57de13eb1032df238d5bc031f1` |
| `config.armeabi_v7a.apk` | `fbb77e20e5d06d0c1827c2e87e67c6b0daf685778f56bcf0b444e0b835af038a` |
| `config.en.apk` | `b6420e29ad49b6a93f3def51c645c94a80c66faccae334e2b5c6099cc08686eb` |
| `config.xxhdpi.apk` | `0b0ee2d01365e00bb193d0899c997ea688dc03a65bd234c6d48e504296d95520` |

```sh
adb install-multiple com.bo.fotoo.apk config.armeabi_v7a.apk config.en.apk config.xxhdpi.apk
```

`dumpsys package com.bo.fotoo` then shows `primaryCpuAbi=armeabi-v7a`. Fotoo runs offline with
local photos, and a slideshow from an Unraid SMB share worked on 512 MB with the vendor apps
disabled.

The SMB form (**Local Network**) has Name (optional), **Address**, Guest login, Username and
Password. Address took the NAS IP alone, with no `smb://` or share name; the share and folder are
picked by browsing afterwards. `libfotoo_smb.so` bundles libsmb2 (SMB2/3, NTLM) and libdsm (SMB1),
so Unraid's defaults (SMB1 off) work. Use a read-only NAS user: the frame stores the password.

Fotoo's in-app purchase needs Google Play, so it can't be bought on this frame.

### 5. Menu button as Home

There is no navigation bar, and Fotoo has no exit gesture. `setprop qemu.hw.mainkeys 0` followed
by `stop; start` (system_server restarted) did **not** produce a navigation bar on this firmware.
Fotoo's window asks for `0x1700` (sticky immersive, no hide-navigation bit), so a bar would
probably have shown over the photos anyway.

`getevent -lt /dev/input/event2` shows the Menu button as `KEY_MENU` (scancode 139) on
`rk29-keypad`, which `/system/usr/keylayout/rk29-keypad.kl` maps to `CALCULATOR`. Remap it:

```sh
adb shell 'mount -o remount,rw /system &&
  cp -p /system/usr/keylayout/rk29-keypad.kl /system/usr/keylayout/rk29-keypad.kl.bak &&
  busybox sed -i "s/^key 139   CALCULATOR\$/key 139   HOME/" /system/usr/keylayout/rk29-keypad.kl &&
  sync; mount -o remount,ro /system'
adb reboot
```

Stock file SHA-256 `845f6bf3cccbbc0e350a05f6466fbf1aa438a65d8ace088e2b6e115f14ddcc0d`, edited
`6689156a15c63027643a46a310578796fb0fa0db6d0881a200b1472917e36ff9`. After the reboot, Menu returns
to KISS from the slideshow.

### 6. Start Fotoo at boot

Fotoo's own **Launch on boot** setting cannot work here. Its `BOOT_COMPLETED` receiver was
refused with `Unable to launch app com.bo.fotoo/… for broadcast … BOOT_COMPLETED: process is bad`,
with no Fotoo crash in the log. The same message appeared for the stock Calendar, Gallery and
StressTest apps. Guess: the ROM blocks background process starts for apps outside a whitelist.

`/system/bin/install-recovery.sh` runs at every boot as root (`service flash_recovery`, class main,
oneshot), so a launch block was appended to it, after the stock lines:

```sh
# photo-frame-dashboard: open Fotoo once Android has finished booting.
# The ROM blocks Fotoo's own BOOT_COMPLETED receiver ("process is bad").
(
  while [ "$(getprop sys.boot_completed)" != "1" ]; do sleep 2; done
  sleep 10
  am start -n com.bo.fotoo/.ui.splash.FTSplashActivity
) &
```

Keep a `.bak`, then restore owner `root:root`, mode `0750` and label
`u:object_r:install_recovery_exec:s0` on the new file. Stock SHA-256
`bafeb15aa1ec80127f211173783afe09958cca833c006107799c033b503828a5`. After a reboot,
`sys.boot_completed` was set at about 27 s and Fotoo resumed its NAS slideshow about 15 s later.

## Open questions

- **The `daemonsu` restart loop** keeps writing to `system` every few seconds. Making the service
  `oneshot` means editing the boot ramdisk. Not tried.
- **The USB-A port** was not tested (host mode, a USB Wi-Fi dongle or a mouse).
- **Other Skylight Frame 2 firmware.** Only `D104S.V2.20.1` has been seen. A `user` build would
  not have root ADB.
- **WebView 39** is too old for modern web dashboards. Newer WebView builds dropped Android 5
  (guess: around Chromium 95). Not tried.

## Undo

```sh
for p in com.skylight skylight.watchdog com.adups.fota android.rockchip.update.service; do
  adb shell pm enable $p
done
adb shell 'mount -o remount,rw /system &&
  cp -p /system/usr/keylayout/rk29-keypad.kl.bak /system/usr/keylayout/rk29-keypad.kl &&
  cp -p /system/bin/install-recovery.sh.bak /system/bin/install-recovery.sh &&
  chcon u:object_r:install_recovery_exec:s0 /system/bin/install-recovery.sh &&
  sync; mount -o remount,ro /system'
adb uninstall com.bo.fotoo
adb uninstall fr.neamar.kiss
adb reboot
```

The full eMMC backup is the fallback for anything else.
