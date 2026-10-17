# Dragon Touch Classic10 Charm (Frameo): root ADB over Wi-Fi and the WebView kiosk

Report from **one unit**, tested on **16–17 October 2026** using an **Apple silicon Mac,
macOS 27.0** with platform-tools 37.0.1. The owner bought it from
[Amazon US, ASIN B0GTLPX5LC](https://a.co/d/0elUZPxy). The listing identifies the
purchase, not a guarantee that another unit has this firmware.

**Verified result:** root ADB was reachable over Wi-Fi with no authorization prompt, and
the shell has full root capabilities. After a private, verified backup of the critical
partitions, the repository's native kiosk (`dashboard/kiosk`) was installed and runs the
hosted dashboard full-screen through the shipped WebView 106 — no browser, no WebView
swap, no boot patch, and nothing written outside `/data`. The kiosk is the frame's only
`android.intent.category.HOME` handler, so it comes up at boot (see
[the HOME finding](#no-app-on-this-unit-claims-home)).

## Identity and observations

| Item | Observed value |
| --- | --- |
| Model in properties | `Classic10 charm` |
| Firmware build | `Classic10 charm_A33M_20260323-1608_V01` |
| Android / SDK | `6.0.1` / `23` |
| Manufacturer / board / hardware | `joyhong` / `exdroid` / `sun8i` |
| Build fingerprint | `joy/astar_ococci/astar-ococci:6.0.1/MOB30R/20260323:user/test-keys` |
| CPU ABI | `armeabi-v7a` |
| Display / density | `1280x800` / `160` |
| Stock app | Frameo, `net.frameo.frame` v1.29.14 (60300) — **not** VPhoto |
| Vendor test app | `com.joyhong.test` v2.0.34 (the owner's "ADB mode" setting lives here) |
| Vendor updater | `com.waophoto.fota` |
| Stock WebView | `106.0.5249.126` — modern; the repo kiosk runs as is |
| ADB shell identity | `uid=0(root)`, context `u:r:su:s0`, full capabilities (`CapEff: ffffffffffffffff`) |
| SELinux | Permissive |
| Other | `/sbin/busybox` present; `com.android.systemui` ships **disabled** (no status or navigation bar); no VPhoto; `pm list packages -3` empty out of the box; `/system/xbin/su` present but not setuid (untested — the shell is already root) |

This is a different model from the
[Dragon Touch Modern10 Charm](dragontouch-modern10-charm.md) (VPhoto, WebView 44) and from
the [Frameo 102K](frameo-102k-a33.md), though all three are Allwinner A33 `astar_*` boards.
The chip was not physically inspected. The partition map matches the 102K's from
`bootloader` (p2, 32 MiB at sector 73728) through `recovery` (p9); `cache` is 256 MiB and
the partitions after it sit at different offsets. The eMMC user area is 30,777,344 sectors
(15,758,000,128 bytes) — the same size as the Modern10 Charm unit. There is no p4; a
2-sector `mmcblk0p3` sits at sector 1.

## ADB access

Throughout this session TCP port 5555 was open with `service.adb.tcp.port=5555` set, and
`adb connect <frame-ip>:5555` returned a root shell immediately — no authorization prompt,
and none could appear: `com.android.systemui` is disabled, so there is no UI to show one.
The same no-AUTH-over-Wi-Fi signature was reported for the Modern10 Charm and for the
Classic15 Pro (issue #146). After one owner-initiated reboot the connection came back the
same way: root, no prompt, same address, with the FOTA disable and the enabled
accessibility service intact. `persist.sys.usb.config=mtp,adb` suggests a USB gadget
config, but the only USB port observed is a USB-A receptacle, and a USB-A-to-USB-C cable
to the Mac enumerated nothing — the same result as the Modern10 Charm report. USB ADB was
not pursued further; Wi-Fi was enough.

**Security hand-off:** this is an unauthenticated root shell open to anyone who can reach
the frame on the network. Keep it on a trusted LAN, never port-forward it, and re-check
the ADB toggle in the vendor app (or block the port) before putting it on an untrusted
network.

## Backup

Before installing anything, the critical partitions were read over ADB and verified:
`bootloader`, `env`, `boot`, `system`, `recovery`, `misc`, `frp`, plus `mmcblk0boot0` and
`mmcblk0boot1` — checked for exact byte counts, SHA-256, gzip readback hash, and fresh
re-reads of each partition plus a 16 MiB sample 128 MiB into `system` (avoiding the mutable
ext4 superblock). All checks matched, and a second `system` sample read an hour later was
byte-identical, so the filesystem was not being written while running. `/sbin/busybox dd`
was used throughout, so the >2 GiB `dd` limit noted for the Modern10 Charm never applied.
Not captured: `UDISK` (`/data`), `cache`, and the small `metadata`, `private`, `empty`,
`alog` and `media_data` partitions — the owner-approved scope covered the static
partitions a restore would need, since the kiosk changes land in `/data`.

A pipeline trap worth recording: **this device's `adbd` appends busybox `dd`'s statistics
line to `adb exec-out` stdout** (`32+0 records in` / `32+0 records out`, 25–41 trailing
bytes depending on digit count). The payload is intact and the junk is strictly trailing,
but any exact-size `cmp` against the stream phantom-fails unless the stream is truncated
to the partition's exact size first (`… | head -c <size> | cmp - image`). Small partitions
"match" by accident because both sides carry the same tail; a sliced compare against a
clean range is where it bites. Trimming the saved images to their exact sizes and
re-verifying produced the matching hashes.

## No app on this unit claims HOME

The complete `dumpsys package` output contains **zero** `android.intent.category.HOME`
filters on this build — Frameo included — and `<preferred-activities />` in
`package-restrictions.xml` is empty. Frameo ships a `BOOT_COMPLETED` receiver
(`net.frameo.frame/.core.BootCompleteReceiver`) — that, not HOME, is how it starts itself
at boot. The boot "Welcome, <name>" screen the owner saw before the disable is gone after
a reboot (owner-confirmed; the receiver is the presumed source). The HOME intent
always resolves to the kiosk once the kiosk's alias is enabled. Frameo is disabled and its
data cleared on this unit (owner-approved; see the change table), so neither path runs.
Consequences:

- After installing the kiosk and running it with the `home` extra, it is the **only**
  HOME handler: no chooser ever appears and `am start -c android.intent.category.HOME`
  goes straight to the kiosk. (On the 102K, Frameo claims HOME and a chooser appears.)
- With `com.android.systemui` disabled there is no navigation bar, so the kiosk's
  accessibility **Home HQ navigation** service (floating Back/Dashboard buttons) is the
  only way back from other apps. Enabled with root:

  ```sh
  adb shell pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS
  adb shell settings put secure enabled_accessibility_services com.wesbos.homehq/com.wesbos.homehq.NavigationService
  adb shell settings put secure accessibility_enabled 1
  ```

  The service was confirmed bound (`dumpsys accessibility`) and the buttons visible in a
  Settings screenshot outside the kiosk. The two-finger gesture was confirmed by the owner
  on the panel, not by screencap — injected touch does not prove input here, and screencaps
  alone do not either (README rule 9).

## What was set up (all owner-approved writes)

| Change | Undo |
| --- | --- |
| `adb install -r dashboard/kiosk/build/homehq.apk` (built from this repo, `minSdk 23`) | `adb uninstall com.wesbos.homehq` |
| Dashboard URL saved and HOME alias enabled: `am start -n com.wesbos.homehq/.MainActivity --es url <url> --ez home true` (demo URL in this trial) | `am start -n com.wesbos.homehq/.MainActivity --ez home false` |
| `WRITE_SECURE_SETTINGS` grant, so the kiosk re-adds its navigation service itself | `pm revoke com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS` |
| Accessibility service enabled (commands above) | disable in Settings → Accessibility |
| `pm disable com.waophoto.fota` (updater disabled while the frame is online) | `pm enable com.waophoto.fota` |
| `pm clear net.frameo.frame` (wipes the setup name and all Frameo data) + `pm disable net.frameo.frame` (kills its `BOOT_COMPLETED` autostart). The boot "Welcome" screen is gone after a reboot — owner-confirmed | `pm enable net.frameo.frame` (data is not restored; re-setup re-asks the name) |
| `settings put global stay_on_while_plugged_in 7` (previous value `0`) | `adb shell settings put global stay_on_while_plugged_in 0` |

The dashboard was verified rendering full-screen by screenshot after install. The clock
was checked against the host twice (after install and after a reboot): correct date, time
and timezone both times — but the Modern10 Charm's clock-jump behaviour may only strike
occasionally, and this unit's `idle` time exceeding `uptime` after a reboot shows the same
underlying quirk, so a wrong date can still present as a silent calendar bug. The owner
has confirmed on the panel that the two-finger hold opens the kiosk menu and that the
dashboard comes back by itself after a reboot; the floating Back/Dashboard buttons were
additionally visible in a Settings screenshot. The vendor test app (`com.joyhong.test`)
remains installed and enabled; Frameo is disabled with its data cleared.

## Not tested

- Factory-reset behaviour and firmware restore (backups exist; restore is unproven).
- USB ADB through other cables, or the `mtp,adb` gadget config on a device-mode port.
- A second computer with a fresh ADB key (the no-key-check observation is one host only).
- Whether other units from this listing ship this firmware.
- Long-term behaviour beyond one owner reboot: FOTA staying disabled, the navigation
  service surviving force-stops of the kiosk (it did survive one reboot), and network
  ADB after a change of Wi-Fi network or DHCP address.
