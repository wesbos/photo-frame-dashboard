# Sandstrom SDPFAG1025 (Frameo)

One unit. Host: macOS, USB. The dashboard tests used a page bundled in the kiosk APK; Wi-Fi was not
tested.

Status: root ADB over USB with no flash writes. Backed up over ADB first (limits [below](#backup-read-only)).
No raw partition or system-file writes were made. **WebView 134 renders once its multiprocess mode is
turned off** ([below](#webview-renders-in-process)), so this repo's kiosk works. The kiosk (Home HQ) is
the Home app and came up after an `adb reboot`. Frameo is still installed and enabled.

This is a sibling of the [SDPFHD10W25](sandstrom-sdpfhd10w25.md): same SoC and Android build ID, but a
different model, build date, build tags, WebView and Frameo version. Don't reuse hashes, partition
offsets or the test-key WebView update from that page.

## Summary

| | |
| --- | --- |
| SoC | Allwinner A133 (`ro.sys.cputype` `QuadCore-A133`, `sun50iw10p1`, platform `ceres`) |
| Android | 12 (SDK 31, `SQ1A.220105.002`), security patch 2022-08-05, 32-bit userspace (`zygote32`, `armeabi-v7a`) |
| Fingerprint | `Frameo1/ceres_aw/ceres-aw:12/SQ1A.220105.002/20260629.093916:user/release-keys` |
| Build | `SDPFAG1025_V2.00`; description says `ceres_aw-eng`, fingerprint says `user` |
| RAM / storage | ~1 GB, `ro.config.low_ram=true`; 32 GB eMMC |
| Display | 1920×1200, `ro.sf.lcd_density` 210, `ro.vendor.sf.rotation` 270. Panel size not recorded |
| Frameo | `net.frameo.frame` 1.30.19 (versionCode 69880) |
| WebView | 134.0.6998.4 as found. Signer not checked |
| USB | VID:PID not recorded. Where it was bought: not recorded |
| ADB | `persist.sys.usb.config=adb`, key check on (`ro.adb.secure=1`) |
| Root | `adb shell` is root (`ro.secure=0`, `ro.debuggable=1`), SELinux permissive |
| Partitions | Slot `_a`, dynamic `super`, eMMC `mmcblk0`, file-encrypted `userdata` |

## Observations

### Getting ADB (macOS)

The Mac's key was authorized by toggling Frameo's ADB access. No `adb_keys` edits or flash writes were
needed. The authorization was still there after two `adb reboot`s.

A second, unknown key is authorized on this unit, as on the
[SDPFHD10W25](sandstrom-sdpfhd10w25.md#key-store-finding-record-not-a-removal-procedure). Its origin and
holder were not verified, and it was not removed. A holder of an authorized key may obtain root USB
access on this build.

### Root and `su`

- `adb shell` is root without any change. `getenforce`: permissive.
- `/system/xbin/su` is runnable by any user.

### SystemUI

`com.android.systemui` was disabled (`enabled=2`) after a reboot. It was not in the disabled list
before, and we did not change it.

### WebView renders in-process

As found, WebView ran with multiprocess on, and its renderers crashed the way they do on the
[SDPFHD10W25](sandstrom-sdpfhd10w25.md#webview-cant-render-anything-on-this-firmware):
`webview_zygote` can't reopen `/sys/kernel/tracing/trace_marker`, because the directory is mode `0700`.

Turning multiprocess off avoids the zygote:

```sh
adb shell cmd webviewupdate disable-multiprocess
adb shell dumpsys webviewupdate          # must say "Multiprocess enabled: false"
```

| | Before | After |
| --- | --- | --- |
| `dumpsys webviewupdate`, multiprocess enabled | `true` | `false` |
| `settings get global webview_multiprocess` | unset | `-2147483648` |
| `webview_zygote` | running | stopped |
| Rendering | renderers crash (kiosk not tried) | kiosk pages draw |

- Held through two `adb reboot`s with USB attached.
- A test page in the kiosk drew, a canvas animated at about 37 fps, and `localStorage` and touch worked.
  Chrome 134 user agent, viewport 1463×914 at device pixel ratio 1.3125. About 115 MB PSS, about 290 MB of
  RAM available. No new tombstones.
- The repo's demo dashboard, bundled in the APK: all seven sections drew, about 140 MB PSS, no new
  tombstones.

Undo: `adb shell cmd webviewupdate enable-multiprocess`, or
`adb shell settings delete global webview_multiprocess` and a reboot to go back to unset.

**What this costs** (from how in-process mode works, not observed here): it is a global setting, so it changes every WebView app on the frame. Pages run inside the
app's own process, without the isolated renderer sandbox, and a renderer crash takes the app with it. With
permissive SELinux and a `su` that any app can run, load only pages you trust.

### Kiosk menu and Open launcher

- The two-finger menu works by touch.
- **Open launcher crashed the kiosk at 346b712.** It started Frameo's Home activity without
  `FLAG_ACTIVITY_NEW_TASK`, and this Android 12 build threw `IllegalStateException: Can't change activity
  type once set`. The app then hung (ANR) until `adb shell am force-stop com.wesbos.homehq`.
- With `FLAG_ACTIVITY_NEW_TASK` added in `openLauncher`, and no other change, Open launcher shows
  Frameo. The owner confirmed this by touch.
- The owner also confirmed by touch, before the kiosk became Home, that menu → **Android settings** → Apps
  lists Frameo, and got back to the kiosk.

## Guesses (not yet confirmed)

- Frameo or the firmware probably disabled SystemUI. Not verified.
- The `trace_marker` crash looks like the same bug as on the SDPFHD10W25. Whether in-process mode also works
  there, or with its WebView 91, has not been tried.
- A WebView update, factory reset or OTA may turn multiprocess back on. Not tested.

## Backup (read-only)

Done over ADB as root before any change, streamed and gzipped in pieces. What was and wasn't checked:

- Every sector of the eMMC is covered across the files, with no `0xCC` filler. Byte counts, gzip and the
  host's SHA-256 list passed.
- Static partitions and the head of the disk matched a hash taken on the frame. Seven key
  partitions were read again after a reboot and matched.
- **Live partitions** (`metadata`, `misc`, `frp`, `env_a`, `env_b`, `private`, `media_data`, `userdata`) and the
  tail of the disk were checked for size and gzip only.
- `userdata` is file-encrypted and was read while mounted, over about 25 minutes and in a later boot than the
  other partitions. It can probably be restored only to this unit.
- **Restore is untested.** The frame dropped off USB during the first `userdata` read and later showed a fresh
  uptime; the cause was not established. The read was then completed in pieces.

## What was done (owner-approved, in order)

Historical one-unit record, not a setup procedure. These changes wrote app and settings data only.
Before reproducing them, meet the README backup rule, confirm the device identity and test the way back.

| # | Change | Command | Undo | Result |
| --- | --- | --- | --- | --- |
| 1 | ADB key expiry off | `settings put global adb_allowed_connection_time 0` | `settings delete global adb_allowed_connection_time` | Was unset. Reads back 0, also after `adb reboot` |
| 2 | WebView in-process | `cmd webviewupdate disable-multiprocess` | `cmd webviewupdate enable-multiprocess` | Pages render ([above](#webview-renders-in-process)) |
| 3 | Home HQ 1.2 with a bundled test page, then with the demo dashboard | `adb install -r` of a [`KIOSK_SITE` build](../dashboard/kiosk/README.md#a-page-bundled-in-the-apk-no-server), saved URL `http://127.0.0.1:8765/` | `adb uninstall com.wesbos.homehq` | Works. No permissions granted. Bundled from 346b712 with the Google Fonts links removed in a copy |
| 4 | Home HQ with the Open launcher fix | `adb install -r` | Reinstall the previous build | Open launcher reaches Frameo |
| 5 | Home HQ as Home | `am start -n com.wesbos.homehq/.MainActivity --ez home true`, then `cmd package set-home-activity com.wesbos.homehq/.Home` | `cmd package set-home-activity net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted`, then `am start -n com.wesbos.homehq/.MainActivity --ez home false` | Below |

Before the reboot for #5, the choice was already saved with `always="true"` (see
[Start at boot](../dashboard/kiosk/README.md#start-at-boot)). After one `adb reboot`, boot completed in 31 s:
Home HQ in front with the dashboard in ambient mode, ADB still authorized, WebView still in-process, key expiry
still 0, no new tombstones. Frameo's process was running.

Offline, the demo dashboard shows blank photo and camera images, fallback fonts and a demo clock that starts at
3:18 PM.

**Way back:** the kiosk's two-finger menu reaches Android settings and Frameo. Otherwise use USB ADB:
`adb shell am start -a android.settings.SETTINGS` (from the sibling guide, not run on this unit). Frameo was not disabled; before disabling it, test
Home and Settings by hand and keep USB ADB.

## Not tested

- Cold power-up, or any boot without USB attached to a Mac.
- Wi-Fi, and anything that needs the network.
- Long runs.
- Restoring the backup.

## Before Wi-Fi

- Use an isolated or IoT network. Root ADB stays on over USB, `su` is open to any app, the unknown ADB key is
  still authorized, and the security patch is from 2022.
- Turn off ADB key expiry first (#1 above). See the
  [SDPFHD10W25 notes](sandstrom-sdpfhd10w25.md#turn-off-key-expiry-before-the-frame-goes-online).
- Frameo is still enabled, and no updater has been disabled. Read the
  [SDPFHD10W25's updater findings](sandstrom-sdpfhd10w25.md#vendor-updater-and-ota-components); that
  component list was not checked on this unit.
