# IQUAL `10X1` (Frameo, RK3326, Android 11 Go): ADB, cleanup and kiosk

Record of one unit, set up on Linux (x86_64) on 2026-10-27 over a USB-A to USB-C data cable.
Observations are kept separate from guesses. Unique identifiers (serial, MAC, BSSID, IP
addresses, SSIDs) are left out.

**Result:** ADB over USB from Frameo's own Beta Program switch, **no root**, the repo's
[kiosk app](../dashboard/kiosk/README.md) set as HOME on a Home Assistant dashboard, the Adups
updater and the factory test app disabled, Frameo disabled, the time zone corrected, and a
rootless speed pass that took the kiosk from ~140% CPU to ~7% ([Performance](#performance)). No
partition was written, no `/system` file was touched. The Magisk route is an open question at
the end.

**The Frameo boot animation is handled by the kiosk, without root.** On this build the Frameo
animation runs above every window after a power cut, so the panel shows the splash while the
kiosk runs underneath. The kiosk's new `bootanim_exit` opt-in sets `sys.bootanim.exit` on every
start, and SELinux being permissive is what lets an ordinary app do that. Verified on a cold DC
power cycle: the splash cleared and the dashboard loaded with nothing attached. See
[the kiosk section](#5-dashboard-kiosk) and
[Frameo owns the Wi-Fi config and the boot video](#frameo-owns-the-wi-fi-config-and-the-boot-video).

**This is not the YIAISIGN `10X1` from [yiaisign-10x1.md](yiaisign-10x1.md).** That frame is an
RK3126 with Android 6.0.1 and a shipped setuid `su`. This one is an RK3326 with Android 11 Go.
The model string, the manufacturer `incar` and the `10X1` product name are identical, so match
the SoC and the fingerprint, not the name.

## How it relates to the known RK3326 frames

Same SoC family as the [Frameo `102k`](frameo-rk3326-s101.md) and the
[SSA 21-inch](ssa-frame-21inch-rk3326.md), but an **Android 11 Go** build with dynamic
partitions and a `super` partition. Do not reuse another RK3326 unit's offsets, and do not run
[`scripts/biuframe-setup.sh`](../scripts/biuframe-setup.sh) against it (that script checks for an
RK3126 fingerprint and refuses).

| | This frame | Frameo `102k` (S101) | SSA 21-inch |
| --- | --- | --- | --- |
| SoC | RK3326 | RK3326 | RK3326 |
| Android | 11 (SDK 30), Go | 11 (SDK 30), Go | 8.1 (SDK 27) |
| Partition scheme | raw NAND, dynamic `super` | raw NAND, dynamic `super` | raw NAND, plain `system` |
| Root | No (`su` present but unusable) | No | Shipped `su` that works |

## 1. Identify the frame

| Item | Observed value |
| --- | --- |
| Sold as | "IQUAL" 10.1" digital photo frame, Frameo app |
| Model / brand / manufacturer | `10X1` / `IQUAL` / `incar` |
| Platform / board / hardware | `rk3326` / `rk30sdk` / `rk30board`, 4× Cortex-A35, 32-bit userspace (`armv8l`) |
| Build ID | `YJ_3326S_10X1-202606011146` |
| Build fingerprint | `IQUAL/10X1/10X1:11/RP1A.201105.002/hxl20220314:user/release-keys` |
| Build tags | `release-keys`, `user`, `ro.secure=1`, `ro.debuggable=0` |
| Kernel | 4.19.193 (`#301`), built 2026-06-01 |
| Android | 11 Go: `ro.config.low_ram=true`, ABI `armeabi-v7a` |
| Security patch | 2022-01-05 |
| RAM | 991,252 kB (~968 MB), plus a 743,432 kB `zram0` swap device |
| Storage | Logical NAND `rknand0`, 30,277,632 blocks (~28.9 GiB). `/data` is 25 GB, 496 MB used |
| Display / density | 1280 × 800, 160 dpi |
| Touch | `gsl3673_800x1280` on `/dev/input/event1` (`getevent -pl`), multi-touch protocol B with `ABS_MT_SLOT` 0–10. The kiosk's two-finger hold opens its menu. |
| WebView | `com.android.webview` **113.0.5672.136** (newer than the dashboard's Chrome 106 target) |
| Frameo | `net.frameo.frame` v1.32.16 (an updated system app; the factory copy is v1.30.19) |
| Vendor apps | `com.incar.update` 5.28 (Adups FOTA, `PERSISTENT`), `com.DeviceTest` |
| Frameo location | `/system/priv-app/Frameo`, privileged system app, `UPDATED_SYSTEM_APP` (factory copy v1.30.19, updated copy v1.32.16) |
| SystemUI | `com.android.systemui` is **disabled on this unit out of the box** (`enabled=2`), but it is `PERSISTENT`, so its process still runs (~84 MB RSS) and draws nothing |
| Bootloader | `ro.boot.flash.locked=0`, `ro.boot.verifiedbootstate=orange`, `ro.boot.veritymode=enforcing`, `ro.boot.dynamic_partitions=true`, `ro.boot.storagemedia=nand` |
| Time zone | Ships as `America/New_York` |
| Trust store | ISRG Root X1 present (`6187b673.0`); ISRG Root X2 absent |

Because SystemUI is disabled, **no "Allow USB debugging?" dialog can ever render**, and the
kiosk gets a clean fullscreen with no status or navigation bar. The clock screen shows
1280 × 800 with `wm size` / `wm density` agreeing.

## 2. Get ADB

1. On the frame: **Frameo → Settings → About**. If there is no hidden entry under the four
   lines the About page shows (hardware brand, model number, Peer ID, Frameo version), look for
   **Beta Program** further down the same page. Turn **Beta Program** on; an **ADB access**
   switch then appears. Turn that on too. This is
   [Frameo's documented route](https://support.frameo.com/hc/en-us/articles/6126183308434--How-to-Enable-ADB-on-Your-Frame).
2. With the USB-A to USB-C data cable already connected, the frame re-enumerates from
   `2207:0007` (MTP only, no ADB) to `2207:0006` (ADB).
3. Accept the prompt on the frame if one appears. On this unit SystemUI is disabled, so expect
   `unauthorized` with no prompt instead. Toggling **ADB access** off and on with the cable in
   let the first host through; a second host key is untested.
4. `adb shell getprop ro.build.display.id` should print `YJ_3326S_10X1-202606011146`. Stop if it
   does not.

Cable notes: USB-C to USB-C did not enumerate on the Linux host. A USB-A to USB-C data cable
worked at once, same as the other Rockchip frames here.

### ADB over Wi-Fi

The frame's Developer options are not reachable (SystemUI is disabled), so Android 11's
Wireless debugging toggle and its pairing code are off the table. The older switch works and
survives reboots:

```sh
adb shell setprop persist.adb.tcp.port 5555
```

`persist.adb.tcp.port` is read by adbd at start, so after the next boot the frame listens on
5555 **and** keeps USB ADB working; both transports appear in `adb devices` at once. Because
`ro.adb.secure=1`, the listener still requires a key that this frame already trusts, so a
stranger on the LAN cannot connect just by finding the port. It is a plain, unencrypted
listener on every interface, though: treat it as a convenience on a trusted network, and clear
it (`setprop persist.adb.tcp.port ""`) if the frame moves to a shared one. With two devices
listed, `adb -s <ip>:5555 shell …` is needed, because plain `adb shell` fails with "more than
one device".

## 3. Root status: `su` exists but does not work

`/system/xbin/su` is `-rwsr-sr-x root shell`, 6,244 bytes, dated 2026-05-31. Every form fails:

```text
$ adb shell su 0 id
su: setgid failed: Operation not permitted
$ adb shell su -c id
su: invalid uid/gid '-c'
```

`ro.debuggable=0`, `ro.secure=1`, so `adb root` is not available either. The `sunxi`-style
"shipped root" route from the RK3126 frames does not apply.

The setuid bit is set and `/` is **not** mounted `nosuid`
(`/dev/block/dm-0 on / type ext4 (ro,dirsync,seclabel,nodev,relatime)`), so the failure is not a
mount option. What is measurable: `NoNewPrivs: 0`, the adb shell's capability bounding set is
only `CapBnd: 00000000000000c0` (`CAP_SETUID|CAP_SETGID`), app processes get the full set, and
`/system/bin/run-as` here has **no** setuid bit (`-rwxr-x--- root shell`). That points at the
adbd shell's `SECBIT_NOROOT`: `su` runs with `euid 0` but no capabilities, so its `setgid(0)`
gets `EPERM`. Whatever the exact cause, treat the shipped `su` as unusable and do not spend time
on it; a root shell needs a patched `boot`, not this binary.

**SELinux is `Permissive` on this unit** (`getenforce` prints `Permissive`), which is why the
`shell` user can write persistent properties here:
`setprop persist.sys.timezone …` and `setprop sys.bootanim.exit 1` both take effect. That is not
root and it does not unlock the block devices, but two problems that need root on other frames
(clock, boot splash) can be fixed from ADB on this one. Treat it as a property-write allowance,
not as a security hole to build on: an app on this frame could set the same properties.

## 4. Partition map

From `/dev/block/by-name` and `/sys/class/block/rknand0p*/{start,size}`, in 512-byte sectors.
Partitions 1–16 are contiguous. `/proc/partitions` reports the same sizes in 1 KiB blocks.

| Node | Name | Start | Size (sectors) | Size |
| --- | --- | --- | --- | --- |
| rknand0p1 | `security` | 8192 | 8192 | 4 MiB |
| rknand0p2 | `uboot` | 16384 | 8192 | 4 MiB |
| rknand0p3 | `trust` | 24576 | 8192 | 4 MiB |
| rknand0p4 | `misc` | 32768 | 8192 | 4 MiB |
| rknand0p5 | `dtbo` | 40960 | 8192 | 4 MiB |
| rknand0p6 | `vbmeta` | 49152 | 2048 | 1 MiB |
| rknand0p7 | `boot` | 51200 | 71344 | ~34.8 MiB |
| rknand0p8 | `recovery` | 122544 | 196608 | 96 MiB |
| rknand0p9 | `backup` | 319152 | 786432 | 384 MiB |
| rknand0p10 | `cache` | 1105584 | 786432 | 384 MiB |
| rknand0p11 | `metadata` | 1892016 | 32768 | 16 MiB |
| rknand0p12 | `fotocube` | 1924784 | 8192 | 4 MiB |
| rknand0p13 | `frp` | 1932976 | 1024 | 512 KiB |
| rknand0p14 | `baseparameter` | 1934000 | 2048 | 1 MiB |
| rknand0p15 | `super` | 1936048 | 4915200 | 2.34 GiB (dynamic: `system`, `system_ext`, `vendor`, `product`, `odm`) |
| rknand0p16 | `userdata` | 6851248 | 53703983 | ~25.6 GiB |

`su` is setuid but the shell user cannot read any of these block devices
(`dd if=/dev/block/rknand0p7` returns 0 bytes), so a partition dump needs loader mode, not ADB.

## 5. Dashboard kiosk

Build and install the [kiosk app](../dashboard/kiosk/README.md) as its README says. On this
Linux host the toolchain was unpacked under a scratch directory, with no system packages:
Temurin JDK 17, Android build-tools 34.0.0, platform 34, plus a `zip` shim on `PATH`
(`build.sh` uses `zip`, which was not installed).

```sh
adb install -r kiosk/build/homehq.apk
adb shell am start -n com.wesbos.homehq/.MainActivity --ez home true \
  --ez bootanim_exit true --es url <dashboard-url>
adb shell cmd package set-home-activity com.wesbos.homehq/.Home
```

`--ez bootanim_exit true` is explained below; it is what keeps the Frameo splash off the
screen after a power cut on this frame.

`set-home-activity` printed `Success` **while Frameo was still enabled**, unlike the second
`102k` unit, where it failed until Frameo was disabled. `am start` saved the URL and
`KEYCODE_HOME` then landed on the kiosk, confirmed with `dumpsys activity activities`.

`am start` with a running kiosk reports `Warning: Activity not started, intent has been
delivered to currently running top-most instance.` The URL is still saved.

### Clearing the vendor boot animation without root

This frame's boot animation does not stop on its own once Frameo is disabled (section 6), and
`sys.bootanim.exit` is the same property that `adb shell setprop sys.bootanim.exit 1` sets by
hand. The kiosk can set it itself, at every start, which is what makes the frame survive a power
cut with no computer attached:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity --ez bootanim_exit true
```

The opt-in is saved and retried once, 5 s after launch. It needs no root **because SELinux is
permissive here**, so the property service accepts a write from an app uid; where SELinux is
enforcing the same call is refused, logs a warning, and changes nothing. Verified on a cold DC
power cycle: the log shows `HomeHQ: Boot animation exit on`, `sys.bootanim.exit` goes from unset
to `1`, `init.svc.bootanim` goes to `stopped`, and the dashboard loads without any ADB command.

### Serving a Home Assistant dashboard

The dashboard used here is a Home Assistant panel on the LAN behind Caddy. Two host-side
details cost time and are worth checking before blaming the frame:

- **`https://<host>.local/...` does not load.** The frame's DNS servers are public
  (1.1.1.1/1.0.0.1), and `ping <host>.local` answers `unknown host`: Android 11 does not resolve
  mDNS `.local` names through its DNS resolver. Use the LAN IP, or add a DNS record on the
  router.
- **HTTPS with Caddy's internal CA does not load.** Caddy served an ECC certificate issued by
  `Caddy Local Authority - ECC Intermediate`, with a 12-hour validity and a single
  `DNS:` SAN. The kiosk cancels SSL errors on purpose (`onReceivedSslError` never calls
  `proceed()`), so the page stays on the error screen.
  Home Assistant's own listener answered on its plain-HTTP port and the kiosk loaded it, so the
  working URL here is `http://<frame-lan-ip>:8123/<panel>`. Cleartext is allowed by the kiosk's
  network security config. A login is still required: the panel loaded Home Assistant's
  "Welcome home!" form, and the WebView stored the session after signing in once on the
  touchscreen. The on-screen Gboard IME is present and works, so no keyboard has to be
  installed.

The page's own API calls are same-origin, so they follow whichever scheme and host the page was
loaded from. With the panel on `http://<ip>:8123`, do not expect the `https://` origin's
`localStorage` to be there.

## 6. What was changed

Every item is reversible from ADB. Nothing on a read-only filesystem was modified.

| Change | Command | Undo |
| --- | --- | --- |
| Home HQ kiosk installed | `adb install -r kiosk/build/homehq.apk` (`com.wesbos.homehq` 1.1, versionCode 2, debug-signed) | `adb uninstall com.wesbos.homehq` |
| Kiosk is HOME | `am start -n com.wesbos.homehq/.MainActivity --ez home true` then `cmd package set-home-activity com.wesbos.homehq/.Home` | `cmd package set-home-activity net.frameo.frame/net.frameo.frame.ui.activities.AWaitForDeferredInitCompleted` |
| Rootless Pixel Launcher 3.9.1 installed, as an escape hatch for the kiosk's two-finger menu | `adb install rootless.apk` (F-Droid `amirz.rootless.nexuslauncher_30911.apk`, SHA-256 `7fa44d560dc4577374d45176220de2c0b00a71e09d6d148cdea4e0a52d38404a`) | `adb uninstall amirz.rootless.nexuslauncher` |
| Adups updater disabled | `pm disable-user --user 0 com.incar.update` | `pm enable com.incar.update` |
| Factory test app disabled | `pm disable-user --user 0 com.DeviceTest` | `pm enable com.DeviceTest` |
| Frameo disabled | `pm disable-user --user 0 net.frameo.frame` | `pm enable net.frameo.frame` (then set it HOME again if wanted) |
| Time zone corrected | `setprop persist.sys.timezone Australia/Sydney` (see below) | `setprop persist.sys.timezone America/New_York` |
| Animations off (also turns on `prefers-reduced-motion` in WebView; see [Performance](#performance)) | `settings put global window_animation_scale 0`, same for `transition_animation_scale` and `animator_duration_scale` | set all three back to `0.5` |
| Hot apps AOT-compiled | `cmd package compile -m speed -f <pkg>` for `com.android.webview`, `com.google.android.inputmethod.latin`, `com.android.settings`, `com.android.permissioncontroller`, `amirz.rootless.nexuslauncher` | `cmd package compile --reset <pkg>` |
| Unused system apps disabled | `pm disable-user --user 0 <pkg>` for each package in the list below | `pm enable <pkg>` |
| Cached background processes capped at 8 | `settings put global activity_manager_constants max_cached_processes=8` | `settings delete global activity_manager_constants` |
| Kiosk JavaScript bridge on (the dashboard sets the backlight; see [Screen control](#screen-control)) | `am start -n com.wesbos.homehq/.MainActivity --ez bridge true` | `--ez bridge false` |
| BLE "always scanning" off | `settings put global ble_scan_always_enabled 0` (it was unset; Wi-Fi scan-always was already `0`) | `settings delete global ble_scan_always_enabled` |

The packages disabled for speed, all checked unused by a Wi-Fi-only kiosk:
`com.android.traceur`, `com.android.managedprovisioning`, `com.android.dynsystem`,
`com.android.localtransport` (these four were running after boot), `com.android.bluetooth`,
`com.android.bluetoothmidiservice`, `com.android.bips`,
`com.android.printservice.recommendation`, `com.android.musicfx`, `com.android.soundrecorder`,
`android.rk.RockVideoPlayer`, `com.android.egg`, `com.android.cellbroadcastreceiver`,
`com.android.wallpaperbackup`, `com.android.wallpapercropper`, `com.android.bookmarkprovider`,
`com.android.htmlviewer`, `com.android.companiondevicemanager`,
`com.android.hotspot2.osulogin`, `com.android.simappdialog`, `com.android.statementservice`,
`com.android.sharedstoragebackup`, `com.android.backupconfirm`, `com.android.storagemanager`.
Left alone on purpose: `com.android.phone` and `providers.telephony` (system services bind to
them even without a modem), `packageinstaller`, `permissioncontroller`, `externalstorage`,
`providers.*`, `networkstack*`, `captiveportallogin`, `wallpaperpicker`, Gboard, Settings and
SystemUI. All 29 disabled packages held across a reboot, and Wi-Fi reconnected.

### Performance

The CPU and GPU are already at their top clocks under load, so this frame cannot be made
faster by clocking. Measured over ADB on 2026-10-27 with the `solar-app` HA panel loaded:

| | Before | After |
| --- | --- | --- |
| `com.wesbos.homehq` CPU (kiosk + WebView GPU raster) | 120–145% | ~7% |
| WebView renderer CPU | 30–57% | ~7% |
| Load average | ~5–6 | ~1.7 |
| `MemAvailable` | ~370 MB | ~425 MB |
| App (`u0_*`) processes | 20 | 12 |
| Settings, cold `am start -W` | first draw +18 s (section 6) | 2.5–3.2 s |
| Power-on to kiosk process | n/a | ~25 s after `adb reboot`; `boot_completed` at 54 s |

Measured with `top` and `/proc/loadavg`, figures rounded.

**Most of the dashboard gain came from turning animations off, not from the debloat.** A
DevTools profile of the panel (kiosk launched with `--ez debug true`, then
`adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>`) showed the main thread busy
58% of the time at ~9 fps. JavaScript accounted for only ~12% of it; the rest was native
paint and raster, driven by the card's SVG SMIL animations (`<animateMotion>` flow dots,
`<animateTransform>`) and `backdrop-filter: blur`. The card turns those off under
`prefers-reduced-motion: reduce`, and WebView reports that preference when
`animator_duration_scale` is `0`. **WebView only reads the setting when it starts, so restart the
kiosk or reboot after changing it.** Any dashboard shown on this frame should keep its motion
behind `prefers-reduced-motion`, avoid `backdrop-filter`, and avoid always-on SVG animation; a
4× Cortex-A35 cannot raster those at 1280 × 800 without saturating.

Also seen: HA serves this WebView (Chrome 113) its legacy `frontend_es5` bundle, which is
slower than the modern build. The system WebView cannot be replaced without root:
`dumpsys webviewupdate` lists only `com.android.webview` as a provider, and the copy in
`/product/app/webview` is signed by a vendor key (`O=Micro-Star, OU=Research Center`,
SHA-256 `16af60cf…0d749`). WebView 113 already runs GPU rasterization, GPU compositing and OOP
canvas on the Mali-G31, so WebView flags have nothing left to enable.

Cromite System WebView 153.0.8010.37 (`arm64_SystemWebView.apk`, which also carries
`armeabi-v7a` libraries; package `com.android.webview`, signer `CN=CromiteOrg`) was tried on
2026-10-27. `adb install -r` fails with `INSTALL_FAILED_UPDATE_INCOMPATIBLE: … signatures do not
match`, and still fails the same way after `pm uninstall -k --user 0 com.android.webview`,
because the system package keeps its signature. Undo that step with
`cmd package install-existing com.android.webview`. The WebView keeps its `speed` dexopt state
after that.

`com.incar.update` and SystemUI are `PERSISTENT`, so `pm disable-user` does not keep their
processes down: `am force-stop com.incar.update` is followed by an immediate restart. Stopping
them for good needs root.

### Screen control

The panel ships at brightness 217/255 with `screen_off_timeout` at its maximum, so it stays bright
all night. Two rootless controls, both checked on 2026-10-27:

- **The dashboard dims it** through the kiosk's opt-in bridge (`--ez bridge true`,
  [kiosk README](../dashboard/kiosk/README.md#let-the-dashboard-dim-the-screen)).
  `HomeHQ.setBrightness(0.02)` showed up as `mScreenBrightnessOverrideFromWindowManager=0.02` in
  `dumpsys power`, and `-1` cleared it to `NaN`. A call from `https://example.com/`, loaded in the
  same WebView, changed nothing.
- **ADB turns it off.** `input keyevent KEYCODE_SLEEP` takes `/sys/class/backlight/backlight/brightness`
  to 0 (`bl_power=4`), and `KEYCODE_WAKEUP` brings the kiosk straight back. With
  `sys.bootanim.exit=1` already set, waking does **not** bring the Frameo splash back
  (`init.svc.bootanim` stays `stopped`, no `BootAnimation` layer). That's unlike the stuck
  animation in section 6, where a sleep and wake restarted it.

Brightness 0 is not off on this panel: the lowest setting drives the backlight at 10/255. Use
sleep for off. **Set brightness through `screen_brightness_float` (0.0–1.0), not the integer
`screen_brightness`.** After `settings put system screen_brightness 0`, putting the integer back
to 217 left the backlight at 10, because the float setting stayed at the minimum.
`settings put system screen_brightness_float 0.851` restored it, and the integer followed.

A system brightness set over ADB only shows while the dashboard's override is `-1`. When the
page has set its own level, that level wins until the page hands it back.

**Home Assistant over ADB.** This frame can't approve a new ADB key, so give Home Assistant a key
it already trusts. Copy the host's `~/.android/adbkey` and `adbkey.pub` to
`/config/.storage/androidtv_adbkey` and `androidtv_adbkey.pub` (the Android Debug Bridge
integration's default key path; modes 600 and 644). From a Docker install, `adb_shell` 0.4.4
inside the container connected to `<frame-ip>:5555` with that key and ran shell commands, with
nothing shown on the frame. That key now also lives on the HA host, so anything with
access to HA's config can reach a shell on the frame. Remove both files to revoke it.

### The way back on the panel

SystemUI being disabled does not break Settings. `am start -a android.settings.SETTINGS` reaches
`SettingsHomepageActivity` and the full list (Network & internet, Apps, Display, …) renders on
the panel; the first draw took **+18 s** on this 1 GB device, so give it time before declaring it
blank. The Wi-Fi list (`android.settings.WIFI_SETTINGS`) and the Gboard IME work, so a Wi-Fi
passphrase can be typed on the touchscreen. Use it through the kiosk's two-finger menu
(**Android settings**), or over ADB, and leave it as the fallback if the kiosk ever stops
loading.

Notes on the vendor apps:
- `com.incar.update` is Adups FOTA 5.28 from `/product/priv-app/IncarFota/IncarFota.apk`
  (SHA-256 `12fb5095379d1cd70c6bb3b7590e693c50ced1df7afffdc3d0fb47f6642876d9`). It holds
  `PERSISTENT`, `RECOVERY`, `REBOOT` and `CHANGE_OVERLAY_PACKAGES`. Its OTA endpoints are not
  readable in the APK's plain strings; the only host-shaped strings are a Firebase project and
  `google.com/iid`. It kept running as `u0_a88` after `pm disable-user`, like the Adups builds on
  other frames: expect it to stop only at the next reboot.
- `setprop persist.sys.timezone <zone>` works from the ADB shell on this build and **persists
  across reboots**, even though the same command is normally refused on other frames. The reason
  is SELinux: `getenforce` reports **Permissive** here (see section 3). `cmd alarm set-timezone`
  also works but only lasts until the next boot. The frame also ships
  `ro.frameo.default.timezone=America/New_York`, which is what the clock falls back to when the
  persistent value is missing.
- SystemUI stays disabled. That is the factory state here and is what keeps the kiosk fullscreen;
  do not "fix" it without a way to get the frame back.

### Frameo owns the Wi-Fi config and the boot video

Two things happen when `net.frameo.frame` is disabled on this build, and both are easy to mistake
for a broken frame:

1. **The saved Wi-Fi network is deleted.** `WifiService` logs `Remove settings for package:
   net.frameo.frame` and `WifiConfigManager: Remove all networks for app …` the moment the
   package is disabled, `cmd wifi status` goes to `Wifi is not connected` and
   `cmd wifi list-networks` prints `No networks`. Frameo provisioned the network, so the config
   belongs to it. Add it again so it belongs to Settings or to `shell`:

   ```sh
   adb shell cmd wifi connect-network "<ssid>" wpa2 "<passphrase>"
   ```

   The kiosk needs the network at boot, so do this **before** the next reboot, not after.

2. **The Frameo boot animation can outlive the boot, and only `sys.bootanim.exit` releases it.**
   `/system/bin/bootanimation` is a small loader for `/system/lib/libbootanimation.so`, a
   Rockchip build that carries `bootvideo` strings and reads both `service.bootanim.exit` and
   `sys.bootanim.exit`, plus `persist.sys.bootvideo.enable`,
   `persist.sys.bootvideo.showtime` and `persist.service.bootanim.displays`.

   With Frameo disabled the animation loops a Frameo logo and progress bar forever, in a
   `BootAnimation#0` layer above every window. `dumpsys window windows` showed no Frameo window,
   the kiosk was `mResumedActivity` and loading its page, yet every `screencap` returned the
   splash. `init.svc.bootanim=running`, `service.bootanim.exit=1`, and SurfaceFlinger had logged
   `sf_stop_bootanim`. The shell user cannot kill it (`kill -9` → `Operation not permitted`).

   Tested, and **none of these stop it**: a cold DC power cycle with Frameo disabled; leaving
   Frameo enabled but not Home; `persist.sys.bootvideo.enable=0` (the animation switches to a
   different frame set and keeps cycling). These **do** release it at once:

   ```sh
   adb shell setprop sys.bootanim.exit 1
   ```

   ...or letting Frameo draw its own UI, which is what happens on the factory configuration.
   So "Frameo disabled" and "kiosk as Home" cannot both be in effect at boot on this unit without
   something to set that property.

   **The kiosk now sets it itself**, through its `bootanim_exit` opt-in (section 5). Because
   SELinux is permissive, an ordinary app can write this property here; the kiosk does it on
   every start, and a cold DC power cycle confirmed the splash clears and the dashboard loads
   with nothing attached. No root is involved. The manual command stays as the fallback if the
   kiosk is not running:

   ```sh
   adb shell setprop sys.bootanim.exit 1
   ```

   A screen toggle (`input keyevent KEYCODE_SLEEP` / `KEYCODE_WAKEUP`) does not help; it only
   restarts the animation. The kiosk keeps its WebView session through all of this, so nothing
   has to be signed in again.

3. **`pm disable-user` is not durable within a few seconds.** Frameo was disabled, listed as
   disabled by `pm list packages -d`, and was `enabled=0` again after a reboot started seconds
   later. Disabling it again and waiting ~45 s held. The other two vendor apps stayed disabled
   across the same reboot. Wait half a minute before rebooting after any `pm` change.

## 7. Magisk: what is known, and what is missing

Not attempted. Root here would mean a Magisk-patched `boot` image on NAND, and this build is a bad
first candidate until the backup route is solved. What it would buy, and what stands in the way:

0. **What root would buy.** Less than it did before this session. The original reason was a
   late-start service script that sets `sys.bootanim.exit 1` after every boot; the kiosk now does
   that itself without root (section 5). What is left is convenience and belt-and-braces: a
   boot-time hook that does not depend on the kiosk starting, the ability to set the clock and
   URL without an app, and a shell that can read the NAND. None of those is needed for the
   dashboard.

   **For speed, root's usual levers are already used up** (see [Performance](#performance)). The
   `interactive` governor already holds all four cores at their 1512 MHz top under load, and the
   Mali GPU sits at its 520 MHz top, so switching to the `performance` governor gains nothing.
   Overclocking would mean a modified device tree in `boot`. Root would still buy three
   things: keeping the `PERSISTENT` updater and SystemUI processes down (~175 MB RSS between
   them), a newer WebView via a Magisk module so HA serves its modern bundle instead of
   `frontend_es5`, and zram and LMK tuning. Every one of those needs the stock `boot.img`
   first, and there is still no way to read it (items 1–4 below).

1. **No verified backup route yet.** The bootloader reports
   `flash.locked=0` / `verifiedbootstate=orange`, which usually means an unlocked Rockchip
   loader, but `ro.boot.veritymode=enforcing` means a patched `boot` alone may not boot. The
   shell user cannot read any block device, so the stock `boot.img` has to come from loader mode
   (`2207:310b`-class USB ID) with `rkdeveloptool`/`upgrade_tool`. `rkdeveloptool` builds cleanly
   from source on this host with the distro `gcc`, `make` and `libusb-1.0`; nothing else is needed.
2. **`adb reboot bootloader` is untested**, and whether this unit's U-Boot exposes fastboot at
   all is unknown. `fastboot` on the host is available; the frame's behaviour is not.
   `adb reboot loader` **was** tried: the frame dropped off USB within 3 s and presented no
   `2207:` or `18d1:` device for the next 80 s. It came back only after a DC power cycle. So
   either this build enters loader mode without a USB gadget, or it powered down. `rkdeveloptool
   ld` saw nothing, so no loader-mode read was possible.

   **The reset pinhole is the recovery key, not a maskrom strap.** Holding it while power is
   applied boots the AOSP recovery menu (section 7, next paragraph); it does not present a
   Rockchip USB device, and the menu has no maskrom entry. With `adb reboot loader` and
   `adb reboot maskrom` both ignored, the software routes and the one accessible hardware route
   are exhausted. What is left is opening the frame to find a maskrom button or test point, with
   the usual risk of shorting the wrong pad on NAND.

   `adb reboot recovery` **does** reach the AOSP recovery menu, and recovery's USB is alive:
   the frame enumerates as `18d1:d001` and `adb devices` lists it as `unauthorized`. Recovery
   runs adbd, but it reads its trusted keys from `/data/misc/adb/adb_keys`, and recovery does not
   mount `/data` on an encrypted device, so the host key that Android already accepts is out of
   reach. There is no prompt to accept a new key in recovery, so this is not a shell route. The
   menu does offer *Mount /system*; that does not expose `adb_keys`. The useful part is that the
   kernel USB gadget works outside Android, which is what fastbootd needs.

3. **`adb reboot fastboot` reaches fastbootd**, and that is the first usable non-Android mode on
   this unit. `fastboot devices` lists the frame within ~15 s, `lsusb` shows the fastbootd
   gadget (`18d1:4ee0`), and `fastboot getvar all` answers with `is-userspace:yes`,
   `dynamic-partition:true`, `partition-type:*:raw` for `boot`, `vbmeta`, `misc`, `uboot`,
   `trust`, `dtbo`, `recovery`, `baseparameter`, `super`, and logical `system`/`vendor`/... So a
   flash of `boot` and `vbmeta` is possible in principle, without loader mode.

   Two cautions from the first session. `fastboot getvar all` is a long sequence of getvars;
   piping it into `head` kills fastboot with SIGPIPE part-way through and **leaves fastbootd
   wedged** — afterwards `getvar` and even `fastboot reboot` hang with no response until the
   frame is power-cycled. Capture the whole output to a file instead.

4. **Readback is not available in fastbootd.** `fastboot fetch misc out.img` fails at once with
   `Unable to get max-fetch-size. Device does not support fetch command.` So fastbootd here is
   write-only: it can flash `boot` and `vbmeta`, but it cannot hand back a backup first. What it
   does report, captured in full:

   | Variable | Value |
   | --- | --- |
   | `unlocked` | `yes` (`secure:yes` as well, which is the factory flash-protection flag) |
   | `is-userspace` | `yes`, `dynamic-partition:true`, `slot-count:0` |
   | `max-download-size` | `0x10000000` (256 MiB) |
   | `partition-size:boot` | `0x22D6000` (36,528,128 bytes = 71,344 sectors) |
   | `partition-size:vbmeta` | `0x100000` |
   | `partition-size:misc` / `dtbo` / `trust` / `uboot` / `security` | `0x400000` |
   | `partition-size:baseparameter` | `0x100000` |
   | `partition-size:recovery` | `0x6000000` |
   | `partition-size:super` | `0x96000000` |

   The sizes match the partition table in section 4 exactly, and `fastboot reboot` returns the
   frame to Android in ~30 s. That makes fastbootd the flashing route once a backup exists.

5. **The Adups updater identifies itself as RK3566.** `ro.fota.platform=RK3566_11.0` and
   `ro.fota.oem=incartech3566_11.0`, while the device tree, `dmesg` and `ro.board.platform` all
   say RK3326 (`Machine model: Rockchip rk3326 863 rkisp1 board`, `SoC : 33260001`). Do not pick
   a loader or a firmware package from those FOTA strings. The updater stages a full package at
   `/data/media/0/incarupdate/update.zip`, but that directory does not exist on this unit, so
   there was no cached `update.zip` to extract `boot.img` from.

What is known: `boot` is `rknand0p7`, 71,344 sectors; `vbmeta` is `rknand0p6`;
`ro.boot.dynamic_partitions=true`; `super` is p15. The Magisk patcher would also need the
`vbmeta` flags handled with `--disable-verity --disable-verification` or an AVB-preserving patch.

Do not start a flash on this unit without a byte-counted, SHA-256-verified readback of at least
`uboot`, `trust`, `misc`, `dtbo`, `vbmeta`, `boot`, `recovery`, `baseparameter` and `super`.

## Open questions

- Whether **maskrom** is reachable at all. `adb reboot loader` dropped the frame off USB,
  `adb reboot maskrom` was ignored (straight back to Android), and the reset pinhole boots
  recovery rather than a Rockchip mode. Only a maskrom button or test point inside the shell is
  left, and that is the only path to the verified backup that would have to exist before a
  Magisk flash. Since the kiosk now clears the boot splash on its own, nothing is blocked by
  this any more; it matters only if root is wanted for its own sake.
- Whether a Magisk-patched `boot` boots with dm-verity enforcing, or whether `vbmeta` must be
  patched too.
- Whether a second computer's ADB key is accepted on this unit without toggling ADB access again.
- What Adups actually contacts when it is left enabled; only the APK was inspected, not traffic.
  Disabled, it still runs (`PERSISTENT`) and crashes on every connectivity change, because its
  `SystemActionService` is disabled with the package: 26 crashes in the first two minutes after a
  power cycle, none while the network is stable.
