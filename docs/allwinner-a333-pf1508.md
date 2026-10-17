# PF1508 / AiMOR 6.0.100 (Allwinner A333, Android 15)

One unit, an Anna Bella 15.6" frame from [Amazon US](https://www.amazon.com/dp/B0H4VVFPG6?tag=webo080-20),
tested 2026-10-17 from macOS (Apple silicon, `adb` 37.0.0). Observations are separate from
guesses, and guesses are marked.

This is a different platform from the other AiMOR frames in this repo: Android 15, 64-bit, on an
Allwinner A333. Persistent USB ADB took about five minutes, through the factory test app from
[#135](https://github.com/wesbos/photo-frame-dashboard/issues/135). No SD card, network,
flashing or root was needed. Don't run the A33 (PF1007L) or A133 (PF1506) routes on it.

## Identify it

AiMOR Settings → About showed:

- Firmware version `YHK.F-null-A333-1506-D2048-C2-V10-PF1508-OS.0.20260725`
- Model `PF1508`
- AiMOR version `6.0.100`

Over ADB:

| Property | Value |
| --- | --- |
| `ro.build.fingerprint` | `Allwinner/a537_pro_arm64/a537-pro:15/AP3A.241105.008/26072516:user/release-keys` |
| `ro.build.display.id` | `PF1508_20260725` |
| `ro.hardware` / `ro.board.platform` | `sun65iw1p1` / `earth`. The build's resource overlays are named `a333_q83_arm64` |
| Android | 15 (SDK 35), `user` build, `ro.debuggable=0`, `ro.adb.secure=1`, verified boot `green` |
| ABI / kernel | `arm64-v8a` only / Linux 6.6.102 |
| RAM / storage | 2 GB (`MemTotal` 1,842,284 kB) / 16 GB free on a new unit |
| Display | 1920×1080 at 160 dpi. The Amazon listing says 1280×800 |
| WebView | `com.android.webview` 124.0.6367.219, the only provider |
| Ports | DC barrel jack for power and one USB-C port. No SD slot |

Guess: the fingerprint's `a537_pro_arm64` is a reused product name; the firmware string and
overlays say A333.

## Get ADB

Before the unlock, USB with a USB-A-to-C data cable (through a hub) showed `1f3a:4ee1`, product
`PF1508`, with one interface, `MTP`. No ADB. On macOS, the Image Capture helper holds that
interface.

1. Open AiMOR Settings → About. Tap **Model** repeatedly (about 10 times) until the
   "Open test app" password box appears.
2. Enter `YHK88888888` (from #135).
3. The test app on this firmware is `com.yhk.devicenewtest`, a Chinese grid of green test
   tiles, not the "IS CLOSED" screen from #135. Tick the small **adb调试** ("adb debugging")
   checkbox at the top right, under the MAC address.
4. Android asks "Allow USB debugging?" with the computer's RSA key fingerprint. Check
   **Always allow from this computer**, then **Allow**.

Avoid the bottom buttons 恢复出厂 (factory reset) and 清除测试数据 (clear test data). 退出 is Exit.
AiMOR brings its own main screen back after about 2 minutes without a touch, even over the test
app, so don't pause.

Afterwards USB shows `1f3a:4ee7` (ADB only), `persist.sys.usb.config=adb` and
`adb_enabled=1`. ADB came back on its own, without a new prompt, after each of four reboots.

The shell is `uid=2000(shell)`, not root. No root route was tried. With a `user` build and
verified boot `green`, `/system` can't be changed, so none of the WebView swaps or boot patches in
this repo apply. None are needed: WebView 124 is new enough for the dashboard.

Not tried: the `license.properties` card route from #104. With no SD slot, it would need a USB
stick on an OTG adapter, and it's unknown whether the USB-C port does host mode.

## What the vendor left on it

- **A saved factory Wi-Fi network**, `A8-20` (WPA2/WPA3), before any Wi-Fi setup. The frame
  would join it whenever it's in range. Removed with `adb shell cmd wifi forget-network 0`; it
  stayed gone after reboots.
- **AiMOR** (`com.efercro.os.aimor`, in `/system/system_ext/priv-app/AUMIOS_MoShare`) runs as the
  `system` user and was the Home app (`cn.nineox.robot.aimor.activity.NavigationActivity`). Its
  `CommunicationService` was running. Guess: that's the same vendor command channel as on the
  other AiMOR frames ([aimor-remote-root-shell.md](aimor-remote-root-shell.md)).
- While AiMOR is Home, it **turns Wi-Fi on at every boot**. `dumpsys wifi` names it
  (`WifiEnabled ... packageName=com.efercro.os.aimor`) about 22 s after boot.
- AiMOR's startup screen ("Welcome, aimor / AiMOR loading complete") has a **Recovery Mode**
  button. It's part of AiMOR, not Android recovery. Guess, from strings in the APK: it opens
  AiMOR's restore-from-backup screen. Not pressed.
- Other vendor packages: `com.yhk.qeota` (OTA, runs as `system` at boot), `com.softwinner.update`,
  `com.softwinner.runin` (Allwinner's factory burn-in app, runs at boot), `com.yhk.devicenewtest`
  (the test app), `com.yhk.rabbit.yhkages`.
- No listening TCP ports, no device owner, no accounts.

## A Home app that isn't AiMOR

There is no Launcher3 on this firmware. The only Home handlers are AiMOR and Settings'
`FallbackHome`, so install a launcher before anything else. KISS 3.26.0 from F-Droid worked:

```sh
# https://f-droid.org/repo/fr.neamar.kiss_224.apk
# SHA-256 da6ab0b1219ad3b5ee573698523fb15d60a918083e0843f94a03c1b12e1098c9 (matches F-Droid's index-v2.json)
adb install fr.neamar.kiss_224.apk
adb shell cmd package set-home-activity fr.neamar.kiss/.MainActivity
# undo: adb shell cmd package set-home-activity com.efercro.os.aimor/cn.nineox.robot.aimor.activity.NavigationActivity
```

`set-home-activity` works on this build (the HOME role moved from AiMOR to KISS). After a reboot,
the boot animation ended normally and KISS came up. The stuck boot animation from #118 didn't
happen.

With another app as Home, **AiMOR doesn't start at all**: no process after boot, so no
`CommunicationService`, no 2-minute return to its screen, and Wi-Fi stayed off after
`cmd wifi set-wifi-enabled disabled` and a reboot. Nothing was disabled to get there.

It still starts if something opens it. The kiosk's **Open launcher** starts the first other Home
app Android lists, and while AiMOR is enabled that's AiMOR, not the installed launcher. AiMOR then
ran its `CommunicationService` again and turned Wi-Fi on. Disabling it (next section) fixed that.

## Turn off the vendor apps

One package at a time, each with a 30-second wait (Android saves package state a few seconds
later; see #139) and a reboot with ADB connected. After each reboot: ADB back without a prompt,
the Home app in front, Wi-Fi still off, and an empty crash log.

```sh
adb shell pm disable-user --user 0 com.efercro.os.aimor      # AiMOR
adb shell pm disable-user --user 0 com.yhk.qeota             # vendor OTA, BOOT_COMPLETED receiver
adb shell pm disable-user --user 0 com.softwinner.update     # Allwinner updater
adb shell pm uninstall -k --user 0 com.softwinner.runin      # factory burn-in, see below
# undo: adb shell pm enable <package>; adb shell cmd package install-existing com.softwinner.runin
```

- Before disabling the OTA app, the framework was checked for a hook like the Joyhong C-2's (where
  disabling the updater crashed every activity). There's no `persist.sys.start_ac`, and the only
  vendor string in `framework.jar` is a patch in `android.webkit.WebViewFactory.getProvider`: it
  lets privileged processes (uid 0, 1000, 1001, 1002, 1027) load WebView when their package name
  contains `com.yhk` or `efercro`. Stock Android refuses ("For security reasons, WebView is not
  allowed in privileged processes"). It isn't a boot hook.
- `com.softwinner.runin` is flagged `PERSISTENT`, so Android started its process at boot even
  while it was disabled (idle: no CPU time, services or receivers, about 95 MB). Uninstalling it
  for user 0 stopped that. The APK stays in `/system`.
- The firmware uses A/B updates (`ro.product.ab_ota_partitions` includes `system`, `vendor` and
  `boot`). Developer options also has **Automatic system updates** on by default;
  `adb shell settings put global ota_disable_automatic_update 1` turns it off.
- Afterwards the Home handlers are the kiosk, KISS and `FallbackHome`, so **Open launcher** reaches
  KISS (checked by hand). No `efercro`, `yhk` or `softwinner` processes run.

## The way back without AiMOR

The test-app password screen lives in AiMOR, so with AiMOR disabled use Android's own Developer
options:

- Settings → About tablet → tap **Build number** 7 times. No "You are now a developer" message
  appears on this firmware, but it works (`development_settings_enabled` becomes 1). Developer
  options is slow to open.
- **USB debugging** is under Debugging. It was on, matching the test app's switch.
- Scrolling Developer options on the panel once turned USB debugging **off**, with no prompt (a row
  tap toggles it, and turning it off doesn't ask). Turning it back on there restored ADB with the
  saved key. Don't scroll that screen more than needed.
- **Disable adb authorization timeout** is off by default, so Android forgets the computer's key
  after 7 days without a connection. `adb shell settings put global adb_allowed_connection_time 0`
  keeps it.

A factory reset brings AiMOR and the test-app route back.

## The kiosk app on Android 15

The kiosk from `dashboard/kiosk` (built unchanged, targetSdk 23) doesn't install:

```text
Failure [INSTALL_FAILED_DEPRECATED_SDK_VERSION: App package must target at least SDK version 24, but found 23]
```

`adb install --bypass-low-target-sdk-block` installs it. The first launch shows Android's "This
app was built for an older version of Android" dialog; it didn't come back after a force-stop or
a reboot. After **OK**, the kiosk runs full screen and showed its "Connect to Wi-Fi?" screen (the
frame was offline).

Built with target SDK 28 instead (`--target-sdk-version 28` in `build.sh`, #169), it installs normally with no dialog. As Home it boots into the kiosk, but wait about 30
seconds after `--ez home true` and `set-home-activity` before rebooting: a reboot 2 seconds later
lost the Home alias and the frame booted into KISS. With the frame still offline,
the demo dashboard was served from the computer over `adb reverse tcp:8080 tcp:8080` and saved
with `--es url http://127.0.0.1:8080/`; it rendered full screen. Without Google Fonts (offline)
the large clock and titles overflow; not checked online yet.

This firmware has no navigation bar, so turn on the kiosk's navigation service:

```sh
adb shell settings put secure enabled_accessibility_services com.wesbos.homehq/com.wesbos.homehq.NavigationService
adb shell settings put secure accessibility_enabled 1
# undo: adb shell settings delete secure enabled_accessibility_services
```

Its **Back** and **Dashboard** buttons showed over KISS and Android Settings, and **Dashboard**
returned to the kiosk. By hand on the panel: the two-finger hold → **Android settings** → **Apps**,
then **Dashboard** back (README rule 9).

## Not tested

- The hosted dashboard over Wi-Fi.
- Network ADB, root, factory reset, OTA behavior, and whether the USB-C port does host mode.
- Exactly how many taps on **Model** open the password box.
