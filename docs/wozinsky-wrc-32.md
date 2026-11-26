# Wozinsky WRC-32 10.1" (Frameo, RK3126)

A record of one unit: a Wozinsky WRC-32 10.1" Frameo photo frame turned into a full-screen Home
Assistant wall panel. Host OS macOS. Observations are separate from guesses; nothing here is a
universal flashing guide. It is close to the [BIUFRAME](biuframe-setup-guide.md) and the other
RK3126 Android 6 frames in the [device index](devices.md) — treat that guide as the model, but
**`biuframe-setup.sh check` fails on this unit** (different fingerprint, model and partition
layout), so do not run its `apply`.

## Identity (one unit, read-only)

| Field | Value |
| --- | --- |
| Model / product | `WRC-32` (`ro.product.model`, `ro.product.device=rk312x`) |
| SoC / board | Rockchip RK3126 class (`ro.board.platform=rk312x`), `armeabi-v7a` |
| Android | 6.0.1, SDK 23, kernel Linux 3.10.0, SELinux **permissive** |
| Fingerprint | `rockchip/rk312x/rk312x:6.0.1/MXC89K/user.fyl.20170927.202757:userdebug/test-keys` |
| Build type | **userdebug / test-keys** (`ro.debuggable=0`, `ro.secure=1`) |
| WebView | `com.google.android.webview` **107.0.5304.36** stock — modern dashboards render fine, no WebView swap needed |
| Root | **`su -c id` → uid=0(root)**, context `u:r:toolbox:s0`; SuperSU-style `daemonsu` runs, **no manager app** (any app gets root with no prompt) |

## ADB and root

- ADB over USB. The tested unit was already authorized; whether an "Allow USB debugging" prompt
  appeared on first connect was not recorded. `adb devices -l` shows `product:WRC-32 model:WRC_32
  device:rk312x`.
- Root is the shipped `su` (no prompt). `pm disable`/`pm hide`/`pm grant`/partition remounts all
  work through `adb shell su -c '…'`.
- Android 6 note: there is **no `cmd` binary** (API 24+) and **no `pm set-home-activity`**, and the
  toolbox has **no `awk`/`pkill`**. Set the default launcher by removing the competing one (below),
  and kill a stuck process by PID (`su -c 'kill -9 <pid>'`).

## Vendor apps present (baseline)

| Package | What it is | Seen doing |
| --- | --- | --- |
| `net.frameo.frame` | Frameo vendor app; was the Home launcher | Listening on a local port and holding an outbound HTTPS connection (phones home) |
| `com.adups.fota` | Adups FOTA updater | Running at boot; Adups has a history of data exfiltration. Survives a non-root `am force-stop` |
| `com.DeviceTest` | Vendor device-test app | — |
| `android.rk.RockVideoPlayer` | Rockchip video player | — |

Only one third-party package was present besides these: the kiosk app (`com.wesbos.homehq`).

## Turning it into a Home Assistant panel (what worked on this unit)

The repo's [kiosk WebView app](../dashboard/kiosk/README.md) (`com.wesbos.homehq`) was installed and
pointed at a local Home Assistant dashboard:

```sh
# Install the kiosk (built with dashboard/kiosk/build.sh), then point it at Home Assistant:
adb shell am start -n com.wesbos.homehq/.MainActivity --es url http://<HA-IP>:8123/
```

WebView 107 renders Home Assistant's Lovelace UI without the WebView swap other RK3126 frames need.
Hold two fingers still for 1.5 s for the kiosk menu (launcher / Android settings / Wi-Fi / reload).

Make the kiosk the launcher and harden the frame (each step reversible; keep adb-over-USB as the
independent way back, and confirm Android Settings opens before disabling the vendor launcher):

```sh
# Reliability: lets the kiosk repair the navigation service and re-request network time after a power cut
adb shell pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS

# Make the kiosk the Home launcher. On Android 6 the default can't be set from the shell, so enable
# the kiosk's Home alias and disable the competing launcher (Frameo) to leave it the only one.
adb shell am start -n com.wesbos.homehq/.MainActivity --ez home true

# Shrink the attack surface (undo with pm unhide / pm enable)
adb shell su -c 'pm disable com.adups.fota; pm hide com.adups.fota; kill -9 $(pidof com.adups.fota)'
adb shell su -c 'pm disable net.frameo.frame'
adb shell su -c 'pm disable com.DeviceTest'
adb shell su -c 'pm disable android.rk.RockVideoPlayer'

# Verify: Home lands on the kiosk, no chooser
adb shell input keyevent KEYCODE_HOME
adb shell 'dumpsys window | grep mCurrentFocus'   # com.wesbos.homehq/.MainActivity
```

After this, the only external network talker observed in `/proc/net/tcp` was the kiosk WebView to the
Home Assistant host on `:8123`; the Adups outbound HTTPS connection cleared once its process was killed.

**Verified across a reboot** on this unit: it boots straight into the kiosk as Home (no launcher
chooser), the disabled/hidden vendor apps stay down, Wi-Fi reconnects on its own, and — because the
frame has no clock battery and boots at 1969 — the kiosk's `WRITE_SECURE_SETTINGS` time-nudge pulls
network time within a minute, after which the dashboard loads.

### Serving HA over HTTPS (optional)

Stock WebView 107 already trusts the Let's Encrypt roots, so a real cert "just works" with no
`/system` change. One unit ran the kiosk against HA over HTTPS by: enabling the HAOS **DuckDNS**
add-on's Let's Encrypt option (free cert, DNS-01, no port-forward), adding the **NGINX SSL proxy**
add-on in front of HA, and pointing the kiosk at `https://<name>.duckdns.org/`, with split-horizon
DNS resolving that name to HA's LAN IP. The kiosk never bypasses certificate errors, so the frame's
clock must be correct first (it self-syncs after boot, as above). Switching the kiosk to an HTTPS
origin requires logging in to HA once on the panel (new origin = fresh session).

## This frame cannot be made secure (read before use)

Same limits as the other RK3126 Android 6 frames:

- Any app can get root with no prompt; last security patch ~July 2016; SELinux permissive. The
  **Android version cannot be upgraded** on this board. "Securest possible" here means containment,
  not a newer OS.
- Keep it on a guest/IoT Wi-Fi network, isolated from workstations/NAS/management. Enforce egress at
  the router — a frame-local firewall is root-bypassable.
- Do not sign into a primary Google, Apple or bank account. Use per-frame, read-only credentials.
- Serve the dashboard so the frame never needs a primary account: a self-hosted page, or a local
  Home Assistant with a dedicated long-lived token.

## Not yet tested / unknowns

- Cold-power (full unplug) start; only a software `adb reboot` was tested, which persisted (above).
- Disabling Frameo did **not** drop saved Wi-Fi on this unit (it reconnected after reboot), unlike
  some RK frames where it does.
- Firmware backup (no `biuframe-setup.sh backup`, because the identity checks don't match this build).
- Whether a USB-C-to-USB-C cable enumerates (tested over the cable that was already working).
- PIR/motion sensor wake behaviour with Frameo disabled.
- Persistent network ADB (`persist.adb.tcp.port=5555`): set on this unit, but 5555 was not reachable
  after restarting `adbd` in the one attempt made; not confirmed.
