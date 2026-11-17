# Frameo HRF102 ("SBUSFGT HY02C") frame access notes

One 10.1-inch Frameo frame, tested from macOS on 2026-11-16 and 2026-11-17. **Root ADB over USB
and Wi-Fi, a verified full eMMC backup and the repo's Home HQ kiosk are working.** The frame
boots into the kiosk on Wi-Fi, with no cable. This is a record of one unit, not a general Frameo
setup script.

Frameo's About screen calls it **SBUSFGT HY02C**; Android calls it **HRF102**. The firmware is
the same Spreadtrum `si006asb` / `sp7731g_1h10` product as the [Uhale SI006](si006-uhale.md),
[VTimes VT01001](vtimes-vt01001.md) and [TAPINSAW DW10](tapinsaw-dw10-s580.md), with Frameo as
the vendor app. The way in was the [HSB / F10 USB keyboard route](uhale-hsb-f10.md#1-open-the-browser-through-usb-hid).
The Allwinner FEL routes and Rockchip
loaders do not apply.

Three things differ from the sibling reports, and each one cost time:

1. **USB disappears about 80 seconds after power-on** until the saved USB mode is changed
   ([below](#usb-dies-80-seconds-after-boot)).
2. **The firmware ships a factory ADB key** in `/system`, and boot copies it back every time
   ([below](#adb-key-reset-at-every-boot-and-the-factory-key)).
3. **WebView 106 is already installed**, so the SI006 WebView overlay is not needed.

## Confirmed identity

| Field | Observed value | Source |
| --- | --- | --- |
| Listing | [Amazon US B0CCT9QGYH](https://www.amazon.com/dp/B0CCT9QGYH) | Owner's order |
| Frameo About | "Hardware brand and model number: SBUSFGT HY02C", Frameo `v1.30.19` | Frameo Settings → About |
| Model | `HRF102` (`ro.product.model`), brand `SPRD` | `getprop` |
| Firmware | `SPRD_HRF102_V01_202606011503` (`ro.build.display.id`) | `getprop` |
| Build fingerprint | `SPRD/si006asb/sp7731g_1h10:6.0/MRA58K/W26.23.1-15:user/release-keys` | `getprop` |
| Product / platform | `si006asb` / `sc8830` | `getprop` |
| Android | 6.0, SDK 23 | `getprop` |
| Security properties | `ro.secure=0`, `ro.debuggable=1`, `ro.adb.secure=1`; `getenforce` prints `Disabled` | `getprop`, `getenforce` |
| RAM | `MemTotal: 976420 kB` (about 1 GiB, same as the SI006) | `/proc/meminfo` |
| eMMC | 30,535,680 sectors of 512 bytes (same as the SI006) | `/sys/block/mmcblk0/size` |
| Display | 1280 × 800, density 160 | `wm size`, `wm density` |
| WebView | `com.android.webview` 106.0.5249.126 in `/system/app/webview` | `dumpsys package` |
| SystemUI | `/system/priv-app/SystemUI`, `versionName=6.0-eng.zfc.20260601.150141` | `dumpsys package` |
| Frameo | `net.frameo.frame`, a **data app** (`/data/app/net.frameo.frame-1`) | `pm list packages -f` |
| Stock browser | `com.android.browser` (`/system/app/Browser`) | `pm list packages -f` |
| Updater | `com.adups.fota` 5.28 (`/system/app/FotaUpdate`) and `com.adups.fota.sysoper` (`/system/app/UpdateProvider`) | `pm`, `dumpsys package` |
| Ports | Barrel-jack power, USB-C, microSD. No navigation bar | observation |
| Cable | USB-A (Mac) to USB-C (frame), through a hub | |

Once authorized, `adb shell` is already root (`uid=0`), and `su -c id` also returns root.

## Starting state

- Before any of this, Frameo's **Settings → About → Check for update** installed an update. The
  versions before it were not recorded, and whether it changed the Android firmware or only the
  Frameo app is unknown. The checks made before and after it (whether the Mac saw the frame over USB,
  and port 5555) gave the same result. Every version in [Confirmed identity](#confirmed-identity) was read after the update.
- Frameo's **Beta Program → ADB Access** toggle made no difference. USB enumerated and ADB
  started on every boot whatever the toggle said, and stayed `unauthorized`. No "Allow USB
  debugging?" prompt appeared on the screen at any point.
- TCP 5555 was refused on Wi-Fi; the only open TCP port found was 51234 (not identified).
- A Windows PC reported **"Configuration Descriptor Request Failed" (Code 43)** and the Mac showed
  nothing. Most likely each check ran after USB had already died (next section). What
  found the window was the owner noticing a Google USB device appear briefly during boot.

## USB dies 80 seconds after boot

Watching the Mac's USB tree (`ioreg -p IOUSB`) once a second through a power cycle:

| Time after power-on | USB device | ADB |
| --- | --- | --- |
| 0 s | `1782:4d00` "Gadget Serial" for a few seconds (the Spreadtrum bootloader) | |
| about 10 s | `1782:4012` "Spreadtrum" | `unauthorized` |
| about 60 s | `18d1:4ee7` "Spreadtrum" | `unauthorized` |
| about 80 s | gone | |

The saved USB mode was `persist.sys.usb.config=ptp,adb`. When Android applies it, about 80 s in,
the USB connection stops working until the next power cycle. From a root shell,
`setprop sys.usb.config adb` brought USB back at once, until the next boot.

**Fix (after the backup):**

```sh
adb shell setprop persist.sys.usb.config adb
```

After that, USB stayed connected through every later reboot. Frameo's photo transfer
from a computer probably relies on PTP; it was not tried after the change.
Undo: `adb shell setprop persist.sys.usb.config ptp,adb`.

The [TAPINSAW DW10](tapinsaw-dw10-s580.md) on the same product lost USB every few minutes. Its
`persist.sys.usb.config` was not recorded. It may be worth checking on similar units. That is a
guess, not something tested on the DW10.

## Working entry route

All of this happens inside the window from about 60 s to about 80 s after power-on, until the
USB fix above is in place.

### 1. Open the browser with an AOA USB keyboard

The frame answered AOA `GET_PROTOCOL` with version `2`. A small host helper (Python, `pyusb`
and libusb-1.0, not included here) registered a standard boot keyboard over USB control transfers
and sent key reports, using the requests and descriptor in the
[HSB / F10 report](uhale-hsb-f10.md#1-open-the-browser-through-usb-hid). It writes nothing to the
frame. Each key was held 60 ms, with 250 ms after each release.

- **Stop the host's ADB server first** (`adb kill-server`). On macOS, a running ADB server holds
  the device and the control transfers fail.
- Wait for `18d1:4ee7` before registering the keyboard. Registering it at `1782:4012`, earlier in
  boot, was not tried.
- **Meta+B** opened the stock Android browser. Offline, it shows an error page; that's fine.
- **Ctrl+L** selected the address bar.
- **The first keystroke after focusing the address bar was dropped**, every time, whatever the
  delay (tried up to 3 s). `file:///…` arrived as `ile:///…`, and the browser ran a search
  instead. Sending a throwaway **Ctrl+A** first fixed it. Typing `x` and then Backspace also
  works: whether or not the `x` is swallowed, the bar ends up empty.
- A report with only the Shift modifier set (`02 00 00 00 00 00 00 00`, then release) wakes the
  panel without typing anything.
- Keyboard registration occasionally timed out, or USB dropped mid-sequence. Running the whole
  sequence again worked.

Start the helper before power-cycling the frame, polling once every 0.3 s for `18d1:4ee7`.
About 3 s after the device appears, register the keyboard, wait 1 s, and press **Meta+B**
(report `08 00 05 00 00 00 00 00`). The device appeared 84 s and 93 s after power-on in two runs.

The browser stays open after USB drops, and works by touch.

### 2. Install Terminal Emulator

The frame was already on Wi-Fi, so the APK came from a small HTTP server on the Mac
(`python3 -m http.server`), with the address typed by touch in the browser
(`http://<mac-ip>:8000/t.apk`). The download finished, but tapping it did not open the
installer, and the browser later closed.

Opening the downloaded file by path worked:

1. `file:///sdcard/Download/t.apk` (or `file:///storage/emulated/0/Download/t.apk`).
2. The browser shows **"Connection problem: net::ERR_FAILED"**. Tap **OK**.
3. A **Download / Open** dialog appears. Tap **Open**, then **Install**, then **Open**.

Unknown sources were already allowed. The APK was Terminal Emulator 1.0.70, the F-Droid archive
build used by the sibling reports (hash in [Downloads used](#downloads-used)). Check the hash
before serving it.

To reopen the browser at that address in the next USB window, the sequence that worked was:
**Meta+B**, wait 2.5 s, **Ctrl+L**, wait 2.5 s, **Ctrl+A** (the throwaway key), wait 0.5 s, type
`file:///sdcard/Download/t.apk`, **Enter**. The chords were 0.4 s apart. In one run that
started late, USB dropped partway through the typing; running it again worked.

### 3. Root shell, and where `/sdcard` is

In Terminal Emulator, `su -c id` printed `uid=0(root)` with no prompt.

**As root, `/sdcard` is not the same folder.** `ls /sdcard/Download` in the terminal listed the
downloaded file, but `su -c 'sh /sdcard/Download/s.bin'` could not find it. Root sees the same
files at **`/data/media/0/Download/`**. The SI006 and VTimes reports found the same thing.

### 4. Authorize the host's ADB key and turn on ADB over Wi-Fi

A short root script, downloaded into Download through the browser (as in step 2), added the
host's **public** key and turned on network ADB. Put your own `~/.android/adbkey.pub` line in
it. Never copy the private `adbkey` to the frame. It was named `s.bin`; the browser asked
about the file type and saved it after **Download** was tapped. Other names were not tried. (`*.bin` is in this repo's `.gitignore`, so keep yours
outside the clone or name it differently there.)

```sh
# s.bin: run as root from Terminal Emulator:  su -c 'sh /data/media/0/Download/s.bin'
mkdir -p /data/misc/adb
grep -q "<first part of your adbkey.pub>" /data/misc/adb/adb_keys 2>/dev/null || \
  echo '<your adbkey.pub line>' >> /data/misc/adb/adb_keys
chown system:shell /data/misc/adb/adb_keys
chmod 640 /data/misc/adb/adb_keys
setprop persist.adb.tcp.port 5555
setprop service.adb.tcp.port 5555
stop adbd
start adbd
```

Pitfalls seen:

- Typing a long one-liner (`am start -d http://…; sleep 10; sh …`) failed. The browser asked
  about the file type, and by the time **Download** was tapped the timer had run out. Download
  first, then run the script on its own.
- The browser showed `k.txt` as a text page instead of saving it, so the key went into the
  script itself instead of a separate file.
- If USB is down while you are in the terminal, typing `su -c setprop sys.usb.config adb` by hand
  brings it back, and the AOA keyboard can then type the rest.

After `adb kill-server`, `adb connect <frame-ip>:5555` gave a root shell. **This key lasts only
until the next boot**; see the next section.

Undo network ADB: `adb shell setprop persist.adb.tcp.port -1` and reboot (not tested on this
unit). `/system/build.prop`
was not checked for `service.adb.tcp.port` on this unit; on the [VTimes](vtimes-vt01001.md#root-network-adb-and-daemonsu)
it was set to 5555 there. Network ADB is **root** ADB for any computer whose key is in
`adb_keys`; keep the frame on a network you trust.

## ADB key reset at every boot, and the factory key

After the first reboot, the frame was `unauthorized` again. As on the SI006, `/init.sc8830.rc`
(line 71) has:

```text
on post-fs-data
    copy /system/etc/security/adb_keys /data/misc/adb/adb_keys
```

On this firmware **`/system/etc/security/adb_keys` is not empty.** It holds one well-formed
2048-bit ADB public key whose comment is **`Administrator@DESKTOP-SOQ54TR`**: a computer at the
manufacturer. The file is `root:root` `0644`, 731 bytes, dated 2026-06-01 (the build date), and
ends with a newline. Its SHA-256 is
`019cc18a1c402ca97b4bed632d200276af6dbe3d040bd95f6996a714db3928d1`.

At every boot that key is copied over `/data/misc/adb/adb_keys`. So **whoever holds the
matching private key gets root ADB on every one of these frames over USB**, and over Wi-Fi once
network ADB is on. To compare yours:

```sh
adb shell 'cut -d" " -f2 /system/etc/security/adb_keys; sha256sum /system/etc/security/adb_keys'
```

(If `sha256sum` is missing, use `md5sum`: this file's MD5 is `de662b79e7338d8b49b02394aa3d9ff5`.)

**Fix used here:** keep a copy of the factory file, then replace it with only the host's key.
That removes the factory key and keeps the host's access through reboots:

```sh
adb pull /system/etc/security/adb_keys adb_keys.factory      # keep this
adb push ~/.android/adbkey.pub /data/local/tmp/host.pub
adb shell 'mount -o rw,remount /system &&
  cat /data/local/tmp/host.pub > /system/etc/security/adb_keys &&
  chown root:root /system/etc/security/adb_keys &&
  chmod 644 /system/etc/security/adb_keys &&
  sync && mount -o ro,remount /system; rm /data/local/tmp/host.pub;
  md5sum /system/etc/security/adb_keys'
md5 -q ~/.android/adbkey.pub    # must match (md5sum on Linux)
```

`cat >` keeps the file's owner and mode. SELinux is disabled here, so there's no label to keep.
After a reboot, USB and Wi-Fi ADB both connected with no prompt, and `/data/misc/adb/adb_keys`
held only the host's key.

To keep the factory key, append instead of replacing (`echo` a newline first if your file does
not end with one, as on the [VTimes](vtimes-vt01001.md#4-authorize-the-hosts-adb-key)).

Undo: `mount -o rw,remount /system`, push `adb_keys.factory` back the same way, remount
read-only, reboot.

A factory reset wipes `/data`, including `persist.adb.tcp.port` and possibly
`persist.sys.usb.config`, but not the key in `/system`; that was not tested. If the frame ever
stops trusting the host again, repeat the [entry route](#working-entry-route). With USB fixed,
the AOA keyboard works any time, not only in the boot window: `wake`, `meta+b`, `ctrl+l`, `text:x`, `backspace`, the
`file://` URL, then in the terminal `su -c 'sh /data/media/0/Download/s.bin'`.

## Security checks and Adups FOTA

- **SystemUI loader from the [Sammix report](sammix-aw105-uhale.md):** `find /system /data` found
  no `libunion*`, `*kw_lib*` or `plg`, and no hidden "Sys" apps. That's a check of the listed
  artifacts, not proof the firmware is clean.
- **Network connections** while on Wi-Fi (`netstat`, `/proc/net/tcp6` matched to app UIDs):
  Frameo (`net.frameo.frame`) to Cloudflare addresses, the browser to Google, and **uid 1000 to
  port 443 on an address registered to Tencent Cloud in Hong Kong**. uid 1000 is shared by many system
  apps; `ps` showed `com.adups.fota` running as `system`, so the match is likely but not proven.
  The connection's content was not examined.
- After the backup, both Adups packages were disabled:

  ```sh
  adb shell 'pm disable com.adups.fota; pm disable com.adups.fota.sysoper; am force-stop com.adups.fota'
  ```

  The Hong Kong connection was gone afterwards, and the packages were still disabled after a
reboot. Whether `com.adups.fota` restarts in a loop once disabled, as on the
[AKIMART](akimart-zn-dp1002.md) Android 8.1 firmware, was not checked. This also stops vendor
firmware updates.

  Undo: `adb shell pm enable com.adups.fota; adb shell pm enable com.adups.fota.sysoper`.

## Verified backup

Taken over USB with root `adb shell` / `adb exec-out`, partition by partition, before any change
except the ADB key and network ADB:

- Every `by-name` partition, both 4 MiB eMMC boot areas (`mmcblk0boot0`, `mmcblk0boot1`), the
  first 34 sectors (MBR and primary GPT) and the last 33 sectors (secondary GPT). 15.6 GB in
  total, including userdata; about 3.5 MB/s over USB.
- For each image: an MD5 computed on the frame, compared with the host's MD5, and a SHA-256 list
  on the host.
- 22 partitions, both boot areas and both GPT copies matched. `userdata` and `cache` differed,
  as expected for mounted read-write filesystems.
- **`system` differed even though it is mounted read-only.** Re-reading on the frame gave yet
  another checksum. Compared in 64 MiB chunks, 21 of 22 chunks matched. The only differences were
  in the first chunk: ext4 superblock fields such as the mount time and mount count. Treat
  `system` as "matches apart from the superblock", not as a byte-exact copy.
- **toolbox `dd` cannot seek past 4 GiB.** Reading the secondary GPT
  (`skip=30535647`) returned nothing. **`busybox dd`** on the frame read it correctly:

```sh
adb exec-out 'busybox dd if=/dev/block/mmcblk0 bs=512 skip=$(( $(cat /sys/block/mmcblk0/size) - 33 )) count=33 2>/dev/null' > gpt-tail.img
```

Keep the backup private: userdata holds Wi-Fi passwords, Frameo account data and photos. No
offline restore was tested.

## Radar presence sensor: does not work on this unit

The kernel exposes an input device **`zed-radar`** (driver `radar_control`, device tree node
`/radar_input`) that reports `KEY_WAKEUP`, and an interrupt `radar_irq`. There is also a light
sensor and an accelerometer. There is no camera.

With the screen off and someone walking up to the frame, `getevent` on the radar device showed
nothing, and the `radar_irq` count in `/proc/interrupts` stayed at **1** (the boot-time
interrupt). Writing `1` to the device's `motion_sensor` sysfs file succeeded (`rc=0`), but it read
back empty and changed nothing.

Frameo has a motion-sensor feature (`net.frameo.frame.feature.motion_sensor.MotionSensorHandler`),
but it turns on only when the firmware sets **`ro.frameo.motionsensor`**. This firmware sets other
`ro.frameo.*` properties but not that one. The likeliest explanation is that the board's
software includes the radar driver but the sensor isn't fitted or isn't wired up. That's
inferred, not confirmed by opening the frame. On this unit, a tap wakes the screen.

## WebView 106 and Android 6 limits

WebView 106 is preinstalled as `com.android.webview`, and the dashboard's user agent reported
`Chrome/106.0.5249.126`. The SI006 overlay and WebView swap were not needed. The three CA roots
from the [SI006 report](si006-uhale.md#fonts-and-https-photos) were not added, and whether
this unit needs them was not tested.

Android 6's emoji font is old. Weather symbols such as 🌦️ (sun behind rain cloud) drew as
empty boxes. ☔ ❄️ ☁️ ⚡ ⛅ ⛈️ ☀️ 🌙 💨 drew correctly. Test any emoji on the frame itself, not
in a desktop browser.

## Home HQ kiosk

The repo's `dashboard/kiosk` was built on the Mac (JDK 17, Android build-tools 34.0.0, platform
34) with the page bundled through `KIOSK_SITE`, then installed with `adb install`. See the
[kiosk guide](../dashboard/kiosk/README.md) for each flag. Credentials were not built into the
APK.

- **Home app:** after `--ez home true`, the Home chooser appeared. Home HQ → **Always** stuck
  (`always="true"` in `package-restrictions.xml`). Frameo was **kept installed** as the second
  Home app, so the kiosk's **Open launcher** has somewhere to go. It stays behind the kiosk.
  Undo: pick Frameo in Settings → Apps → Default apps → Home, then
  `adb shell am start -n com.wesbos.homehq/.MainActivity --ez home false`.
- **The two-finger hold did not open the kiosk's menu** on this touchscreen. The single-tap
  **Menu** button worked:
  `adb shell am start -n com.wesbos.homehq/.MainActivity --ez menu_button true`.
  It sits at the bottom left, so keep that corner of the page clear. Undo: `--ez menu_button false`.
- **No navigation bar.** Opening Android Settings left no way back by touch. The kiosk's
  **NavigationService** fixes this with floating Back and Dashboard buttons:

  ```sh
  adb shell pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS
  adb shell settings put secure enabled_accessibility_services com.wesbos.homehq/com.wesbos.homehq.NavigationService
  adb shell settings put secure accessibility_enabled 1
  ```

  Both settings were `null` before. The owner tested it by hand: Menu → Android settings, then
  the floating **Dashboard** button, returned to the kiosk. The buttons sat near the screen
  edge, where this touchscreen sometimes needed a second tap, so drag them further in.
  Undo: `pm revoke` the permission, `settings put secure enabled_accessibility_services ""`,
  `settings put secure accessibility_enabled 0`.
- A reboot test passed: the frame went straight into the kiosk, USB stayed connected, the Menu
  button and floating buttons were still there, and Adups was still disabled.

### Screen sleep: drop `FLAG_KEEP_SCREEN_ON`

`MainActivity` sets `FLAG_KEEP_SCREEN_ON`, so Android's screen timeout never applies while the
kiosk is in front. To test screen sleep (and the radar), a local build removed that flag:

```java
getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);   // was FLAG_KEEP_SCREEN_ON | FLAG_FULLSCREEN
```

With `adb shell settings put system screen_off_timeout 600000`, the panel turned off after 10
minutes without a touch, and a tap woke it straight back into the dashboard. The stock
`screen_off_timeout` was `0`. This is a local change, not an upstream kiosk feature.
Undo: reinstall the unmodified kiosk, keeping the same signing key.

The owner later chose an always-on screen instead:

```sh
adb shell settings put global stay_on_while_plugged_in 7
adb shell settings put system screen_off_timeout 2147483647
adb shell settings put secure screensaver_enabled 0     # the clock daydream was on (1)
```

Undo: `stay_on_while_plugged_in 0`, `screen_off_timeout` back to your previous value,
`screensaver_enabled 1`.

## Change summary and undo

| # | Change | Undo |
| --- | --- | --- |
| 1 | Host key appended to `/data/misc/adb/adb_keys` from the terminal | Lost at the next boot anyway (row 6 replaces it) |
| 2 | `persist.adb.tcp.port=5555` (network ADB) | `setprop persist.adb.tcp.port -1`, reboot (untested) |
| 3 | `pm disable com.adups.fota`, `com.adups.fota.sysoper` | `pm enable` each |
| 4 | `persist.sys.usb.config=adb` (was `ptp,adb`) | `setprop persist.sys.usb.config ptp,adb` |
| 5 | Home HQ installed, saved URL, set as Home with Always; Menu button on; NavigationService on | See [Home HQ kiosk](#home-hq-kiosk); `adb uninstall com.wesbos.homehq` removes it |
| 6 | `/system/etc/security/adb_keys` replaced with the host's key only (factory copy kept) | Put the factory copy back, as above |
| 7 | Kiosk without `FLAG_KEEP_SCREEN_ON`, then `stay_on_while_plugged_in=7`, `screen_off_timeout` set, `screensaver_enabled=0` | Reinstall the stock kiosk; restore the three settings |

## Downloads used

Binaries are not included.

| Item | Source | SHA-256 |
| --- | --- | --- |
| Terminal Emulator 1.0.70 | [F-Droid archive](https://f-droid.org/archive/jackpal.androidterm_72.apk) | `95095176ca3fa421102352ecaea0fffb6d13527db023967a7cfa280f7bc05cb5` |
| pyusb (host only, for the AOA keyboard helper) | [PyPI](https://pypi.org/project/pyusb/), installed into a virtualenv | not recorded |
| Temurin JDK 17 and Android build-tools 34, platform 34 (host only, to build the kiosk) | Adoptium and Google `sdkmanager` | not recorded |

## Limits

- One unit, one firmware (`W26.23.1-15`). Another "HY02C" listing may have a different board;
  match the fingerprint before reusing anything here.
- Android 6.0 with root `adbd` and SELinux disabled. Keep the frame on a trusted network and do
  not sign in to sensitive accounts on it.
- Whether other `si006asb` builds ship the same factory key was not checked. The SI006 and VTimes
  reports kept their factory file but did not record its key comment.
- What Adups sent to the Hong Kong address was not examined.
- Frameo's own data use was not examined. Frameo was left installed and enabled.
- The **Timer Switch Machine** entry in Android Settings (probably a scheduled on/off) was
  seen but not tried.
- No offline flash restore was tested.
