# PF1007L / AiMOR `20260529` on macOS: ADB already on, Home Assistant kiosk and the frame firewall

One PF1007 with the May `20260529` firmware shipped with root ADB already on over USB, like #8.
The whole setup ran over plain `adb` from an Apple-silicon Mac. It went from stock to a Home
Assistant dashboard in the Home HQ kiosk, with the boot fixes and the optional frame firewall, in
one session (2026-11-25). No FEL, boot patch or SD card was needed. One unit, one host. Everything
below was observed on that unit unless it is marked as a guess.

## Report

```text
About model / firmware:   PF1007 (ro.es_frame.product), Android model AEEZO
                          YHK.F-null-A33-1001-D1024-PF1007L-V10-1680.0.20260529
                          fingerprint AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260529:eng/test-keys
AiMOR version:            6.0.78
Ports (DC jack, or USB-C only): USB-C (DC jack not recorded)
Cable and port that gave USB data: first seen through a monitor's USB hub; backup and setup on a
                          USB-A to USB-C cable through a USB-C to USB-A adapter, direct Mac port
T3 USB IDs seen / adb devices output: 1f3a:1002 ("Android", "USB Developer"); adb devices listed
                          the unit as "device" at first plug-in
T3b network ADB result (port 5555): not tried
T4 sunxi-fel version output (or skipped): skipped (ADB already on)
T5 check-dump stage / chunks (or skipped): skipped
eMMC size in sectors:     30,777,344
Boot partition start sector: 172032 (bootloader 73728, env 139264, system 237568,
                          recovery 2400256, cache 2465792, UDISK 4366336)
Boot image SHA-256 (sector 172032, 31,028 sectors):
                          6c118dc1aa583797884c33cd3ac3796c72b2bd3a3f1fcafd1bf0982ae5f29e2c (stock)
Route used and result:    none: adb -d shell id = uid=0(root), SELinux Disabled,
                          persist.sys.usb.config=mass_storage,adb already set, survived reboots
Host OS:                  macOS 26.7.1, Apple silicon; adb 37.0.1 (Homebrew android-platform-tools)
First failed step and its exact output: none for access; see "Frame firewall" for one failed boot
```

## Before the session: the frame was already online

The owner had put the frame on the router's guest Wi-Fi before the session, with AiMOR running.
See [aimor-remote-root-shell.md](aimor-remote-root-shell.md) for why that matters.

- `svc wifi disable` turned Wi-Fi off (`wifi_on=0`, no `wlan0`).
- **Wi-Fi came back on after a power cycle** (replugging the USB-C cable). The frame rejoined the
  saved network about 3 minutes into the boot, with `wifi_on=1`. It was disabled again and
  checked before each backup chunk; it stayed off for the rest of the backup.
- After `com.efercro.os.aimor`, `com.yhk.qeota` and `com.DeviceTest` were disabled, Wi-Fi stayed
  off across a reboot. Guess: AiMOR turned it back on. The WebView swap happened between the two
  boots too, so this run does not isolate the cause.

Turn Wi-Fi off and expect it to come back at every boot until the vendor apps are disabled.

## Backup over ADB

