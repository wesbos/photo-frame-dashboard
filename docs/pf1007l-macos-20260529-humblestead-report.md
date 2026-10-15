# PF1007L May firmware, Humblestead 10.1": recovery-window write on the larger eMMC, from macOS

One USB-C-only PF1007L sold as a **Humblestead 10.1" digital photo frame** (Amazon.nl ASIN
`B0GGB7LWX8`, model `HM-PF1007-BK-ZYF-DY`) running the May 2026 firmware reached persistent
**USB root ADB** on 2026-10-14 with the
[recovery-window boot write](pf1007l-macos-20260529-recovery-boot-write.md), from a Mac, with no
SD card. It is the first report we know of for that route on the larger **30,777,344-sector** eMMC.
The unit was then set up as a dashboard (WebView 106, Home HQ kiosk, boot fixes) and the vendor
packages were disabled. This is a unit report; it adds observations, not a new route.

Start with [the PF1007L checks](pf1007l-start-here.md) and follow the
[backup, approval, and privacy rules](../README.md#rules-we-learned-the-hard-way). Serial, MAC,
Wi-Fi details and the whole-disk hash are left out on purpose.

## Unit and host

| Item | Observed value |
| --- | --- |
| Listing | Humblestead 10.1", Amazon.nl `B0GGB7LWX8`, model `HM-PF1007-BK-ZYF-DY` |
| About model | `PF1007` |
| Firmware | `YHK.F-null-A33-1001-D1024-PF1007L-V10-1680.0.20260529` |
| AiMOR | 6.0.78 |
| Fingerprint | `AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260529:eng/test-keys` |
| Ports | USB-C only, a power button, a reset pinhole, a TF slot; no DC jack |
| eMMC | 30,777,344 sectors; `UDISK` starts at 4,366,336; boot is `mmcblk0p6` at sector 172,032 |
| Boot image SHA-256 (sector 172,032, 31,028 sectors) | `6c118dc1aa583797884c33cd3ac3796c72b2bd3a3f1fcafd1bf0982ae5f29e2c` (matches the table) |
| Stock ADB | Off: `1f3a:1000` "Android" ("USB Developer", 480 Mb/s), `adb devices` empty |
| Host | macOS 27.0.1, Apple silicon Mac Studio |

## Cable, power and USB observations

- The **boxed A-to-C cable is power-only**: no enumeration on a hub or on a direct port.
- A known-good A-to-C data cable on a **USB-A port on the back of the Mac Studio** gave
  `1f3a:1000` within 2 s. Power from that port survived boots and the Wi-Fi start; no brown-out.
- `uhubctl` can power-cycle the frame from that port (Apple USB2 hub, `ppps`), which matters
  because `adb reboot` hangs this unit.

## Route and result

Recovery-window write, as the guide describes: `recovery-pull.sh`, `recovery-patch-build.py`,
`recovery-patch.sh write`. The window lasted about 18 s; the `mmcblk0p6` node appeared, the original
boot image was confirmed by hash, the pushes took 5 s, the read-back equalled the patched image
(`8c05b34e…`; the patched hash depends on the host's zlib, as the table notes). Next boot:
`1f3a:1002`, `adb -d shell id` → `uid=0(root)`. No failed step. T3b (network ADB), T4 (FEL) and
T5 (`check-dump`) were skipped: the owner kept the frame off the network until the lock-down.

## After root: observations that may help others

- **Wi-Fi MAC on a TP-Link Deco mesh.** `install.sh apply` with `MAC=` empty derived a
  locally-administered address; a Deco mesh (XE75 + 2× BE85) timed out on authentication with it
  on every attempt, and the AIC8800 driver then reported `CTRL-EVENT-SCAN-FAILED ret=-16` until
  Wi-Fi was restarted. Setting `MAC=` to the frame's first-boot vendor-style address
  (`88:00:33:77:xx:xx`) fixed authentication.
- **One Deco node never authenticates.** The XE75 node specifically never completed
  authentication even with that MAC, while the BE85 nodes did. The 2 s DHCP rejoin in
  `frame-wifidefer.sh` then moved the frame to a BE85. The owner added a small watchdog that
  restarts Wi-Fi when there is no address for 45 s (not in this repository).
- **No UDP replies.** `toybox nc -u` and `busybox nc -u` received nothing on this firmware, not even
  a DNS answer from the gateway, so `frame-timesync.sh` never synced over SNTP. Its saved-time
  restore works once something else writes `/data/local/frame-lasttime`; Android's own NTP
  sync also works.
- **Home "Always" does not persist** (`preferred-activities`, `always="true"`) on this firmware.
  The `KIOSK=` chooser guard in the boot fixes handled it.
- `input keyevent KEYCODE_HOME` does nothing; `am start` of the launcher works.
- **Memory.** Home HQ with WebView 106 uses 66 MB on a simple page and 83 to 90 MB with three
  screens open over a day; no swap needed.
- **AiMOR lock-down.** With `com.efercro.os.aimor`, `com.yhk.qeota` and `com.DeviceTest` disabled
  (`pm disable`), `netstat` on the frame shows nothing on port 7806 across power cycles.
