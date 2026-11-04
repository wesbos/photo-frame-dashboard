# SI006 Uhale frame access notes

**Security update:** [issue #279](sammix-aw105-uhale.md) reports a SystemUI malware loader on
three Sammix AW105 units with the same `si006asb` product but different firmware. This guide's
disabled-app list includes the same payload package names. Disabling them does not establish
that their source is removed. This SI006 build has not been checked for that loader; keep a
suspected frame isolated and use the report's read-only checks. Do not disable SystemUI.

One 10.1-inch Uhale frame tested on Linux on 2026-10-11. **Root USB ADB, a verified
firmware backup, WebView 106, and the repo's dashboard are working.** Our locally
modified kiosk boots into Home HQ, and USB ADB reconnects without an SD card or
another RSA prompt. This is a record of this unit, not a universal SI006 setup script.

This frame uses Spreadtrum hardware. The
[PF1007L start guide](pf1007l-start-here.md) is for Allwinner A33 hardware; its FEL,
U-Boot, partition offsets, and boot patches do not apply to this unit.

For model `HSB`, firmware `F10_V1.01_20260826_195506`, see the separate
[HSB / F10 report](uhale-hsb-f10.md). That unit's hidden tap menus did not open;
USB keyboard input provided browser access before ADB. Its partition layout,
WebView and ADB authorization behavior differ from the SI006 described here.

The [VTimes VT01001](vtimes-vt01001.md) calendar is the same `si006asb` product under another
brand. This guide's WebView overlay and CA roots worked on it unchanged; the way in was the HSB / F10
USB keyboard route.

## Confirmed identity

| Field | Observed value |
| --- | --- |
| Model | `SI006` |
| Product / hardware | `si006asb` / `sp7731g_1h10` |
| Android / ABI | Android 6.0, SDK 23 / `armeabi-v7a` |
| Build fingerprint | `SPRD/si006asb/sp7731g_1h10:6.0/MRA58K/W25.22.5-11:user/release-keys` |
| Working USB mode | MTP + ADB, `1782:4002`, USB name `Spreadtrum` |
| Internal eMMC | 30,535,680 sectors of 512 bytes |

## Hardware read through ADB

| Component | Observed value |
| --- | --- |
| SoC | Kernel reports `sc7731`; board `sp7731gea_hdr`, platform `sc8830`. The board name suggests SC7731G, but the exact chip variant is not independently confirmed |
| CPU | Four cores present (`0-3`), ARM implementer `0x41`, part `0xc07` (Cortex-A7), maximum frequency 1,300,000 kHz |
| RAM | `MemTotal: 976420 kB` (about 954 MiB usable), consistent with a nominal 1 GiB device |
| GPU | SurfaceFlinger reports `ARM, Mali-400 MP, OpenGL ES 2.0`; GPU core count not exposed |
| Display | Android reports 1280 × 800 at approximately 60 Hz; hardware composer reports an 800 × 1280 panel mode with rotation |
| Storage | eMMC product `F312MB`, manufacturer ID `0x15`, 15,634,268,160 bytes (16 GB class) |

The CPU part ID is defined in the
[ARM Cortex-A7 reference manual, section 4.3.1](https://documentation-service.arm.com/static/5e8f089d88295d1e18d3b906).
Exact RAM package, Wi-Fi chipset, and display panel part number are not confirmed.

## What worked

1. In Uhale **Settings → About**, repeatedly tapping **System version** opened
   native Android Settings. The documented range is about 15–30 taps; the exact
   count on this unit was not recorded.
2. Tapping Android's **Build number** seven times enabled Developer options.
   USB debugging was enabled, but the frame stayed `unauthorized` on the PC.
   The generic debugging warning appeared; a computer RSA fingerprint prompt did
   not appear.
3. Installed **Terminal Emulator for Android 1.0.70** from a FAT32 SD card using
   **Settings → Storage & USB**. The APK came from the
   [author's download page](https://jackpal.github.io/Android-Terminal-Emulator/); its hash was
   not recorded. The F-Droid archive build
   ([`jackpal.androidterm_72.apk`](https://f-droid.org/archive/jackpal.androidterm_72.apk),
   1.0.70-rebuild) has SHA-256
   `95095176ca3fa421102352ecaea0fffb6d13527db023967a7cfa280f7bc05cb5`. Use that build and check
   the hash before installing.
   Running `su -c id` in the terminal returned `uid=0(root)`.
4. Put a local helper, `f.sh`, on that SD card and ran it with `su`. The root shell
   could read the card at `/mnt/media_rw/<SD-UUID>/f.sh`. This helper backed up
   `/data/misc/adb/adb_keys`, preserved existing keys, appended **this PC's public
   ADB key**, restored its SELinux label, and saved an undo script under
   `/data/local/tmp/`. It did not flash firmware or change network ADB settings.
   The PC's private key stayed on the PC.
5. With the frame in **MTP** USB configuration and the USB data connection
   re-established, `adb devices -l` changed to `device`.
   Both `adb -d shell id` and `adb -d shell su -c id` returned `uid=0(root)`.

The trust file is on internal storage, so the SD card is no longer needed for
an already established ADB connection; removing the card did not interrupt access.
An unexpected reboot initially lost authorization. Its cause and the persistent
fix are described below. The original helper remains a private local artifact
because it embeds the owner's public key; a reusable version must accept each
owner's key.

## Useful findings and failed attempts

- **`ro.adb.secure=0` did not mean USB ADB accepted an untrusted PC.** Authentication
  was observed in practice. An initial helper requiring this property to equal
  `1` stopped before making changes; the successful helper only added the USB
  trust key. Later inspection found TCP port 5555 already listening, and a fresh
  ADB connection received an `AUTH` challenge. A Wi-Fi shell was not tested.
- **PTP and ADB-only mode were unreliable on this unit.** Linux sometimes reported
  `no configurations` and error `-22`. Selecting **MTP** in Developer options
  restored enumeration. MTP file transfer itself remained unreliable; using the
  SD card avoided that transfer problem. Continuous kernel USB and ADB monitoring
  helped distinguish failed enumeration from an authorization problem.
- **Use the root-visible SD mount path.** After a network transfer to `/sdcard/f.sh`,
  `su -c 'sh /sdcard/f.sh'` reported no such file. A different storage view in the
  root shell is suspected, not proven. The direct `/mnt/media_rw/` path worked.
- **No Home/Back controls were visible.** Reopening the terminal APK through
  Settings, installing it again, and choosing **Open** worked after a restart.
- The alternate Uhale **Powered by** tapping sequence and code `770880` did not
  open a menu on this unit. Do not assume all Uhale hidden menus behave alike.

The hidden Settings and local-terminal approach was informed by the
[Quokka Uhale security assessment, Appendix J](https://go.quokka.io/hubfs/App-Intel/Technical_Uhale-Digital-Picture-Frame-Security-Assessment.pdf).

## Verified backup before system changes

The backup is stored privately on the host, not on the SD card:

- First 3,334,144 eMMC sectors: 1,707,081,728 bytes (1628 MiB), covering the
  firmware partitions before this unit's userdata partition.
- Both 4 MiB eMMC boot areas and the final 33 sectors containing the secondary GPT.
- Exact byte counts, SHA-256, complete gzip readback, and checks for `0xCC` filler.
- Independent re-reads matched the boot partition, recovery partition, and a
  16 MiB system sample.
- Original ADB key files, package state, build properties, WebView APK,
  framework resources, and APKs of disabled apps were also saved separately.

This excludes userdata and is **not a full backup of personal photos or app data**.
An offline flash restore has not been tested. Derive partition boundaries from
each device's GPT; these numbers are observations, not generic dump commands.
The old toolbox `dd` failed when seeking near the end of the 16 GB eMMC;
`toybox dd` read the secondary GPT successfully.

## Why ADB authorization disappeared

This unit's `/init.sc8830.rc` contains:

```text
on post-fs-data
    copy /system/etc/security/adb_keys /data/misc/adb/adb_keys
```

The factory source exactly matched the key file recovered after reboot. Adding
a public key only to `/data/misc/adb/adb_keys` therefore lasted until the next boot.

After verifying the backup, we preserved the original keys and added the host's
public key to **`/system/etc/security/adb_keys`** as well. The source file has
owner `root:root`, mode `0644`, and SELinux type `system_file`. The active data
file retains its Android ADB ownership, mode, and label. Readback matched the
prepared file; `/system` was remounted read-only. Never put a private `adbkey`
on the device. Keep both original files for undo.

The working USB configuration is MTP + ADB (`mtp,adb`). A local, device-specific
boot workaround reapplies it using the shipped `su`; this workaround is not in
the upstream kiosk. Controlled reboots with that workaround preserved USB access.
If the frame enumerates incorrectly after a restart, select **MTP** again in
Developer options. SELinux remains enforcing.

This firmware also had `service.adb.tcp.port=5555` in `/system/build.prop`.
Setting only `persist.adb.tcp.port=-1` did **not** prevent the service property
from re-enabling network ADB after reboot. With the original build properties
backed up, that one line was changed to `service.adb.tcp.port=-1`; ownership,
mode, and label were preserved, and readback matched. `adb usb` restarted the
daemon in USB-only mode. Restore the backed-up file to undo this change.
The final reboot reported both TCP properties as `-1`, with no port-5555
listener in either `/proc/net/tcp` or `/proc/net/tcp6`. USB ADB still connected.

The earlier unexpected reboot reported boot mode `wdgreboot`. Its trigger is
unresolved; no useful last-kernel log was available. It happened during read-only
hardware queries and should not be described as a proven fix for a watchdog bug.

## WebView: different from the other frames

The factory WebView is version **80.0.3987.132**, package
`com.google.android.webview`, re-signed by the vendor. The framework's
`config_webViewPackageName` also names `com.google.android.webview`. A normal
Google-signed update conflicts with the vendor signature; the other frames'
`com.android.webview` replacement recipe cannot be applied unchanged.

A locally built copy of the dashboard initially showed only its sidebar. WebView
debugging confirmed a JavaScript syntax error in the Chromium-106-targeted bundle.

The working solution on this unit:

1. Install the ARMv7 standalone `com.android.webview` 106.0.5249.126 APK as a
   normal data app. Package Manager extracts its native libraries, keeping the
   small system partition free.
2. Build the small [resource overlay](../scripts/si006-webview-overlay/) and put
   its APK in `/system/vendor/overlay/si006-webview-overlay.apk`, owned by root,
   mode `0644`, SELinux type `system_file`. It changes only
   `android:string/config_webViewPackageName` to `com.android.webview`.
3. Before reboot, `idmap --path` successfully mapped exactly that one resource
   against this unit's actual `framework-res.apk`. At boot, Android scanned the
   trusted `/vendor/overlay` directory and generated the resource mapping.
4. After reboot, logcat reported `Loading com.android.webview version
   106.0.5249.126`; the dashboard's user agent also reported Chrome 106.

The original WebView and `framework-res.apk` remain intact. To undo the provider
change, remove this overlay APK and reboot **before** uninstalling the new
WebView. Do not uninstall the selected provider while the overlay is active.

This follows Android 6's resource-based provider selection; see
[Chromium's system integration documentation](https://chromium.googlesource.com/chromium/src/+/d4afc97b7/android_webview/docs/aosp-system-integration.md)
and [Android 6 PackageManagerService](https://android.googlesource.com/platform/frameworks/base/+/android-6.0.1_r81/services/core/java/com/android/server/pm/PackageManagerService.java).

## Fonts and HTTPS photos

The old trust store rejected the dashboard's external fonts and photos with
`ERR_CERT_AUTHORITY_INVALID`. Three public roots were obtained from their
official CA repositories, matched against roots already trusted by the Linux
host, and added to `/system/etc/security/cacerts/` with mode `0644`, root ownership,
and the original directory's SELinux type:

| Certificate | Android filename | SHA-256 of DER certificate |
| --- | --- | --- |
| [GTS Root R1](https://pki.goog/repo/certs/gtsr1.pem) | `f013ecaf.0` | `d947432abde7b7fa90fc2e6b59101b1280e0e1c7e4e40fa3c6887fff57a7f4cf` |
| [GTS Root R4](https://pki.goog/repo/certs/gtsr4.pem) | `5acf816d.0` | `349dfa4058c5e263123b398ae795573c4e1313c83fe68f93556cd5e8031b3c7d` |
| [ISRG Root X1](https://letsencrypt.org/certs/isrgrootx1.pem) | `6187b673.0` | `96bcec06264976f37460779acf28c5a7cfe8a3c0aae11a8ffcee05c0bddf08c6` |

These files were absent on this unit. Check for filename collisions on another
device; do not overwrite an existing certificate based only on its short hash.
After restarting Home HQ, Archivo, Instrument Serif, and sample photos loaded
correctly. No certificate checks were bypassed. This is a targeted compatibility
update, not a complete modernization of Android's trust store.

## Dashboard, launcher, and disabled apps

Installed Rootless Pixel Launcher 3.9.1 as an escape route, Firefox 143.0.4 ARMv7,
and a locally modified build of the repo's Home HQ kiosk. The stock repository
uses a hosted dashboard over the frame's own Wi-Fi. **It does not require a
USB tether, a running PC, or an SD card for normal use.** USB was used here for
setup and diagnostics. See [the dashboard](../dashboard/) for its hosting setup;
set `DEFAULT_URL` in the kiosk to your own deployment when needed.

The kiosk build used JDK 17, Android build-tools 34.0.0, and platform 34. This host's
JDK 21 caused D8 compilation errors; JDK 17 built successfully.

This firmware showed no system navigation bar even with `qemu.hw.mainkeys=0`.
Opening Android Settings or the launcher's Home settings could leave the owner
without a way back. Until navigation controls are installed, keep USB ADB available
while configuring those screens. This returns to Home HQ:

```sh
adb -d shell am start -n com.wesbos.homehq/.MainActivity
```

Native kiosk controls and optional floating Back/Dashboard buttons were tested
locally and are proposed separately. Automatic startup and bundled web assets
were also local kiosk changes; this device report does not add those features
to the upstream app. Neither asset bundling nor USB tethering is necessary to
use the hosted dashboard.

After backing up their APKs and package state, these packages were disabled with
`pm disable-user --user 0` and force-stopped. Their files and data remain for undo:

```text
com.zeasn.frame
com.adups.fota
com.adups.fota.sysoper
com.fota.wirelessupdate
net.nault.nobel
com.sprd.systemupdate
com.cghs.stresstest
com.zediel.pcbtest
com.rainbow.xk4
com.mobile.applock.xk1
com.mobile.applock.xk3
```

For these previously enabled packages, undo is `adb -d shell pm enable PACKAGE`.
This list records package state, not malware removal. In particular, the three `xk` packages
also appear in the [Sammix SystemUI-loader report](sammix-aw105-uhale.md); on that firmware,
SystemUI could install payloads independently of the vendor photo app. Re-enabling a suspected
payload is not a recommended recovery step. Preserve evidence and containment first.
Do not disable shared Android services merely because they have a vendor-looking
name. Core Settings, SystemUI, networking, media, and storage services remain enabled.

Downloads used (binaries are not included):

| App | Source | SHA-256 of APK |
| --- | --- | --- |
| Rootless Launcher | [F-Droid, version 30911](https://f-droid.org/repo/amirz.rootless.nexuslauncher_30911.apk) | `7fa44d560dc4577374d45176220de2c0b00a71e09d6d148cdea4e0a52d38404a` |
| Firefox 143.0.4 ARMv7 | [Mozilla archive](https://archive.mozilla.org/pub/fenix/releases/143.0.4/android/fenix-143.0.4-android-armeabi-v7a/fenix-143.0.4.multi.android-armeabi-v7a.apk) | `af560738627d4efc9ace75e708fc48aad6a24c78ef43a89daca27e16ff3829f8` |
| WebView 106 ARMv7 | [LineageOS prebuilt at 4b0ae494a7dd](https://raw.githubusercontent.com/LineageOS/android_external_chromium-webview_prebuilt_arm/4b0ae494a7dd/webview.apk) | `e2edc1f89ec1608b169da9e7ffc037190b70c7825f0be29694f4cae719980580` |

## Limits and remaining work

On-device validation of the local kiosk build covered all seven tabs with injected
touch taps, loaded fonts and photos, and no JavaScript or network errors during
that check. Controlled reboots preserved the host key and disabled-app state;
the locally modified kiosk started automatically without an SD card. These tests
establish the device and WebView configuration, not upstream support for the
local kiosk features. WebView remote debugging is off for ordinary launches.

- The dashboard is the repo's **prototype with mock data**, including a demo
  clock starting at 3:18 PM. Long-press its sidebar clock for demo controls and
  **Real time**. Calendars, weather, chores, cameras, and home controls are not
  connected to the owner's services.
- Android remains **6.0**. No verified newer firmware for this exact board was
  found; another frame's ROM or a generic system image is not an established
  upgrade path. The old OS and root-enabled firmware remain unsuitable for
  sensitive accounts or exposure to untrusted networks.
- Firefox and WebView versions are chosen for compatibility, not current browser
  security support. They do not make this an up-to-date Android device.
- The watchdog reboot's cause and an offline firmware restore path remain untested.
- A reusable, parameterized initial ADB key-import helper would improve the guide.

Raw diagnostics, photos, keys, dumps, and vendor APKs are kept privately and
are not included in this report.