The whole eMMC user area was read in 30 chunks of 512 MiB with `/sbin/busybox dd`
(BusyBox v1.18.3), as section 4 of the [setup guide](allwinner-a33-pf1007l.md#4-back-up-before-modifying-android)
recommends. Each chunk was read twice: once hashed on the frame with `busybox sha256sum`, once
streamed to the Mac with `adb exec-out` and hashed there. The named partitions (bootloader, env,
boot, recovery, misc, system) and `mmcblk0boot0`/`boot1` (4 MiB each) were read the same way.

- About 10 MB/s, so about 105 s per chunk with both reads. The run took 64 minutes on a direct
  Mac port.
- 29 of 30 chunks matched on the first try. The sizes added up to 15,758,000,128 bytes.
  bootloader, env and boot also matched the bytes at their offsets in chunk 0.
- **One chunk inside the mounted `/data` (`UDISK`) never matched.** On each of its three tries,
  the frame-side hash equalled the previous try's host hash. So consecutive reads agreed, and
  the contents changed in between because Android was writing to the live filesystem. It was
  kept and marked unverified. Expect this for any chunk inside a mounted read-write partition.
  The partitions that the later changes touch were all verified.

## After root

In this order, with Wi-Fi off until the vendor apps were disabled:

- **Rootless Launcher 3.9.1**, installed as a fallback. Its F-Droid signature and pinned
  SHA-256 were checked.
- **WebView 106.0.5249.126**, installed as in [section 6](allwinner-a33-pf1007l.md#6-upgrade-webview-before-using-the-kiosk).
  It was staged in `/data/local/tmp` and compared with the host copy. It was copied to
  `/system/homehq-new-webview` and compared again, and the trees were swapped. The live files
  were compared a third time and `/system` was remounted read-only. The stock tree (`webview.apk`
  and `oat/arm/webview.odex`) was kept at `/system/homehq-stock-webview`. `/system` had 405,824 KiB
  free beforehand.
- **Install the kiosk only after the reboot that follows the WebView swap.** Installed and started
  before that reboot, Home HQ crashed in `onCreate` (`WebViewFactory`, from `applyDebugFlag`),
  because the package manager still pointed at the old WebView. Android then showed the Home
  chooser. After the reboot, `dumpsys package com.android.webview` reported 106.0.5249.126, the
  logcat had no `dlopen failed` for WebView, and the kiosk ran.
- **Disabling the vendor apps before the kiosk was working.** Before disabling, the owner
  checked by hand that Rootless could reach Settings → Apps on the panel. Root USB ADB was a
  second way in. All three packages showed `enabled="2"` in `package-restrictions.xml` before
  the reboot and again after it. No vendor processes were running.
- **Home chooser.** As the [kiosk README](../dashboard/kiosk/README.md#start-at-boot) warns,
  tapping Home HQ in the list only wrote `always="false"`. Pressing Home again brought the
  chooser back with **Just once / Always**, and **Always** wrote `always="true"`.
- **No navigation bar.** There is no SystemUI, so the owner was stuck in Settings until the
  kiosk could run. The Home HQ navigation service was turned on in the accessibility settings
  on the panel. `enabled_accessibility_services` listed it, but `accessibility_enabled` stayed
  `0`, and the service did not bind until `settings put secure accessibility_enabled 1`.
- **Vendor background cleaner.** `kill_background_services=1` and `kill_background_services_list`
  was absent. `BackgroundManagerService` logged `package not in whitelist: com.wesbos.homehq`.
  The list was set to `com.wesbos.homehq,amirz.rootless.nexuslauncher`, the list semantics
  documented in the [January notes](allwinner-a33-pf1007l.md#vendor-background-cleanup-the-list-is-an-exception-list-on-this-build).
  Whether this is needed on this firmware was not tested.
- **CA roots were not needed** here. The dashboard is a local Home Assistant over plain HTTP.

## Vendor network settings left in Android

- **`captive_portal_server` was `status.eqoe.cn`.** On every Wi-Fi connect, Android's captive
  portal check went to that vendor-set host instead of Google's, and the vendor apps being
  disabled does not change that. `captive_portal_detection_enabled` was unset, which means on.
  Set `settings put global captive_portal_detection_enabled 0` if the frame doesn't need sign-in
  page detection.
- `ntp_server` was unset, so Android's own SNTP client uses its default pool. It was pointed at
  the router, which answered NTP (checked from the Mac with `sntp`).
- The kiosk has its own captive portal probe (`connectivitycheck.gstatic.com/generate_204`). It
  ran only when the dashboard failed to load, for example at boot before Wi-Fi was up.

## Home Assistant

- The saved URL is a local Home Assistant on `http://<ip>:8123/...`. On this network port 80 on
  the same host was a different web app, and the kiosk showed a `404 Not Found` page in dark
  text on a dark background, which looked like a black screen. Check the port from the computer
  before saving the URL.
- WebView 106 runs the current Home Assistant frontend (2026-11): login page, sections dashboard
  and tiles. With **Keep me logged in**, the session survived three reboots, each confirmed with a screenshot of the logged-in dashboard. Dark mode was set
  on the frame's own Home Assistant profile page. A dedicated non-admin user is used.

## Boot fixes and the frame firewall

`scripts/pf1007l-boot/install.sh check`, `apply` and `verify` passed with the defaults:
`WIFI_DEFER=1`, `POWER_FIX=0`, `MAC` empty (generated from the serial number), `NTP_SERVER` empty
(the router answered NTP), and `KIOSK=com.wesbos.homehq/.MainActivity`. In the verified boots,
Wi-Fi started at 43.3 to 44.6 s of uptime with the configured MAC, the clock was right and the
kiosk was in focus. `adb reboot` worked on this unit. macOS has no `timeout` command, so a
reboot wrapped in `timeout 30 adb reboot` silently does nothing; check that
`/proc/sys/kernel/random/boot_id` changed.

Then `FIREWALL=1`, `FIREWALL_ALLOW="<HA ip>:8123"`, `FIREWALL_DNS="<router ip>"` and
`IGNORE_IPV6_RA=1`. The router advertised IPv6 DNS servers, so `net.dns1`/`net.dns2` were IPv6
before, and the firewall blocks all IPv6. This was re-applied with `install.sh apply`.

- **Boot 1:** `FIREWALL: rules changed during activation; protection unverified`, then
  `FIREWALL not applied; Wi-Fi startup continues, use router isolation`. The rules were
  nevertheless still hooked in and correct: `FWF_*` was first in INPUT and OUTPUT for both
  families, with exactly the configured rules. The kiosk had connections only to Home Assistant
  on 8123. **The monitor was not running.** `frame-wifidefer.sh` starts `frame_firewall_monitor`
  only when `frame_firewall` succeeds, and the failure came from the final
  `frame_firewall_healthy` check (`frame-firewall.sh`, the line after the old-chain cleanup).
  That path returns 1 without removing the new hooks.
- **Boot 2** (no changes): `FIREWALL: applied: configured IPv4 TCP/DNS, DHCP/NTP; all non-loopback
  IPv6 blocked`. The hooks were first in both families, and the only connections were to Home
  Assistant on 8123.
- Guess: something else (probably `netd` around Wi-Fi start) changed INPUT or OUTPUT between the
  first verification and the final health check. Two boots are not enough for a rate.

So a frame can boot with the firewall rules active but unmonitored, while the log says they were
not applied. Read `iptables -S` and `ip6tables -S` instead of relying on that log line, and keep
router isolation in place, as [the boot-fix guide](pf1007l-boot-fixes.md#optional-frame-firewall)
says.

## Host notes (macOS)

- `brew install --cask temurin@17` needs `sudo`. `brew install openjdk@17` doesn't, and with
  `JAVA_HOME` set to it, `dashboard/kiosk/build.sh` built the APK with build-tools 34.0.0 and
  platform 34.
- `brew install --cask android-commandlinetools` refuses to install until a Java runtime is found.
