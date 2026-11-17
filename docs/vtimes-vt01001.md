# VTimes VT01001 frame access notes

One 10.1-inch VTimes frame tested on Arch Linux (Omarchy, x86_64) on 2026-10-18. **Root USB
ADB, a verified firmware backup, WebView 106, the CA roots and the repo's Home HQ kiosk are
working.** The frame boots into the kiosk on Wi-Fi with no USB cable. This is a record of one
unit, not a general VTimes setup script.

The firmware is the same Spreadtrum product as the [Uhale SI006](si006-uhale.md)
(`si006asb` / `sp7731g_1h10`) with a VTimes vendor app and a newer build. The SI006 WebView
overlay and CA root steps worked unchanged. The way in was different: ADB was already on over
USB, but the vendor app has no working hidden menu, so the
[HSB / F10 USB keyboard route](uhale-hsb-f10.md#1-open-the-browser-through-usb-hid)
was used to reach the browser. The Allwinner FEL routes and Rockchip loaders do not apply.
The [Frameo HRF102](frameo-hrf102.md) used the same route.

## Confirmed identity

| Field | Observed value | Source |
| --- | --- | --- |
| Listing | [Amazon US B0FLJTNRPH](https://www.amazon.com/dp/B0FLJTNRPH?tag=webo080-20), brand VTIMES, model number `SMXK-003`, sold as "10.1" Digital Calendar, 1280 \* 800 WiFi Digital Picture Frame" | Amazon listing |
| Vendor app | VTimes 1.5.0, package `com.rino.instaview` (`/system/priv-app/VtimesSmart`) | About page, `pm` |
| Brand / model | `VTimes` / `VT01001` | About page, `ro.product.model` |
| Firmware | `VTimes_VT01001_V01_202511101224` | About page |
| Build fingerprint | `VTimes/si006asb/sp7731g_1h10:6.0/MRA58K/W25.46.1-12:user/release-keys` | `getprop` |
| Product / device / board / platform | `si006asb` / `sp7731g_1h10` / `sp7731gea_hdr` / `sc8830` | `getprop` |
| Android / SDK / ABI | 6.0 / 23 / `armeabi-v7a` | `getprop` |
| RAM | `MemTotal: 2012680 kB` (about 2 GiB; the SI006 report has about 1 GiB) | `/proc/meminfo` |
| eMMC | 30,777,344 sectors of 512 bytes (SI006: 30,535,680) | `/sys/block/mmcblk0/size` |
| Display | 1280 × 800, density 160 | `wm size`, `wm density` |
| WebView | `com.google.android.webview` 80.0.3987.132 in `/system/app/webview` | `dumpsys package` |
| USB | `1782:4002`, name `Spreadtrum`, MTP + ADB interfaces from the first boot | sysfs |
| Cable | USB-A (PC) to USB-C (frame) | |
| Power | Separate barrel-connector adapter. `dumpsys battery` reports `USB powered: true`, `AC powered: false` and a battery at 100% anyway, so it does not show the real power source | |

## Starting state

- New out of the box, at the VTimes setup screens: language, privacy policy, Wi-Fi (can be
  skipped), time zone. Wi-Fi was skipped and the frame stayed offline until the vendor apps
  were disabled.
- The time zone chosen in the VTimes setup did **not** change the system time zone, which
  stayed `America/New_York`. The date could not be set in the setup and read Dec 31, 2011
  until NTP set it on Wi-Fi.
- USB already exposed an ADB interface, but `adb devices` showed `unauthorized` and no RSA
  prompt appeared at any point. `adb reconnect` made the frame disappear from `adb devices`
  until the cable was replugged.
- No navigation bar. The VTimes app fills the screen.

## What did not work

- VTimes **Settings → About**: 30 taps, fast and slow, on System Version; about 15 taps each on
  Firmware Version, Model, VTimes Software Version and Brand; 15 taps on the logo on the home
  screen. Nothing opened. The VTimes Settings menu (My Frame, Manage Album, Account Management,
  Display, Slideshow Settings, Wireless Network, Notifications, Help, About) has no ADB or
  developer entry.
- **Keyboard menus.** In any text box (for example My Frame → Frame Name), a long press on the
  comma key opens Input options. **Languages** opens a Settings sub-page whose back arrow
  returns to VTimes. **Android Keyboard Settings → Text correction → Personal dictionary** opens a
  Settings page with no search and no back arrow; there is no way back by touch.
- AOA keyboard **Meta+Esc** did not act as Home on this frame. `Esc` did act as Back.
- The browser could not open `file:///storage/emulated/0/Download/...` the first time (see below).

## Working entry route

### 1. Open the browser with an AOA USB keyboard

This follows the [HSB / F10 report](uhale-hsb-f10.md#1-open-the-browser-through-usb-hid). The frame answered AOA `GET_PROTOCOL` (request 51)
with version `2`, so it accepts HID input over USB. The host registered a standard boot-keyboard
HID with requests 54 and 56 (the descriptor in the [HSB / F10 report](uhale-hsb-f10.md#1-open-the-browser-through-usb-hid)) and sent eight-byte keyboard reports
with request 57. This needs no app on the frame and writes nothing to it. The host helper
(Python `ctypes` with `libusb-1.0`) is not included here; the [HSB / F10 report](uhale-hsb-f10.md#1-open-the-browser-through-usb-hid) lists the protocol details.

- `Esc` worked as Back, which also gave a way out of the Personal dictionary page.
- **Meta+B** opened the stock Android 6 browser. Offline it shows `ERR_INTERNET_DISCONNECTED`.
- **Ctrl+L** selected the address bar. Typed text arrived correctly with each key held 50 ms
  and about 150 ms per character.

### 2. Copy the APK over MTP, not over the network

Unlike the [HSB / F10 unit](uhale-hsb-f10.md), the frame stayed offline. MTP worked with GNOME's `gvfs-mtp` (`gio mount`), and
the APK was copied to **Internal storage/Download** with `gio copy`. The SHA-256 read back from
the frame matched.

In the browser, `file:///storage/emulated/0/Download/androidterm.apk` first gave
**"Connection problem: net::ERR_FAILED"**. After **OK**, a **"Download / Open"** dialog appeared
("This type of files can be opened, select open or download"). **Open** started the package
installer. Unknown sources was already allowed; the installer did not block it.

### 3. Shipped root in Terminal Emulator

Terminal Emulator 1.0.70 (F-Droid archive build, hash below). The prompt is
`u0_a70@sp7731g_1h10`. `su -c id` returned `uid=0(root) gid=0(root) groups=0(root)
context=u:r:init:s0` with no prompt.

### 4. Authorize the host's ADB key

As on the SI006, `/init.sc8830.rc` line 72 has:

```text
copy /system/etc/security/adb_keys /data/misc/adb/adb_keys
```

Both files existed. `/data/misc/adb/adb_keys` was `root:shell` `0640` `adb_keys_file`;
`/system/etc/security/adb_keys` was `root:root` `0644` `system_file`. The factory file has **no
newline at the end**, so appending a key directly would join it to the factory key's line.

The host's **public** key (`~/.android/adbkey.pub`) was copied to Download over MTP. In the root
terminal:

```sh
su -c 'cp -p /data/misc/adb/adb_keys /data/misc/adb/adb_keys.orig && (echo; cat /data/media/0/Download/adbkey.pub) >> /data/misc/adb/adb_keys'
```

The owner saved the copy in `/data/local/tmp`. That folder is writable by the ADB shell user, so
keep root-made copies in a root-only folder such as `/data/misc/adb/`, as above.
The `/data/media/0/...` path is the one the root shell can read, as on the SI006. After
`adb kill-server`, the frame showed as `device`. This lasts until the next boot.

## Root, network ADB and `daemonsu`

- `ro.secure=0` and `ro.debuggable=1`: once authorized, `adb shell` is already root
  (`u:r:su:s0`). SELinux is enforcing.
- **`/system/build.prop` has `service.adb.tcp.port=5555`, and `adbd` listened on `0.0.0.0:5555`.**
  On Wi-Fi this would give root ADB to anything on the same network that has an authorized key
  (key rejection over the network was not tested). Change it before the frame goes online (below).
- `daemonsu` (`/system/xbin/daemonsu --auto-daemon`, `init.rc` line 752) is in a restart loop
  (`init.svc.daemonsu=restarting`) and remounts `/system` about every 5 seconds
  (`EXT4-fs (mmcblk0p17): re-mounted` in `dmesg`). `/sys/fs/ext4/mmcblk0p17/lifetime_write_kbytes`
  rose by 72 KiB in 10 seconds while `/system` was mounted read-only. This is the same loop as
  in [uhale-a33-astar-d7.md](uhale-a33-astar-d7.md#backup-and-the-daemonsu-remount-loop).
  `stop daemonsu` stopped the remounts until the next boot; `su` in the terminal still worked
  after a reboot.

## Verified backup

Taken over `adb exec-out` with `toybox dd`, with `daemonsu` stopped:

- Sectors 0 to 3,334,143 (1,707,081,728 bytes, 1628 MiB): every partition before userdata. The
  layout before userdata is **identical to the SI006**; userdata (`mmcblk0p23`) starts at
  sector 3,334,144 on both. Only the userdata size differs.
- Both 4 MiB eMMC boot areas, and the last 33 sectors (secondary GPT, `EFI PART` header).
- Checks: exact byte count, complete gzip readback with matching SHA-256, a device-computed MD5
  of the same range that matched, no 1 MiB blocks of `0xCC` filler, and independent re-reads
  that matched for boot (`mmcblk0p16`), recovery (`mmcblk0p21`), the full system partition
  (`mmcblk0p17`), both boot areas and the secondary GPT.
- **The first acquisition, taken with `daemonsu` running, did not match.** A per-partition
  comparison showed only `system` differed; two reads of it differed in 40,203 bytes of ext4
  metadata (superblock times, inode times, journal). The second acquisition with `daemonsu`
  stopped matched everywhere.

Partition images, for comparison with other units:

| Partition | Sectors | SHA-256 |
| --- | --- | --- |
| boot (`mmcblk0p16`) | 71,680 + 32,768 | `7a50e3374c6347af2dbca2bd18a04bf730abc4917cb26b64effdf903f35fad5c` |
| recovery (`mmcblk0p21`) | 3,295,232 + 36,864 | `81c6207f72b4c736b4ed6e817df0add0c47aa0d18458e739048a94b916ec1cb2` |

Userdata was not backed up. No offline restore was tested.

## Persistent ADB key and no network ADB

Both changes were made in one script, with `daemonsu` stopped, that first checked the current
contents (the factory `adb_keys` equal to the saved original, and `build.prop` by MD5), saved
copies to `/data/local/tmp` (better: a root-only folder, see above), remounted `/system` read-write, rewrote the files with `cat >` so
owner, mode and SELinux label stayed the same, remounted read-only, and compared the result.

1. `/system/etc/security/adb_keys` = the factory key, a newline, and the host's public key.
2. `/system/build.prop` line 185: `service.adb.tcp.port=5555` → `service.adb.tcp.port=-1`.

**Do not edit `build.prop` with `sed` on the frame.** The frame's toybox `sed`
(`s/^service\.adb\.tcp\.port=5555$/service.adb.tcp.port=-1/`) produced a file 24 bytes larger,
with a NUL byte in place of the newline after the changed line and part of the next line
repeated. The script's checks stopped before any write. The edited file was made on the host
(exactly one line different) and pushed.

After a reboot: USB ADB connected with no prompt, `/data/misc/adb/adb_keys` equalled the
`/system` file, `service.adb.tcp.port` was `-1`, and nothing listened on 5555 in `/proc/net/tcp`
or `tcp6`. A listener on `127.0.0.1:5037` (loopback only) exists on the frame; its program was
not identified.

Undo: restore the two files from the saved copies the same way and reboot.

## Vendor packages disabled

Before Wi-Fi, with `pm disable-user --user 0` and `am force-stop`. Undo with `pm enable`.

| Package | Code path | Version |
| --- | --- | --- |
| `com.adups.fota` | `/system/app/FotaUpdate` | 5.28 |
| `com.adups.fota.sysoper` | `/system/app/UpdateProvider` | 5.1.5 |
| `com.fota.wirelessupdate` | `/system/priv-app/DlSystemFota` | 4.4.2 |
| `com.sprd.systemupdate` | `/system/app/SystemUpdate` | 6.0 |
| `net.nault.nobel` | `/system/priv-app/DlSystemUpdate` | 1.0 |
| `com.cghs.stresstest` | `/system/app/StressTest` | 3.0.2 |
| `com.zediel.pcbtest` | `/system/app/ZedielPcbTest` | 6.6 |
| `com.rino.instaview` (VTimes) | `/system/priv-app/VtimesSmart` | 1.5.0 |

No packages were disabled from the factory. VTimes was not a device administrator. What the
VTimes app does online was not examined; it was disabled before the frame went on Wi-Fi.

## WebView 106 and CA roots: SI006 steps unchanged

The framework's `config_webViewPackageName` is `com.google.android.webview`, as on the SI006.

1. WebView 106.0.5249.126 (`com.android.webview`, ARMv7) installed with `adb install` as a data app.
2. [`scripts/si006-webview-overlay`](../scripts/si006-webview-overlay/) built unchanged (JDK 17,
   build-tools 34.0.0, platform 34). `idmap --path` against this frame's `framework-res.apk`
   mapped exactly one entry, `string/config_webViewPackageName` (entry `0x4b`, resource
   `0x0104004b`).
3. `/system/vendor/overlay` did **not** exist and was created (`root:root` `0755`
   `system_file`). The overlay was placed there as `si006-webview-overlay.apk`
   (`root:root` `0644` `system_file`).
4. After a reboot, Android generated `/data/resource-cache/vendor@overlay@si006-webview-overlay.apk@idmap`,
   and logcat showed `Loading com.android.webview version 106.0.5249.126 (code 524912600)`.

The three CA roots from the SI006 report (`f013ecaf.0`, `5acf816d.0`, `6187b673.0`) were not
present and had no filename collisions among the 158 existing files. They were added in the
same format as the existing files (PEM followed by `openssl x509 -text -fingerprint` output),
`root:root` `0644` `system_file`. The dashboard's fonts and photos then loaded over HTTPS.

Undo: delete the overlay (and the folder) and the three certificates, reboot, then uninstall
the extra WebView.

## Home HQ kiosk

The unmodified upstream kiosk (`dashboard/kiosk`, built with JDK 17 and build-tools 34.0.0;
JDK 17 from Arch's `jdk17-openjdk`) was installed with `adb install`, with the documented
`WRITE_SECURE_SETTINGS` grant, and its navigation service enabled with
`settings put secure enabled_accessibility_services com.wesbos.homehq/com.wesbos.homehq.NavigationService`
and `accessibility_enabled 1` (both were `null`). The floating Back and Dashboard buttons appeared.

Choosing the Home app on Android 6:

- After `--ez home true`, the Home chooser showed a **"last used" suggestion** at the top.
  Tapping Home HQ under "Use a different app" opened it **once** and offered no Always.
  **Settings → Home** (`am start -a android.settings.HOME_SETTINGS`) lists the Home apps with
  radio buttons; choosing Home HQ there saved it with `always="true"` in
  `/data/system/users/0/package-restrictions.xml`.
- **Disable any other Home app before choosing the default.** The saved choice includes the
  set of Home apps at that time. VTimes was disabled after choosing Home HQ; at the next boot
  Android showed the chooser again. Choosing Always then saved the set {Home HQ, Rootless
  Launcher}, and the following cable-free boots went straight to the dashboard.
- The stock `com.android.launcher3` is installed but was never offered as a Home app.

Hand test by the owner on the panel: the two-finger menu opened; **Open launcher** reached
Rootless Launcher; **Android settings** opened Settings; floating **Back** and **Dashboard**
worked from both.

### First load after Wi-Fi

The first loads ran while the date was still 2011 (WebView logged certificate `checkValidity`
warnings). After NTP corrected the date, Home HQ kept logging
`Retry still pending after 15000 ms, starting a new one` and showed "Can't reach the
dashboard", although Android had validated the network. `am force-stop com.wesbos.homehq`
and a restart loaded the dashboard within 20 seconds. This did not happen again on later
boots, when the date was already correct.

### Time zone

`service call alarm 3 s16 America/Los_Angeles` set `persist.sys.timezone`, and it stayed after
reboots with `auto_time_zone=1` (the frame has no mobile network to change it).

## Downloads used

Binaries are not included.

| Item | Source | SHA-256 |
| --- | --- | --- |
| Terminal Emulator 1.0.70 | [F-Droid archive](https://f-droid.org/archive/jackpal.androidterm_72.apk) | `95095176ca3fa421102352ecaea0fffb6d13527db023967a7cfa280f7bc05cb5` |
| Rootless Launcher 3.9.1 | [F-Droid, version 30911](https://f-droid.org/repo/amirz.rootless.nexuslauncher_30911.apk) | `7fa44d560dc4577374d45176220de2c0b00a71e09d6d148cdea4e0a52d38404a` |
| WebView 106 ARMv7 | [LineageOS prebuilt at 4b0ae494a7dd](https://raw.githubusercontent.com/LineageOS/android_external_chromium-webview_prebuilt_arm/4b0ae494a7dd/webview.apk) | `e2edc1f89ec1608b169da9e7ffc037190b70c7825f0be29694f4cae719980580` |
| Android command-line tools | [`commandlinetools-linux-15859902_latest.zip`](https://dl.google.com/android/repository/commandlinetools-linux-15859902_latest.zip) | `4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583` |
| CA roots | GTS Root R1, GTS Root R4, ISRG Root X1 from the URLs in the [SI006 report](si006-uhale.md#fonts-and-https-photos); DER hashes matched it | |

## Limits

- One unit, one firmware. Another VTimes listing may have a different board.
- Android stays 6.0 with shipped root and SELinux enforcing. WebView 106 and the added roots
  are compatibility updates, not current security support. Keep the frame on an isolated
  network and do not sign in to sensitive accounts on it.
- The dashboard is the repo's demo with mock data.
- What the VTimes app sends or accepts online was not examined.
- The `127.0.0.1:5037` listener and the `daemonsu` restart loop were not investigated further.
- No offline flash restore was tested.
