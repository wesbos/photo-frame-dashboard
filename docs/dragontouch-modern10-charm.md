# Dragon Touch Modern10 Charm (VPhoto): Wi-Fi root ADB and Firefox dashboard

Report from **one unit**, tested on **12 October 2026** using an **Apple silicon Mac,
macOS 27.0 (26A428)**. The owner bought it from
[Amazon UK, ASIN B0DXV3HGH7](https://www.amazon.co.uk/dp/B0DXV3HGH7).
The listing identifies the purchase, not a guarantee that another unit has this firmware.

**Verified result:** root ADB was already reachable over Wi-Fi. After a private, verified
backup, Rootless Pixel Launcher 3.9.1 and Firefox 143.0.4 ARMv7 were installed. The hosted
dashboard runs full-screen through Firefox's **Home HQ** home-screen shortcut, with the
stock system WebView retained. This is a browser setup; the repository's native kiosk APK
has not been tested on this unit.

![Hosted dashboard running full-screen on this unit; all displayed data is demo data](images/dragontouch-modern10-charm-dashboard.png)

## Identity and observations

| Item | Observed value |
| --- | --- |
| Model in Settings / properties | `Modern10 charm` |
| Firmware build | `Modern10 charm_A33MAU_202605151735_4.0_V01` |
| Android / SDK | `6.0.1` / `23` |
| Manufacturer / board / hardware | `joyhong` / `exdroid` / `sun8i` |
| Build fingerprint | `joy/astar_ococci/astar-ococci:6.0.1/MOB30R/20260515:user/test-keys` |
| CPU ABI | `armeabi-v7a` |
| Display / density | `1280x800` / `160` |
| Stock home app | VPhoto, `com.waophoto.smartframe` |
| Vendor updater | `com.waophoto.fota` |
| Stock WebView | `44.0.2403.119` |
| ADB shell identity | `uid=0(root)`, `gid=0(root)`, SELinux context `u:r:su:s0` |

The build's `A33` marker and `sun8i` hardware property suggest an **Allwinner A33-family**
board. The chip was not physically inspected. This is different firmware from the
PF1007L / AiMOR units. Neither the Rockchip `apply` script nor the PF1007L boot-patch routes
were used; those routes are not validated for this frame.

The owner reports a **USB-A port**. With a USB-A-to-USB-C cable connecting it to the Mac,
`system_profiler SPUSBHostDataType` showed no connected USB device. USB ADB was not obtained
with that combination. This does not establish whether another cable, port or mode would work.

## ADB access

The frame was already connected to Wi-Fi. Connecting to TCP port **5555** succeeded without
an authorization prompt, and the shell was already root. No developer-menu change, `adb tcpip`,
vendor-app trick, root installation or boot patch was needed during this session. Factory-reset
state and the persistence of this access across reboot have not been tested.

With Android platform-tools installed, replace the example address with the IP shown in the
frame's Settings. Read-only identity checks:

```sh
FRAME_IP='FRAME_IP_FROM_SETTINGS'
adb connect "$FRAME_IP:5555"
adb -s "$FRAME_IP:5555" shell id
adb -s "$FRAME_IP:5555" shell getprop ro.product.model
adb -s "$FRAME_IP:5555" shell getprop ro.build.display.id
adb -s "$FRAME_IP:5555" shell getprop ro.build.version.release
adb -s "$FRAME_IP:5555" shell getprop ro.hardware
adb -s "$FRAME_IP:5555" shell getprop ro.product.cpu.abi
```

Check your unit before making changes. Root ADB without an authorization prompt grants broad
access to anyone who can reach that port; keep it on a trusted network and do not expose it
to the internet. Changing ADB authentication or disabling network ADB was not part of this trial.

## Backup before app installation

A private live capture of the whole eMMC user area and both hardware boot areas completed
before installing apps. No firmware images or backup hashes are included in this report.

| Area | Raw bytes |
| --- | ---: |
| eMMC user area | 15,758,000,128 |
| eMMC boot0 | 4,194,304 |
| eMMC boot1 | 4,194,304 |

Verification checked exact raw byte counts, streamed SHA-256 against full gzip readback,
gzip integrity and uniform 64 KiB `0xCC` filler. Eight fresh reads matched the saved bytes:
both hardware boot areas, the disk header, a system-data sample, env, boot, recovery and
bootloader. Full boot, recovery, env and bootloader reads through their partition devices
also matched the corresponding whole-image ranges.

Two compatibility findings:

- Stock Android Toolbox `dd` returned `Invalid argument` and zero bytes when seeking to
  recovery beyond 2 GiB. **BusyBox `dd` worked** for the same offset. Use the partition map
  read from your own unit; do not reuse another model's offsets.
- The first 8 KiB of the live system partition differed in six bytes in the ext4 mount-time,
  mount-count and lifetime-write counters. Their locations are documented in the
  [Linux ext4 superblock layout](https://www.kernel.org/doc/html/latest/filesystems/ext4/super.html).
  A fresh 16 MiB system-data read starting 128 MiB into that partition matched the saved
  whole-image range. The mutable superblock bytes were not counted as a matching check.

Android was running during capture: writable filesystems were not frozen into an atomic
offline snapshot, and **restore has not been tested**. These are backup observations, not a
recovery or flashing guide.

## Launcher and browser setup

Only these two apps were added. The pinned builds also appear in
[biuframe-setup-guide.md](biuframe-setup-guide.md); that guide's device-specific system changes
were not applied here.

| App | Source | SHA-256 |
| --- | --- | --- |
| Rootless Pixel Launcher 3.9.1 | [F-Droid APK](https://f-droid.org/repo/amirz.rootless.nexuslauncher_30911.apk) | `7fa44d560dc4577374d45176220de2c0b00a71e09d6d148cdea4e0a52d38404a` |
| Firefox 143.0.4 ARMv7 | [Mozilla archive APK](https://archive.mozilla.org/pub/fenix/releases/143.0.4/android/fenix-143.0.4-android-armeabi-v7a/fenix-143.0.4.multi.android-armeabi-v7a.apk) | `af560738627d4efc9ace75e708fc48aad6a24c78ef43a89daca27e16ff3829f8` |

Both APKs passed source hash, Android signature and minimum-SDK checks (both require SDK 21).
Firefox's ARMv7 ABI matched the frame. APKs were transferred to `/data/local/tmp`, their
on-device hashes checked, then installed with root-shell `pm install`. Installed package
versions were verified and temporary APK copies removed. Package IDs are
`amirz.rootless.nexuslauncher` and `org.mozilla.firefox`.

To reproduce the UI setup after installing the verified APKs:

1. Open Rootless Pixel Launcher. In **Select home app**, choose **Rootless Pixel Launcher**
   and **Always**. The other choice on this unit was VPhoto.
2. Open Firefox, complete its initial onboarding, and visit
   [the hosted demo](https://home-dashboard.wesbos.workers.dev/).
3. In Firefox's menu, choose **Add to Home screen**. The **Home HQ** shortcut appeared on
   Rootless's home screen. Open that shortcut.
4. Verify that it opens full-screen without Firefox's normal toolbar. On this unit the
   activity was `org.mozilla.firefox/org.mozilla.fenix.customtabs.ExternalAppBrowserActivity`.
5. Try **Calendar**, then press and hold the small clock at the bottom left for about one
   second to open the demo-controls drawer. Both were tested successfully by touch.

The dashboard's manifest requests `fullscreen` and landscape orientation. Firefox uses its
own engine, so this route did not require replacing the stock WebView 44. The screenshot
above is a 1280x800 device capture of the working Today view.

The hosted demo contains sample people, events, weather and devices. Its clock initially
starts at 15:18 rather than the frame's real time. It returns to Today after 60 seconds idle
and enters ambient mode after 120 seconds. This is the demo's behaviour, not a device fault.
The frame fetches the hosted site directly over Wi-Fi; the Mac does not need to stay connected.

## Scope, exit and undo

- The repository's native kiosk app and its two-finger exit gesture are **not** part of this
  Firefox setup. Android navigation controls were hidden during the trial. ADB can return to
  the launcher with `adb -s "$FRAME_IP:5555" shell input keyevent 3`.
- To restore the vendor home app, open Android **Settings → Home** from Rootless's app drawer
  and choose **VPhoto**. The installed apps can remain available for another trial.
- VPhoto and its updater remain installed and enabled. They were not audited for remote
  commands; the AiMOR findings from another model should not be attributed to VPhoto.
  The [Joyhong JT101F-I02](joyhong-jt101f-i02.md) has the same platform (`astar_ococci`) and the
  same updater, `com.waophoto.fota`. There it is privileged, with `INSTALL_PACKAGES` and
  `REBOOT`. Consider `pm disable com.waophoto.fota` before the frame stays online.
- No system WebView replacement, CA-root changes, swap setup, boot patch or direct firmware
  writes were performed. The stock screen timeout was retained.
- Automatic dashboard startup after reboot, offline use, long-term stability and firmware
  restore are **not verified**. This report establishes the browser dashboard on this build,
  not full kiosk support for all Modern10 Charm units.

The local source checkout used for the trial was
`9dd323e7974f1d4cc10935044386101f9c18e6d0`. Check the current repository and the identity of
your own frame before adapting these observations.

## Follow-up, 2026-10-14: reboot behaviour, and the native kiosk on this unit

Same unit, same host family (Apple silicon Mac, macOS 27.0.1). The report above covers the Firefox
route set up on 12 October; this records what two further days of daily use on the same unit added,
and answers two things that report left open.

### Root ADB survives a reboot (previously untested)

After a normal reboot, connecting to `<frame-ip>:5555` again succeeded with no authorization prompt
and the shell was still root. The Android **Settings → Home** choice persisted as well.

### The native kiosk runs on this unit (previously untested here)

The report above notes that the repository's native kiosk APK "has not been tested on this unit".
It has now run on this unit continuously for two days, with two deliberate differences from
`dashboard/kiosk/`:

- **GeckoView rather than WebView.** This build ships AOSP WebView `44.0.2403.119`, too old to run
  the dashboard at all (no ES modules, no CSS `clamp()`). The kiosk is built around **GeckoView
  `143.0.20251003115653`, armeabi-v7a** — the same engine as the Firefox already installed on the
  unit — so nothing on `/system` is touched and the stock WebView is left in place. That avoids the
  WebView-swap route in [biuframe-setup-guide.md](biuframe-setup-guide.md) on this unit.
- **A `BOOT_COMPLETED` receiver rather than the Home-app route.** The kiosk starts itself from a
  `BootReceiver` and retries a failed load every 5 s, because Wi-Fi is usually not up yet at boot.
  VPhoto still claims `HOME`; the launcher's home screen carries a shortcut inserted directly into
  `launcher.db` (the launcher-database technique already described in [biuframe.md](biuframe.md)).

Observed working on this unit: the board renders full-screen at 1280x800 in the kiosk; the
two-finger hold for 1.5 s opens the native menu; **Exit Calendar** reaches Rootless Launcher; the
Accessibility service's floating **Back** / **Dashboard** buttons return to the board from Settings;
and the board starts itself after a reboot. As the kiosk README warns for other units, the
two-finger gesture could not be reproduced by injected touch here either — this touch controller is
protocol A (`gslX680`, no `ABS_MT_SLOT`) and Android rejected a synthetic two-contact frame — so it
was confirmed by a physical press.

### Force-stopping the app, or installing over it, drops the Accessibility service

The floating-button service was enabled by root ADB as documented above, and was later found **no
longer on the enabled list** after the kiosk had been force-stopped (`am force-stop`). A
`pm install -r` of the kiosk on its own did **not** drop it, tested straight afterwards. With no
navigation bar, those buttons are the way back from Settings, so this is worth checking after
either. Re-enable by root:

```sh
adb shell settings put secure enabled_accessibility_services <pkg>/<pkg>.NavigationService
adb shell settings put secure accessibility_enabled 1
```

Having the kiosk re-add itself on start, as `dashboard/kiosk`'s `keepNavigationEnabled()` does with
`WRITE_SECURE_SETTINGS`, is the durable fix. The symptom matches the PF1007L note in the
[kiosk README](../dashboard/kiosk/README.md#frames-without-home-or-back-buttons), on different
firmware. Whether a reboot alone also drops it was not isolated.

### One blank board, and a date bug that presents as a device fault

A single blank-white 1280x800 board was seen, with the kiosk activity still focused, no crash and no
error logged. It was not pinned to one cause: a stalled load and a stalled compositor both fit what
was observed. What is certain is that GeckoView reports both — `ProgressDelegate.onPageStop(success
= false)` for a failed load, and `ContentDelegate.onPaintStatusReset`, documented as firing
"whenever the painted content is no longer being displayed" — and that a kiosk which retries only on
a *failed* load will sit on a hung one indefinitely. The kiosk on this unit now retries a load that
has not finished, and rebuilds the session when the painted content stops being displayed.

A trap worth recording while adapting the upstream kiosk's stall retry: **on a load that hangs,
GeckoView fires `onFirstContentfulPaint` for the empty document.** Its own documentation says that
callback "may be nothing more than the page background colour. It is not an indication that the
whole page has been rendered." Treating it as "the page loaded" — the obvious reading of the name,
and how a WebView port would naturally read it — disables the stall retry exactly when it is
needed. Key the stall off `ProgressDelegate.onPageStop` instead, and treat
`ContentDelegate.onPaintStatusReset` as the callback that actually means the board has gone blank.

Separately, worth knowing because it presents as a device fault: **this frame's clock is set from
the network shortly after boot and can jump by years.** A page loaded before the jump computed its
date range from the wrong clock, so the calendar came up on an empty week in 1969 and the day view
read "free" all day, while weather and news (which involve no date) looked perfectly fine.
`adb shell uptime` reporting **idle time longer than uptime** was the tell.

Still untested on this unit: factory-reset behaviour, and firmware restore.

## Follow-up, 2026-10-19: USB-C root ADB from Windows

Second unit, same firmware string as the report above
(`Modern10 charm_A33MAU_202605151735_4.0_V01`, fingerprint
`joy/astar_ococci/astar-ococci:6.0.1/MOB30R/20260515:user/test-keys`, WebView
`44.0.2403.119`). Host: Windows 11, build 26200, with Google platform-tools installed by winget.
The identity checks matched before anything was installed.

### USB-C enumerates

The report above connected a USB-A port to a Mac with a USB-A-to-USB-C cable and saw no USB
device. On this unit the owner plugged the USB-C connector into Windows, and the frame
enumerated immediately. The case was not opened, so the host receptacle and the gadget
receptacle were not identified separately.

| Item | Observed |
| --- | --- |
| USB ID | `1f3a:1007` (Allwinner). Windows showed a USB composite device, an Android interface, and a WPD device named Modern10 charm |
| `adb devices -l` | `device`, `product:astar_ococci`, `model:Modern10_charm`, at the same time as the Wi-Fi connection on port 5555 |
| Shell | `uid=0(root)`, SELinux context `u:r:su:s0`, no authorization prompt |

No `adb tcpip`, developer-menu change, or boot patch was used.

A streamed BusyBox `dd` of `/dev/block/mmcblk0` moved about 7.1 MB/s over USB and about 0.9 MB/s
over Wi-Fi. The Wi-Fi copy was stopped after a few percent and repeated over USB. The user area
was 15,758,000,128 bytes, the same size as the unit above. Gzip readback matched the streamed
SHA-256. Fresh reads matched boot0, boot1, the first 1 MiB of the user area, bootloader, env,
boot, recovery (the partition device, and a seek to that range on `mmcblk0`), and a 16 MiB
sample starting 128 MiB into system. None of the 240,448 blocks of 64 KiB in the user area were
uniform `0xCC`. The whole-disk hash is not published.

### Partition map from this unit

`/sys/block/mmcblk0/mmcblk0p*/start` and `size` are 512-byte sectors. Names come from
`/dev/block/by-name` on this unit. Another model's offsets are not a substitute.

| Partition | Name | Start sector | Size, sectors |
| --- | --- | ---: | ---: |
| p3 | (no `by-name` link) | 1 | 2 |
| p2 | bootloader | 73728 | 65536 |
| p5 | env | 139264 | 32768 |
| p6 | boot | 172032 | 32768 |
| p7 | system | 204800 | 4194304 |
| p8 | misc | 4399104 | 32768 |
| p9 | recovery | 4431872 | 65536 |
| p10 | cache | 4497408 | 1572864 |
| p11 | metadata | 6070272 | 32768 |
| p12 | private | 6103040 | 32768 |
| p13 | frp | 6135808 | 1024 |
| p14 | empty | 6136832 | 31744 |
| p15 | alog | 6168576 | 163840 |
| p16 | media_data | 6332416 | 32768 |
| p1 | UDISK | 6365184 | 24412160 |

`/proc/partitions` reports the user area as 15,386,672 one-kilobyte blocks. `mmcblk0boot0` and
`mmcblk0boot1` are each 4,096 one-kilobyte blocks (4,194,304 bytes).

boot1 was entirely zeros at that size, and a second full read matched. BusyBox on the device is
v1.18.3. Stock toybox has no `sha256sum`. BusyBox `dd bs=1048576 skip=2164 count=32` read
recovery from `mmcblk0` past 2 GiB and matched a read of `/dev/block/by-name/recovery`.

### Windows `adb exec-out` and `dd`

`adb exec-out busybox dd if=/dev/block/mmcblk0 bs=512 count=1` returned 543 bytes: the 512 data
bytes plus `dd`'s status text. The local stderr pipe was empty, so the status arrived on the
data stream. Redirecting on the device kept the stream exact:

```sh
adb exec-out sh -c 'busybox dd if=/dev/block/mmcblk0 bs=1048576 2>/dev/null'
```

A 65,536-byte read of `/dev/block/by-name/boot` contained 552 `0x0a` bytes and was still exactly
65,536 bytes, so this Windows `adb` did not expand newlines. The first eight bytes were
`ANDROID!`.

### Clock

About 28 minutes after boot, `uptime` reported idle time longer than uptime, the tell from the
note above, while `date` already showed 19 October 2026. A jump of years was not seen in this
session.

Not tested here: whether USB ADB survives a reboot, factory reset, and firmware restore.

## Follow-up, 2026-10-31: firmware `V03`, Wi-Fi root ADB from macOS

Third unit, **newer firmware** than the units above. Host: Apple silicon MacBook Pro, macOS 26
(Darwin 25.6.0), Google platform-tools 37.0.1 (the zip from `dl.google.com`; no Homebrew).

| Item | Observed value |
| --- | --- |
| Firmware build | `Modern10 charm_A33MAU_26060810_4.0_V03` |
| Build fingerprint | `joy/astar_ococci/astar-ococci:6.0.1/MOB30R/20260608:user/test-keys` |
| VPhoto version (Settings → About) | `2.1.3.73` |
| CPU ABI | `armeabi-v7a` |
| ADB shell identity | `uid=0(root)`, SELinux context `u:r:su:s0` |
| BusyBox | `/sbin/busybox` |

### ADB: Wi-Fi only on this host

- **Wi-Fi:** `adb connect <frame-ip>:5555` succeeded with no prompt; the shell was root. As on `V01`,
  nothing had to be enabled first.
- **USB-C to USB-C:** the frame's USB-C port to the Mac's USB-C port, with a cable that syncs a phone
  on the same Mac, plugged in directly. `system_profiler SPUSBHostDataType` listed only the Mac's own
  buses: no device, and no macOS "Allow accessory" prompt. A USB-A host (an adapter or hub) on the Mac
  was not tried; the Windows report above may have used one.
- **Frame's USB-A port:** with a USB-C-to-USB-A cable from the frame's USB-A port to the Mac, the
  **Mac started charging from the frame**, which suggests the frame acts as USB host on that port. No
  data path to the Mac was seen. Don't leave a laptop charging from it.
- **Finding the IP:** the frame's Wi-Fi details dialog (Status, Signal strength, Link speed,
  Security) shows no IP address. A ping sweep of the subnet, then `arp -a` filtered by the Wi-Fi MAC
  from Settings → About, found it; the DHCP hostname was `android-<hex>`.

### Vendor updater: no boot hook on this build

`getprop persist.sys.start_ac` printed nothing, so the FOTA boot hook described in
[joyhong-c2-a133.md](joyhong-c2-a133.md#the-vendor-fota-boot-hook-read-this-before-disabling-anything)
does not appear to be present. `com.waophoto.fota` is `versionName=1.0` and lists
`.MainActivity`, `.MessageService` and `com.blankj.utilcode.util.MessengerUtils$ServerService`.
`pm list packages -3` was empty (VPhoto and the updater are system apps).

Only the updater service was disabled, not the whole package:

```sh
adb shell pm disable com.waophoto.fota/.MessageService
adb shell am force-stop com.waophoto.fota
# undo: adb shell pm enable com.waophoto.fota/.MessageService
```

`dumpsys package com.waophoto.fota` then listed `MessageService` under `disabledComponents`. Whether
this survives a reboot has not been tested yet.

### Partial backup and partition sizes

Not a full backup: only `bootloader`, `env`, `boot`, `recovery`, `misc`, `frp`, `mmcblk0boot0` and
`mmcblk0boot1`, over Wi-Fi with `adb exec-out "busybox dd if=… bs=1048576 2>/dev/null"`. Each file's
macOS `md5` matched an on-device `busybox md5sum` of the same block device, and the byte counts were
33,554,432, 16,777,216, 16,777,216, 33,554,432, 16,777,216, 524,288, 4,194,304 and 4,194,304.
Wi-Fi moved about 0.3 to 0.6 MB/s here, so a whole-disk copy over Wi-Fi was not attempted.

The `by-name` links and every partition size in `/proc/partitions` match the 19 October table
above (start sectors were not read on this unit). `/proc/partitions` lists `mmcblk0` as
15,388,672 one-kilobyte blocks, which is exactly the 15,758,000,128-byte user area; the
15,386,672 figure in the 19 October section looks like a typo.

### Browser dashboard

Rootless Pixel Launcher 3.9.1 and Firefox 143.0.4 ARMv7, the same pinned files and SHA-256
values as the first report, installed with `adb install -r` over Wi-Fi (Firefox took about
5.5 minutes to push). After choosing Rootless as Home (**Always**) and adding the hosted demo with
Firefox's **Add to Home screen**, the dashboard opened full-screen, as on `V01`.

There was no on-screen Back or Home control after leaving the dashboard for Settings (SystemUI's
state was not checked). `adb shell input keyevent 3` returned to the launcher.

Not tested on this unit: reboot persistence of network ADB and of the disabled updater service,
the native kiosk, a USB-A host on the Mac, factory reset and restore.
