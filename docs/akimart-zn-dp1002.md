# Akimart ZN-DP1002 10.1-inch frame (SSA RK3326 board)

Investigated 2026-10-13. A record of one owner's unit, not a flashing guide.

**This unit is not the frame described in [PR #42](https://github.com/wesbos/photo-frame-dashboard/pull/42).**
That PR documents an Akimart ZN-DP1002 with a Rockchip RK3126, Android 6.0.1 and eMMC. This unit,
sold under the same name, has a Rockchip RK3326, Android 8.1 and logical NAND. Do not run PR #42's
script on it. Check `ro.build.fingerprint` before following any Akimart guide.

End result: Frameo and both vendor updaters disabled, the repo's
[kiosk app](../dashboard/kiosk/README.md) as HOME so the frame boots into the dashboard (served
from a LAN server), Rootless Pixel Launcher and Firefox behind it, and the floating
[Frame Home](../scripts/home-button/README.md) button. No flash write,
system remount or system APK edit was needed.

## Identity from ADB

| Field | Observation |
| --- | --- |
| Model / brand / manufacturer | `Frame` / `SSA` / `rockchip` (`ro.product.model` is **not** `ZN-DP1002`) |
| Platform / board | `rk3326` / `rk30sdk`, 4× ARMv8 cores, 1.512 GHz max |
| Android / API | 8.1.0 / 27, ABI `armeabi-v7a`, kernel 4.4.138 |
| Security patch | 2020-06-05 |
| Firmware | `SSA_Frame_20260420` |
| Fingerprint | `rockchip/rk3326_go/rk3326_go:8.1.0/OC/085013:user/release-keys` |
| Build flags | `ro.debuggable=1`, `ro.adb.secure=1`, SELinux permissive, verified boot `orange` |
| RAM / display | 976,904 KiB / 1280×800, 160 dpi |
| Storage | logical NAND `rknand0`, 60,555,264 sectors; `/dev/block/by-name` present |
| Root | shipped `/system/xbin/su`; syntax is `su 0 <cmd>` (`su -c` fails: `invalid uid/gid '-c'`) |
| WebView | `com.android.webview` 106.0.5249.126 in `/system/app/webview`, already, no swap needed |
| Frameo | `net.frameo.frame` v1.32.12, updated into `/data/app` |
| Vendor updaters | `com.adups.fota`, `android.rockchip.update.service` |

## Cables and ADB access

- The supplied cable runs from a wall adapter to USB-C and is power only.
- From a computer's USB-C port, a known-good Apple USB-C/Thunderbolt cable gave **no power and no data**:
  nothing changed on screen. A **USB-A to USB-C** data cable worked.
- Frameo Settings → About → Beta Program → ADB Access was on. It enabled **USB** ADB only. With it
  on, and after a reboot, TCP 5555 refused connections. A scan of all 65,535 TCP ports found only
  33413 open; that is Frameo's service, `adb connect` to it stays `offline`. This matches
  [PR #66](https://github.com/wesbos/photo-frame-dashboard/pull/66) (Rollei, RK3126).
- Over USB, the authorization prompt appeared on screen and was accepted.
- `adb tcpip 5555` over USB then opened network ADB until the next reboot. A second host's key
  needed its own prompt; `ro.adb.secure=1`, so network ADB here requires an approved key.

## Logical NAND partition map

From sysfs and `/dev/block/by-name`, in 512-byte sectors. Partitions 1–15 are contiguous.

| Node | Name | Start | Size |
| --- | --- | --- | --- |
| rknand0p1 | uboot | 16384 | 8192 |
| rknand0p2 | trust | 24576 | 8192 |
| rknand0p3 | misc | 32768 | 8192 |
| rknand0p4 | resource | 40960 | 32768 |
| rknand0p5 | kernel | 73728 | 65536 |
| rknand0p6 | boot | 139264 | 65536 |
| rknand0p7 | recovery | 204800 | **262144** |
| rknand0p8 | backup | 466944 | 393216 |
| rknand0p9 | security | 860160 | 8192 |
| rknand0p10 | cache | 868352 | 786432 |
| rknand0p11 | system | 1654784 | 3932160 |
| rknand0p12 | metadata | 5586944 | 32768 |
| rknand0p13 | vendor | 5619712 | 786432 |
| rknand0p14 | oem | 6406144 | 262144 |
| rknand0p15 | frp | 6668288 | 1024 |
| rknand0p16 | userdata | 6669312 | 53885919 |

Same partition names, order and NAND size as the [VESWWE DP100](veswwe-10.1.md), except recovery
is 128 MiB rather than 64 MiB, which shifts every later partition by 131,072 sectors. Do not reuse
the VESWWE offsets. `/system`, `/vendor` and `/oem` mount ext4 read-only; `/data` is ext4.

## Verified firmware backup

- Transport probe: a 4 KiB read of boot through `adb exec-out "su 0 dd ..."` arrived as exactly
  4,096 bytes and matched the on-device SHA-256. Unlike SuperSU on the VESWWE, this `su` does not
  translate LF to CRLF, so no base64 or `adb root` was needed.
- Boot starts with a Rockchip `KRNL` wrapper (`4b524e4c`), not `ANDROID!`.
- Capture: the initial 8 MiB of `rknand0`, then each partition node p1–p15 in 64 MiB chunks, so no
  seek exceeds 2 GiB. Every chunk returned its exact length.
- Result: 3,414,687,744 bytes (sectors 0–6,669,311); stream SHA-256 matched the gzip readback;
  no aligned 4 KiB block was all `0xCC`; independent on-device SHA-256 of all 16 regions matched,
  including OEM. Compressed size about 608 MiB. Over Wi-Fi ADB this ran at about 2 MiB/s.
- Entire 32 MiB boot partition SHA-256:
  `4ed777af252fcd537195fcda0cb8a4a59ffb3f88d543d210f04163d1045a891b`.

This is a logical firmware capture, not a physical NAND/OOB image or a userdata snapshot.
Restoration is untested.

## Setup performed (2026-10-13)

Each change was approved separately, after the backup, and read back.

| Change | Command | Undo |
| --- | --- | --- |
| Disable FOTA | `pm disable-user --user 0 com.adups.fota` | `pm default-state --user 0 com.adups.fota` |
| Disable Rockchip updater | `pm disable-user --user 0 android.rockchip.update.service` | `pm default-state --user 0 android.rockchip.update.service` |
| Install launcher | `adb install` Rootless Pixel Launcher 3.9.1 (SHA-256 `7fa44d56…404a`, F-Droid) | `adb uninstall amirz.rootless.nexuslauncher` (restore Frameo HOME first) |
| Install browser | `adb install` Firefox 157.0.1 armeabi-v7a (SHA-256 `a7682f65…f51c`, archive.mozilla.org) | `adb uninstall org.mozilla.firefox` |
| Launcher as HOME | `cmd package set-home-activity --user 0 amirz.rootless.nexuslauncher/com.google.android.apps.nexuslauncher.NexusLauncherActivity` | `cmd package set-home-activity --user 0 net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted` |
| Disable Frameo | `pm disable-user --user 0 net.frameo.frame` | `pm default-state --user 0 net.frameo.frame` |
| Home button | Frame Home installed, `appops set com.photoframe.homebutton SYSTEM_ALERT_WINDOW allow`, **Show Home button** tapped | `adb uninstall com.photoframe.homebutton` |
| Kiosk | `dashboard/kiosk` built with `DEFAULT_URL` set to a LAN server | `adb uninstall com.wesbos.homehq` (restore launcher HOME first) |
| Kiosk as HOME | Rebuilt with a second intent filter (`MAIN` + `HOME` + `DEFAULT`) on `MainActivity`, then `cmd package set-home-activity --user 0 com.wesbos.homehq/.MainActivity` | `cmd package set-home-activity --user 0 amirz.rootless.nexuslauncher/com.google.android.apps.nexuslauncher.NexusLauncherActivity` |

All three vendor packages started as `enabled=0` with running processes, and read back as
`enabled=3` with no process. Before Frameo was disabled, HOME resolved to the launcher and it was
the resumed, focused activity. After a normal reboot, all three stayed `enabled=3` with no process,
the launcher was HOME and focused, and Firefox started (`org.mozilla.firefox/.App`).

The framework draws no navigation bar. Frame Home's foreground service ran, and a tap on its
button from Firefox returned to the launcher. After a second normal reboot, its foreground service
and overlay window came back on their own, with the overlay permission kept. The kiosk rendered the repo's demo dashboard
(`vite build` output) full screen in WebView 106. Its first launch took 2 m 23 s to display; later
launches were not timed. `am start -W` hung on that first launch, a plain `am start` did not.

With the kiosk set as HOME, the Home key and Frame Home's button both open the dashboard, and
after a normal reboot the frame came up on the dashboard (owner observation; network ADB was not
reconnected for that boot). Rootless Pixel Launcher stays reachable from the kiosk's two-finger
hold → **Open launcher**, which skips the kiosk's own HOME entry.

## Second unit: Dxmart ZN-DP1002 (2026-10-15, macOS)

A second owner's frame, sold as **Dxmart** ZN-DP1002 10.1", has the same board. Host: macOS on
Apple silicon, USB ADB only.

- **Identity:** every field in the [identity table](#identity-from-adb) matched, including the
  fingerprint, `SSA_Frame_20260420`, the NAND size and the 128 MiB recovery.
- **Firmware:** the 32 MiB boot partition SHA-256 is the same `4ed777af…891b` as above.
- **Frameo:** v1.30.13, still the copy in `/system/priv-app`; it had not updated itself into
  `/data/app` yet.
- **Cables:** a USB-A to USB-C path through a hub gave power and data. USB-C to USB-C straight
  into the Mac gave neither.
- **Root:** `adb root` works (adbd runs as `u:r:su:s0`), and `su 0 <cmd>` works too.
- **Backup:** the same `adb exec-out "su 0 dd"` method over USB ran at about 11.5 MiB/s, about
  6 minutes for the 3.4 GB capture, checks included. Every check passed: chunk lengths, gzip
  readback, no `0xCC` blocks and on-device SHA-256 of all 16 regions.
- **Wi-Fi with the screen off:** the driver rejects scheduled scans (`wificond:
  NL80211_CMD_START_SCHED_SCAN failed`). With the screen asleep, Wi-Fi was enabled but stayed
  disconnected. `input keyevent KEYCODE_WAKEUP` brought the connection back within seconds. Prefer
  low brightness to sleeping the screen if the dashboard must stay online.
- **Screen turning off:** while Frameo was enabled, its sleep schedule
  (`net.frameo.frame/.feature.sleep_schedule.AScreenOffOverlay`) put the screen to sleep, even
  over the kiosk. This stopped once Frameo was disabled.
- **Kiosk as HOME without a rebuild:** the current kiosk has a `.Home` alias.
  `am start -n com.wesbos.homehq/.MainActivity --ez home true`, then
  `cmd package set-home-activity --user 0 com.wesbos.homehq/.Home`, made it HOME. ActivityManager
  reported the activity displayed after 5.3 s. The screen was asleep then; when it was woken about
  a minute later, the page had rendered.
- **Navigation:** the kiosk's own **Home HQ navigation** accessibility service gave the Back and
  Dashboard buttons. The owner enabled it on the panel and went to Settings → Apps and back before
  Frameo was disabled. Frame Home was not installed. The two-finger hold works, but only with
  both fingers completely still. The first few tries failed.
- **Pitfall, Frameo came back:** `pm disable-user` read back `enabled=3`, but after an
  `adb reboot` within about 20 seconds Frameo was `enabled=0` and running again. In
  `/data/system/users/0/package-restrictions.xml` its entry had no `enabled` attribute, while the
  updaters disabled earlier kept `enabled="3"`. The second try worked: disable, wait 30 s, check
  the file, `sync`, then `adb reboot`. Before you reboot, check the file:
  `adb shell "su 0 grep 'net.frameo.frame' /data/system/users/0/package-restrictions.xml"` must
  show `enabled="3"`. `svc power reboot` from the shell did nothing on this unit.
- **After a normal reboot:** Frameo and both updaters stayed `enabled=3` with no process. The
  kiosk was HOME and focused, the navigation service stayed on, and USB ADB stayed on. No TCP port
  was listening. The only outbound connections were the kiosk and Gboard
  (`com.google.android.inputmethod.latin`, to a Google address).
- **Hardware seen:** touchscreen `gslX680-d708`, accelerometer `sc7a30`, and a PIR motion
  sensor. The kernel log prints `pir_gpio_status`.
- **Boot animation:** `/system/media/bootanimation.zip` holds four PNG parts at 870×432 on
  white. `/oem` is a separate ext4 partition with no `media/` folder. `/system` mounts straight
  from `rknand0p11`, with no dm-verity device, although `ro.boot.veritymode` reads `enforcing`.

## Guesses, not confirmed

- Android probably writes `package-restrictions.xml` a few seconds after `pm disable-user`, and
  `adb reboot` does not wait for that write. That would explain the lost Frameo state above.
- AOSP 8.1 looks for `/oem/media/bootanimation.zip` before the `/system` one. Placing a custom
  animation there would then replace the boot graphic without editing `/system`. Not tried.
- The PIR sensor probably wakes the screen for Frameo's motion feature;
  which Android component reads it is not checked.
- The board is probably the same SSA RK3326 frame as the Runxion 10.1" in
  [PR #58](https://github.com/wesbos/photo-frame-dashboard/pull/58), which also uses `su 0 <cmd>`.
- The USB-C port probably lacks the CC pull-down resistors a USB-C host needs before supplying
  power, which would explain a USB-C to USB-C cable doing nothing.
- The Akimart listing likely ships more than one board, as other listings in the
  [device index](devices.md) do.

## Not yet checked

- Other factory apps' network behaviour. Keep the frame on an isolated network: Android 8.1 with
  a 2020 security patch and shipped root.
