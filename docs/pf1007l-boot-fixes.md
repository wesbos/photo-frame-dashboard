# PF1007L: boot fixes (one MAC, correct clock, no freeze at Wi-Fi start)

These fixes make a rooted PF1007L boot straight to the kiosk, every time, even after a power cut.
They also apply to other AIC8800 / AXP223 A33 frames. The 30-boot test below is from one unit;
`install.sh check`, `apply` and `verify` have since passed on January, April `20260416` and May
units (see [Tested on](#tested-on)).

You must have root ADB (T7 in [pf1007l-start-here.md](pf1007l-start-here.md)) and a kiosk set as
the Home app. Follow the [repository rules](../README.md#rules-we-learned-the-hard-way): the owner
approves each write, and `install.sh` makes a backup before it changes anything.

**Install over USB ADB if you can.** These fixes replace `wpa_supplicant` and change how Wi-Fi
starts. If that goes wrong, network ADB goes with it, and on Route S that is your only ADB: you
would need the SD card to get back in. `install.sh check` warns when ADB is over the network.

## What each fix does

| Problem (observed) | Cause | Fix | Setting |
| --- | --- | --- | --- |
| A new Wi-Fi MAC at each boot, so the DHCP address and per-device firewall rules change | The AIC8800 has no stored MAC; the driver picks a random `88:00:33:77:xx:xx` at each load | A `wpa_supplicant` wrapper sets your MAC before Wi-Fi associates; a loop corrects it if the driver changes it later | `MAC` |
| Wi-Fi stays off until a power cycle: switched on, but no scan and no connection | A MAC change (the `MAC` loop in the row above) or anything else that takes `wlan0` down while Android starts the driver: `WifiStateMachine` logs `Failed to start driver after 2` and never retries; `wpa_cli status` shows `INTERFACE_DISABLED` | After 30 s in that state (or with no supplicant answering), toggle Wi-Fi as Settings would; if it stays dead, retry after 60 s, doubling to every 10 min. Skipped while `frame-nowifi` exists | always on |
| After a power cut the clock is 1969 and every HTTPS page fails ("date invalid") | No battery-backed clock. Android 6's SNTP client accepted a rate-limit reply (Kiss-o'-Death) from the router as the time, then waited 24 h | Restore the last saved time early in boot, then SNTP every 2 s until the server answers; save the time every 10 min | `NTP_SERVER` |
| The screen goes dark or freezes white about 30 s into boot, on most boots | The AIC8800 powers up while boot is at its busiest. The frame has no battery. The kernel log ends during the Wi-Fi firmware load or the first scan | Hide the driver from Android's boot-time load, then start Wi-Fi a few seconds after boot completes | `WIFI_DEFER` |
| (same) | The AXP223 starts with a 500 mA input limit (register `0x30 = 0x21`) and the kernel lifts it only at ~31 s | Write `0x63` (no limit) early in boot and keep it there. **Off by default:** only with a charger that supplies more than 500 mA, since frames on laptop ports browned out | `POWER_FIX` |
| About 1 boot in 10: connected to Wi-Fi but no IP address for ~36 s | The access point sent a group-key update right after the handshake; then no DHCP offer arrived. Reconnecting fixed it | If associated with no address for 2 s, disconnect and reconnect (about 4 s) | always on |
| Every DNS lookup takes 6-10 s | The network's IPv6 router advertisements listed a DNS server the frame could not reach; Android tried it first | Drop IPv6 router advertisements on Wi-Fi | `IGNORE_IPV6_RA` |
| "Select a Home app" chooser at boot instead of the kiosk | A power cut corrupted `package-restrictions.xml`; Android reset it and lost the "Always" choice | Start the kiosk if the chooser is showing. Also consider `pm disable-user` on other launchers | `KIOSK` |
| Network ADB is root with no authentication | `ro.adb.secure=0` on this firmware. Other devices on the same network reach it without passing the router | Allow TCP 5555 only from one network, on the frame itself. `ADB_ALLOW` only adds the firewall rule; it does not turn network ADB on (#172). Turning it on with `persist.adb.tcp.port` opens root ADB with no key check at every boot (see [T3c](pf1007l-start-here.md#t3c-temporary-adb-through-the-aimor-connection)) | `ADB_ALLOW` |

## Tested on

One PF1007L, firmware `astar_m86_8723cs-eng 6.0.1 MOB30R 20260529 test-keys` (May), Linux host,
October 2026, on a 2 A wall supply:

- Observed: 30 boots in a row (half after a simulated power cut: `service call alarm 2 i64 100000`,
  then reboot) reached the kiosk with the configured MAC, the right time, no error page and no Home
  chooser. Median 58 s from power-on to the page; boots that needed the DHCP reconnect took 63 s.
  These boots also ran a script that kept the boot animation on screen until the page loaded; it
  is not part of this set.
- Observed: installed with `install.sh apply` (this code, Home app set to a custom kiosk), 8 boots in
  a row (half after a simulated power cut) reached the kiosk at 58-63 s; one needed the DHCP reconnect.
- Observed: before the fixes, the same unit froze or went dark at Wi-Fi start on most boots; the
  hangs became more frequent over a day of repeated power cycles.
- Observed: on a laptop USB port the frame browned out even with the input limit lifted. Use a wall
  supply of 2 A or more.
- Observed: one freeze on the wall supply during development had no log, and did not happen again
  in more than 60 later boots. Its cause is unknown.
- Observed on other units, one or a few boots each: `check`, `apply` and `verify` passed on January
  `20260113` (#137, #164, #172, #179), April `20260416`
  ([macOS report](pf1007l-macos-20260416-report.md#boot-fixes),
  [Linux report](pf1007l-linux-20260416-hotspot-report.md#boot-fixes)) and May `20260519`
  ([#204](pf1007l-aimor-20260519-windows-adb-on-report.md#setup-that-worked) from Windows Git Bash,
  `check` and `apply` only; [#227](pf1007l-macos-20260519-12mhz-full-setup-report.md), Wi-Fi at 42.6 s;
  #240), with `WIFI_DEFER=1` and `POWER_FIX=0`.
  Wi-Fi started at 39.9 to 44 s uptime. Repeated and power-cut boots were not tested on most of them;
  the Linux `20260416` unit also reached the page by itself on a wall charger, and again after an
  unplug and replug.
- Observed before the fixes, the same freeze on other units: a January unit went dark about 30 s
  into a boot from a laptop port (#137); a January unit on a 5 W USB-A charger stayed black after
  the boot logo (#164); an April unit boot-looped on a Mac port when Wi-Fi started (#187).
- Observed: a TP-Link Deco (#190) and an Orange Livebox 6
  ([Linux hotspot report](pf1007l-linux-20260416-hotspot-report.md#boot-fixes)) did not answer NTP;
  `NTP_SERVER=time.google.com` worked there and on #137, #164 and #172.
- Observed on a second `20260529` unit (macOS, [report](pf1007l-macos-uk-20260519-20260529-report.md#unit-2-cpu-clock-during-the-backup-and-the-wi-fi-start-freeze)): before the fixes, 3 of 6 boots froze, on a powered dock's USB 2 hub port; each logged freeze ended at `Start app: 00130009, 4`, the AIC8800 calibration firmware start, at 27.7 s and 43.5 s. One boot from a direct Mac port passed the same line. With `WIFI_DEFER=1` and `POWER_FIX=0`, the first boot (direct Mac port) reached the kiosk, started Wi-Fi at 42 s and passed `verify`; not yet tested on the dock port.
- Guess: the Wi-Fi start freeze is a power problem (current spike with no battery), not a driver
  bug. The kernel log ends at different points of the Wi-Fi start, and the frame survived the
  same start when it ran after boot.

## Install

1. Copy the settings file and edit it:

   ```sh
   cp scripts/pf1007l-boot/frame-boot.conf.example scripts/pf1007l-boot/frame-boot.conf
   ```

   Each setting is described in the file. `frame-boot.conf` is ignored by git: it holds your MAC
   and network details. Leave `MAC` empty to get a stable address made from the serial number.
   For your own kiosk, set `KIOSK` to its activity.

2. Check, then install (the owner approves this write):

   ```sh
   scripts/pf1007l-boot/install.sh check
   scripts/pf1007l-boot/install.sh apply
   ```

   `apply` copies `install-recovery.sh`, `wpa_supplicant` and any old settings to
   `backups/pf1007l-boot/<time>/`, checks each file by SHA-256 after it is written, and leaves
   `/system` read-only. If earlier `sudo` runs left files in `backups/` owned by root, `chown`
   them back to your user first — one unit's `apply` failed until then (#110).

3. Power-cycle the frame (`adb reboot` hangs on many units), then:

   ```sh
   scripts/pf1007l-boot/install.sh verify
   ```

   **Pass:** the MAC is the configured one, the clock is right, the focus is your kiosk, and the
   log shows `Wi-Fi started`.

4. Reserve the MAC in your router's DHCP server.

## What changes on the frame

| Path | Change |
| --- | --- |
| `/system/bin/install-recovery.sh` | One line added at the end: `exec /system/bin/sh /system/bin/frame-boot-hook.sh`. The stock file is kept as `install-recovery.sh.bak` |
| `/system/bin/wpa_supplicant` | Replaced by a small wrapper script. The real binary is moved to `wpa_supplicant.real` |
| `/system/bin/frame-*.sh` | The fix scripts (in `scripts/pf1007l-boot/device/`) |
| `/data/local/frame-boot.conf` | Your settings |
| `/data/local/frame-lasttime` | The saved time |

`init` runs `install-recovery.sh` as root early in every boot (service `flash_recovery`). It kills
a service's background children when the main process exits, so the hook ends with `exec` of the
MAC loop, which never exits (from PR #6).

To keep Wi-Fi off at boot for debugging: `adb shell touch /data/local/frame-nowifi`.

## Undo

```sh
scripts/pf1007l-boot/install.sh uninstall
```

It puts back `install-recovery.sh` and `wpa_supplicant`, removes the scripts and settings, and
needs a reboot. The backups from `apply` are in `backups/pf1007l-boot/`.

## On the router

- **NTP:** if the frame uses the router for time and the router limits NTP clients (ntpd's
  `restrict default kod limited`), exempt the frame. A frame that retries quickly can stay
  limited. On pfSense: Services → NTP → ACLs, add the frame's address with only "No Modify",
  "No Peer" and "No Trap". That produces `restrict <frame IP> mask 255.255.255.255 nomodify nopeer notrap`.
- **NTP, no answer:** many home routers do not answer NTP at all. Then the clock sync never
  succeeds: `/data/local/frame-lasttime` is never written, and after a power cut the clock starts
  in 1969 again. Set `NTP_SERVER` to a public server, such as `time.google.com`. Before the 3 s
  limit on each try, a router with no NTP answer also left `nc` spinning at about 45 % CPU, which
  overheated one frame to 75 °C and made it hang.
- **IPv6:** if the network advertises an IPv6 DNS server that the frame cannot reach (for example
  a documentation address such as `2001:db8::`, left from a test), fix the router or set
  `IGNORE_IPV6_RA=1`.
- **Firewall:** the frame needs only DNS, NTP and the dashboard's HTTPS. An allow-list keeps the
  AiMOR app and any other app from reaching the internet.
