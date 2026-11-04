# YunQiDeer YQ156001 15.6" Frameo (Allwinner A133, Android 10)

A record of **two units**. Root ADB over USB with no flashing: turn on Frameo's ADB toggle, accept
the prompt, and `adb shell` is already uid 0. The only hard part on the first unit was the cable.
The second unit replaced the stock WebView 74 with LineageOS WebView 155 by editing `/product`
as root, and now boots into the Home HQ kiosk with Frameo disabled. That needed a one-line init
file, because this firmware leaves ending the boot animation to Frameo
([second unit](#second-unit-webview-155-and-the-kiosk)).

**Tested on:**

- **First unit**, set up on 2026-10-17: bought new on eBay for $59.95
  ([item 800520985117](https://www.ebay.com/itm/800520985117), "YunQiDeer FRAMEO Digital Photo
  Frame 15.6 in IPS Touch Screen"), from a MacBook (M1, macOS 26.6) with platform-tools 35.0.2.
- **Second unit**, 2026-10-28: same firmware, smaller eMMC. From a Mac (M4 Pro, macOS 26.6.2) with
  platform-tools 36.0.2, over USB.

## Identity

| Field | Value seen on this unit |
| --- | --- |
| About screen | `YunQiDeer YQ156001`, Frameo `v1.22.5 (43680)` |
| USB | `1f3a:1001`, product `ceres-mcx`, vendor string `Frameo` |
| `ro.product.model` / `ro.product.manufacturer` | `ceres-mcx` / `Frameo` |
| `ro.hardware` / `ro.board.platform` | `sun50iw10p1` (Allwinner A133) / `ceres` |
| Android | 10, `user` build, kernel 4.9.170, `armeabi-v7a` userspace |
| `ro.build.display.id` | `ceres_mcx_V01_24071114` |
| `ro.build.fingerprint` | `Allwinner/ceres_mcx/ceres-mcx:10/QP1A.191105.004/20240711-145712:user/release-keys` |
| RAM / storage | 1 GB with `ro.config.low_ram=true` / 32 GB eMMC (61063168 sectors), 25 GiB userdata |
| Display | 1920x1080, density 210 |
| WebView | `com.android.webview` 74.0.3729.186 |
| Home app (stock) | `net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted`; Launcher3 and SystemUI also installed |
| Vendor updaters | `com.adups.fota`, `com.qiot.update` (both running) |
| Boot image | `boot` (p3, 65536 sectors) SHA-256 `c51e5ee772b0dcad36396c87cceb4fa95745670dc679f895614be51fcae00065` |

## Ports and cable

Back panel, left to right: SD/MMC slot, headphone jack, **USB-A** (host, for thumb drives),
**USB-C** (device port, ADB), 12V DC barrel jack. The frame is powered by the 12V jack, not USB.

- **USB-C to USB-C from the Mac does not work.** The Mac's port stayed at `ConnectionActive = No`
  with no transports in `ioreg`, so the frame doesn't present itself as a USB device on the CC
  lines and the Mac never turns the port on.
- **A cable into the USB-A port does nothing.** That port is a host port.
- **Working:** Mac USB-C → USB-C hub (Anker) → USB-A to USB-C data cable → the frame's USB-C port.

## Getting ADB

1. Frameo Settings → About → **Beta Program** on, then **ADB access** on.
2. Connect as above. `adb devices` first showed `unauthorized` with no prompt on screen.
3. Toggling **ADB access** off and on with the cable plugged in brought up the
   "Allow USB debugging?" prompt. After accepting, the frame showed as `device`.

No ADB on port 5555 was found on the LAN, but the frame was not connected to Wi-Fi at the time.

## Root and security state

- `ro.secure=0`, `ro.debuggable=1`: `adb shell id` returns `uid=0(root)` with context `u:r:su:s0`.
- `/system/xbin/su` is setuid root (`-rwsr-sr-x root shell`) and `su 0 id` also returns root.
- `ro.adb.secure=1`: the key check is on.
- `getenforce` reports **Permissive**, though the kernel command line has `androidboot.selinux=enforcing`.
- `ro.boot.verifiedbootstate=green`, `ro.boot.vbmeta.device_state=locked`, and the eMMC user
  area has a `TOC0.GLH` header at byte 8192 (Allwinner secure boot). The `mmcblk0boot0`/`boot1`
  hardware partitions are empty. Patching `boot` is untested and probably fails verified boot;
  root ADB makes it unnecessary.

## Partition layout

512-byte sectors, from `/sys/block/mmcblk0/mmcblk0p*/start` and `size`.

| Name | Device | Start | Size |
| --- | --- | --- | --- |
| bootloader | p1 | 73728 | 65536 |
| env | p2 | 139264 | 32768 |
| boot | p3 | 172032 | 65536 |
| system | p4 | 237568 | 4194304 |
| vendor | p5 | 4431872 | 737280 |
| product | p6 | 5169152 | 737280 |
| misc | p7 | 5906432 | 32768 |
| recovery | p8 | 5939200 | 85536 |
| cache | p9 | 6024736 | 1572864 |
| vbmeta | p10 | 7597600 | 32768 |
| metadata | p11 | 7630368 | 32768 |
| private | p12 | 7663136 | 32768 |
| frp | p13 | 7695904 | 1024 |
| empty | p14 | 7696928 | 31744 |
| dtbo | p15 | 7728672 | 4096 |
| media_data | p16 | 7732768 | 32768 |
| UDISK (`/data`, f2fs) | p17 | 7765536 | 53297599 |

Unlike the [LOOFII C-3](allwinner-a133-loofii-c3.md), this build has no `super` partition:
`system`, `vendor` and `product` are plain partitions.

## Backup

Everything before userdata over root ADB, about 6 minutes at ~13 MB/s:

```sh
adb exec-out "dd if=/dev/block/mmcblk0 bs=4096 count=970692 2>/dev/null" \
  | tee >(shasum -a 256) | gzip -1 > emmc-0-7765536.img.gz
```

`count` is in 4 KiB blocks: 7765536 sectors / 8. A `bs=1M` read would stop short, because
7765536 sectors is not a whole number of MiB. Verified with the exact byte count (3975954432),
a gzip readback against the stream hash, and on-device re-reads of the first 73728 sectors,
`boot`, 16 MiB of `system`, `recovery`, `vbmeta`, `dtbo` and `media_data`, each matching its
range in the image. The backup GPT is the last 33 sectors (from 61063135).

## Second unit: WebView 155 and the kiosk

Everything in this section is from the second unit, which isn't the unit the sections above describe.

### How it differs from the first unit

Same `ro.build.fingerprint`, same `boot` SHA-256 (`c51e5ee7…00065`), and p1–p16 have the same start
and size. Frameo's `versionName` was `v1.32.16_-_OTA_test` (the first unit's About screen showed `v1.22.5`). The eMMC is smaller:
`AT2Y1B`, dated 08/2024, **60604416** sectors.

| | First unit | Second unit |
| --- | --- | --- |
| eMMC sectors | 61063168 | 60604416 |
| UDISK (p17) size | 53297599 | 52838847 |
| Backup GPT starts at | 61063135 | 60604383 |

The [backup command](#backup) is the same for both, because everything before userdata is the same.
To save the backup GPT, use the frame's own size minus 33 (`cat /sys/block/mmcblk0/size`), not a
fixed number.

### Why the C-2/C-3 WebView route doesn't work here

The [joyhong C-2](joyhong-c2-a133.md#webview-and-the-kiosk) and LOOFII C-3 updated WebView by
re-signing LineageOS WebView with the AOSP testkey and running `adb install -r`. That depends on
the stock WebView being signed with the testkey. On this build it isn't (the fingerprint ends in
`release-keys`):

| APK | Signer SHA-256 |
| --- | --- |
| `/product/app/webview/webview.apk` (74.0.3729.186) | `80:F6:AB:10:…:3A:84:64` (vendor key, not the AOSP testkey) |
| `/system/framework/framework-res.apk` (platform) | `8D:AD:34:59:…:CE:0A:20` (a different vendor key) |

`dumpsys webviewupdate` lists only `com.android.webview`, so there's no second provider package
to install either.

### Why editing `/product` works

Checked read-only before any write:

- `fstab.sun50iw10p1` mounts `system`, `vendor` and `product` with `wait,first_stage_mount` only:
  no `avb` or `verify` flag, and no `dm-*` devices exist. `/product` is `/dev/block/mmcblk0p6` directly.
- `vbmeta` (p10) has hash descriptors for `boot`, `dtbo` and `recovery`, chain descriptors for
  `vbmeta_system` and `vbmeta_vendor` (neither partition exists), and a **hashtree** descriptor
  for `product`. That hashtree is only enforced by dm-verity, which fstab doesn't turn on.
- The ext4 on p6 has no `shared_blocks` feature (so it remounts read-write) and **no journal** (so
  keep power steady while it's read-write). 157032 KiB were free.
- The stock WebView APK stores `libwebviewchromium.so` uncompressed and page-aligned (offset
  9609216), and there's no `lib/` folder on disk.

### The swap that worked

1. **Fetch LineageOS WebView 155**: [`android_external_chromium-webview_prebuilt_arm`](https://github.com/LineageOS/android_external_chromium-webview_prebuilt_arm)
   at `170e8996e41ef542769b5479297ab91072b487e2` (the same commit the C-2 and C-3 used), `webview.apk`,
   SHA-256 `e744cd81ea83cfa6bda3da471ce58a5d9eac5d32260ad0ef98b8c9f49348f20e`, 97638829 bytes.
   Without `git-lfs`, the LFS batch API on the server in the repo's `.lfsconfig` returns a download link:

   ```sh
   curl -s -X POST -H 'Accept: application/vnd.git-lfs+json' -H 'Content-Type: application/vnd.git-lfs+json' \
     -d '{"operation":"download","transfers":["basic"],"objects":[{"oid":"e744cd81ea83cfa6bda3da471ce58a5d9eac5d32260ad0ef98b8c9f49348f20e","size":97638829}]}' \
     https://review.lineageos.org/LineageOS/android_external_chromium-webview_prebuilt_arm.git/info/lfs/objects/batch
   ```

2. **Don't re-sign it.** It's signed with APK Signature Scheme v2 (no v1 `META-INF`). Any valid
   signature works, because PackageManager accepts a new signer for a package on a system partition.
3. **Its libraries aren't page-aligned** (`libwebviewchromium.so` at offset 13749120), so Android
   can't load them from inside the APK. It also doesn't extract libraries for an app on a read-only
   partition. So the extracted libraries go next to the APK, in `lib/arm/`, where PackageManager
   already looks (`legacyNativeLibraryDir=/product/app/webview/lib`):

   ```sh
   unzip -j webview.apk 'lib/armeabi-v7a/*' -d webview-155-lib-arm
   adb push webview.apk /data/local/tmp/webview155.apk
   adb push webview-155-lib-arm /data/local/tmp/webview155-lib-arm
   adb shell cp /product/app/webview/webview.apk /data/local/tmp/webview74-stock.apk   # for undo
   adb shell cp -a /product/app/webview/oat /data/local/tmp/webview74-oat              # for undo
   adb shell mount -o remount,rw /product
   adb shell 'set -e
     W=/product/app/webview
     cp /data/local/tmp/webview155.apk $W/webview.apk
     rm -r $W/oat
     mkdir -p $W/lib/arm
     cp /data/local/tmp/webview155-lib-arm/*.so $W/lib/arm/
     chown -R root:root $W
     chmod 755 $W $W/lib $W/lib/arm $W/lib/arm/*.so
     chmod 644 $W/webview.apk
     chcon -R u:object_r:system_file:s0 $W
     sync'
   adb shell mount -o remount,ro /product
   adb reboot
   ```

   Check every file's SHA-256 after copying. This left 36208 KiB free on `/product`.

**Result after the reboot:** `ro.boot.verifiedbootstate` was still `green`. `dumpsys webviewupdate`
reported `com.android.webview` 155.0.8059.39 as current and preferred, with 1 of 1 relro finished.
PackageManager logged `System package com.android.webview signature changed; retaining data.` In
the built-in HTML viewer, `oklch()`, `color-mix()`, `aspect-ratio` and flex `gap` rendered. That
viewer always turns JavaScript off; the kiosk below showed JavaScript working.

**Undo:** remount `/product` read-write, copy `webview74-stock.apk` back to `webview.apk` and
`webview74-oat` back to `oat`, delete `lib/`, set labels again, remount read-only and reboot. Not tested.
A saved image of p6 restores it exactly; it's the range 5169152–5906431 of the [backup](#backup).

### Vendor updaters

- `com.adups.fota` (`/product/priv-app/FotaUpdate`) is marked `PERSISTENT`. After
  `pm disable-user --user 0` it came back with a new PID about every 30 s, as on the
  [DP101](veswwe-dp101.md#setup-that-worked). `pm uninstall -k --user 0 com.adups.fota` stopped it;
  no process came back over 2.5 min after a reboot. Undo: `cmd package install-existing com.adups.fota`.
- `com.qiot.update` (`/system/app/SystemFota`, shared user `android.uid.system`) stopped after
  `pm disable-user --user 0` and stayed off after a reboot. Nothing else on the system (framework,
  apps, init scripts, compiled code) references `com.qiot`. Settings only links to Adups from its
  System Update entry.
- **Wait for the save before rebooting.** The first attempt rebooted too soon, and both updaters
  came back enabled. `enabled="3"` took about 9 s to appear in
  `/data/system/users/0/package-restrictions.xml`, and `adb reboot` doesn't wait for it. The same
  happened on a Pastigio FRAME156 (#139). Check with
  `grep 'name="com.adups.fota"' /data/system/users/0/package-restrictions.xml` before rebooting.

### Frameo runs root commands

Frameo uses the shipped `/system/xbin/su`. At boot, `net.frameo.frame` ran `su` and then `cmd`,
and SystemUI was disabled right after (`enabled="2"` in `package-restrictions.xml`). SystemUI's
process kept running, so the panel looked normal. Launcher3 was already disabled the same way.
Strings in Frameo's code include:

- package changes: `pm disable `, `pm enable com.android.systemui`, `pm install -r `, `pm uninstall --user 0 `
- system and ADB: `mount -o rw,remount /system`, `setprop service.adb.tcp.port 5555 && stop adbd && start adbd`, `settings put global adb_enabled`
- power and screen: `svc power reboot`, `input keyevent 223` / `224`, screen brightness settings

Frameo also has a malware scanner (`BadBoxDetector`, `BadBox2Detector`, `BadPotionDetector`,
`BadWeatherDetector`). It checks for files under `/data/data/com.android.systemui/`, such as
`files/plg` and `app_e_kw_lib`. None of them existed on this unit.

`enabledCaller="shell:1000"` in `package-restrictions.xml` doesn't tell you who made a change:
commands from a root `adb shell` were recorded the same way.

### Home HQ kiosk

`dashboard/kiosk` 1.1, built with `build.sh` (JDK 17, build-tools 34). After the swap, `adb install -r`
and the default demo URL worked. On WebView 155 the whole demo dashboard rendered, including the
JavaScript parts. At the stock density of 210 (about 1463×823 CSS px by calculation) nothing was cut off, with narrow
dark bands on the left and right. The app used about 162 MB PSS.

### Home HQ as the Home app, Frameo disabled

These steps were done in this order, each followed by a reboot:

1. `am start … --ez home true`, then `cmd package set-home-activity com.wesbos.homehq/.Home`. Wait
   until `<preferred-activities>` in `package-restrictions.xml` names `com.wesbos.homehq/.Home`
   (about 6 s) before rebooting.
2. `pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS`, then set
   `enabled_accessibility_services` to `com.wesbos.homehq/com.wesbos.homehq.NavigationService` and
   `accessibility_enabled` to `1`, for the floating Back and Dashboard buttons.
3. With Frameo still enabled, reboot. Home HQ was in front, and the owner checked by hand that the
   two-finger menu reached Android Settings → Apps and that the Dashboard button came back.
4. `pm disable-user --user 0 net.frameo.frame` **and** `pm enable com.android.systemui` before the
   same reboot. With Frameo gone, nothing turns SystemUI off at boot, and SystemUI provides the only
   wallpaper. After the reboot: Home HQ was Home, Wi-Fi reconnected (the network is saved in Android,
   `wifi_on=1`), USB ADB still worked, and the hand check passed again.

In Settings, Frameo's App info then shows **ENABLE** greyed out, so turning Frameo back on needs ADB
(`pm enable net.frameo.frame`). Its data (about 495 MB including received photos) stays in place.

### The boot animation never ends without Frameo

With Home HQ as Home, the Frameo boot logo stayed over the screen after every boot, even with
SystemUI and its wallpaper back. Home HQ was running underneath and took touches. The cause is in
this firmware's `/system/framework/services.jar`:

- In stock Android 10, `WindowManagerService.performEnableScreen` sets `service.bootanim.exit` to `1`
  once the Home app, keyguard and wallpaper are drawn. In this build, the method sets
  `mBootAnimationStopped` and tells SurfaceFlinger the system has booted, but the `SystemProperties.set` call is gone.
  The string `service.bootanim.exit` appears 0 times in either `classes.dex`. Read with `dexdump -d`
  from build-tools 34.
- `ActivityManagerService.systemReady` sets a vendor property, `service.bootanim.delay`, from a
  vendor resource (`0x01110049`).
- So the firmware leaves ending the animation to the Home app, which is Frameo (it has root through
  the shipped `su`). Any other Home app leaves the logo up.

`adb shell setprop service.bootanim.exit 1` clears it until the next reboot. The permanent fix that
worked was a two-line init file. `/system` (`mmcblk0p4`, mounted as `/`) has no dm-verity, and its
ext4 has no `shared_blocks`:

```sh
adb shell mount -o remount,rw /
adb shell 'printf "on property:sys.boot_completed=1\n    setprop service.bootanim.exit 1\n" > /system/etc/init/homehq-bootanim.rc
  chown root:root /system/etc/init/homehq-bootanim.rc
  chmod 644 /system/etc/init/homehq-bootanim.rc
  chcon u:object_r:system_file:s0 /system/etc/init/homehq-bootanim.rc
  sync'
adb shell mount -o remount,ro /
```

Check `/system` against your backup first. After a reboot with no manual step:
`init.svc.bootanim=stopped`, `service.bootanim.exit=1`, verified boot `green`, and the dashboard on
screen. Undo: remount `/` read-write and delete the file. The PF1506's stuck boot animation (#104,
#118) may have the same cause; not checked.

## Guesses, not tested

- The board looks close to the PF1506 (A133, `ceres`, shipped `su`, permissive SELinux) and
  the [VESWWE DP101](veswwe-dp101.md) (`ceres`, Android 10, Frameo + Adups). The DP101 shipped
  WebView 113 and kept it. For the WebView step, the [C-2](joyhong-c2-a133.md#webview-and-the-kiosk)
  is closer (A133, WebView 74), but its testkey route doesn't apply; see the
  [second unit](#second-unit-webview-155-and-the-kiosk).
- `ro.config.low_ram=true` may kill background apps the way the
  [Denver PFF-1015](denver-pff-1015.md#low-ram-mode-kills-every-app-you-leave) does. Not checked yet.
- The `product` hashtree in `vbmeta` suggests verity was meant to be on. A future firmware that
  turns it on would refuse a changed `/product`.
