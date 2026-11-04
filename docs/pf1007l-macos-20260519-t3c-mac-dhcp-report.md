# PF1007L / AiMOR May 2026 (`20260519`): T3c with the Mac as temporary DHCP and DNS server

This PF1007L reached persistent root ADB over USB with
[T3c](pf1007l-start-here.md#t3c-temporary-adb-through-the-aimor-connection) and
`persist.sys.usb.config`, with no boot or system write to get access. Neither the router nor the
frame could change DNS, so for a few minutes the Mac handed out DHCP leases on the home network
itself, with its own address as the DNS server. No second network interface, hotspot or uplink was
needed.

**One unit, tested once.** Run T1 to T3b on your own unit first, and follow the
[T3c procedure](pf1007l-20260410-network-adb.md) and its identity checks.

## Unit report

```text
About model / firmware: PF1007L / YHK.F-null-A33-1001-D1024-PF1007L-FL-AIMOR-OS.0.20260519
AiMOR version: 6.0.78
Ports: USB-C only
Cable and port that gave USB data: USB-A to USB-C cable into the USB-A port of a bus-powered
  USB 3 hub on the Mac (USB-C ports only). The first plug-in showed no USB device at all; after
  replugging, the frame enumerated as 1f3a:1000
T3 USB IDs seen / adb devices output: 1f3a:1000 ("Android" / "USB Developer", mass storage
  interface only), adb devices empty
T3b network ADB result (port 5555): connection refused
T4 / T5: skipped
eMMC size in sectors: 30,777,344
Boot partition start sector: 172032
Boot image SHA-256 (sector 172032, 31,028 sectors):
  9a6e2456952f3dc2b99e64ea021321397bdc824364b5c8b42f503f847261630a (matches the table)
Route used and result: T3c with the Mac as temporary DHCP + DNS server (dnsmasq), then
  persist.sys.usb.config=mass_storage,adb: root ADB over USB after every power cycle
Host OS: macOS 14, Apple silicon
First failed step: none
```

## Why this route

- **The frame's Wi-Fi screen only asks for the password.** No static IP, no DNS field, no
  **Modify network**, as in the [macOS T3c report](pf1007l-macos-20260519-t3c-report.md).
- **The router could not override DNS.** A Sagemcom F@st 5670 (the MásMóvil/Yoigo router in Spain):
  **LAN → DHCP** has only the on/off switch, the pool, the lease time and IP reservations. There is
  no DNS server field and no local host record.
- The [Linux hotspot route](pf1007l-linux-20260416-hotspot-report.md) and
  [#245](https://github.com/wesbos/photo-frame-dashboard/pull/245) (macOS Internet Sharing with a
  `pf` redirect) need the computer to run a separate network, which needs a second interface or
  uplink. This Mac had only its Wi-Fi on the home network.

The frame gets its DNS server from DHCP. If the Mac answers DHCP, the frame uses the Mac as DNS,
and only the vendor hostname has to be redirected.

## How it ran

1. `brew install dnsmasq`. Checked that nothing listened on UDP 53, TCP 53, UDP 67 or TCP 7806,
   that the macOS firewall was off, and that a small pool at the top of the router's range was
   unused (no ping or ARP replies). Ran `test-protocol.py`, `test-dns.py` and
   `server.py --dry-run`; all passed.
2. Wrote this config (example addresses: router `192.168.1.1`, Mac `192.168.1.133`) and checked
   it with `dnsmasq --test -C <file>`:

   ```ini
   interface=en0
   bind-interfaces
   listen-address=192.168.1.133
   except-interface=lo0

   # Forward everything to public resolvers, except the two AiMOR command hosts.
   no-resolv
   no-hosts
   server=1.1.1.1
   server=8.8.8.8
   address=/imsconnect.efercro.com/192.168.1.133
   address=/iwsconnect.efercro.com/192.168.1.133

   # Small pool outside the addresses already in use. Not authoritative, so it does not NAK
   # other devices' existing leases.
   dhcp-range=192.168.1.240,192.168.1.249,255.255.255.0,1h
   dhcp-option=option:router,192.168.1.1
   dhcp-option=option:dns-server,192.168.1.133
   dhcp-leasefile=<private dir>/dnsmasq.leases
   pid-file=<private dir>/dnsmasq.pid
   log-facility=<private dir>/dnsmasq.log
   log-dhcp
   ```

   Both hostnames point at the Mac, so AiMOR could not reach either vendor host during the
   session. `dnsmasq` forwards every other name, so any other device that took a lease in that
   window still resolved normally.
3. Started it with `sudo dnsmasq -C <file>`, then turned off the router's DHCP server for the
   session. Checked `dig @192.168.1.133 imsconnect.efercro.com` (the Mac) and an unrelated name
   (a public address).
4. The frame joined Wi-Fi and took a lease from the pool. The lease file gave its address for
   `--frame-ip`. TCP 5555 was refused (T3b).
5. Started `server.py --bind <mac-ip> --frame-ip <frame-ip> --seconds 600`. AiMOR connected
   within seconds, with no Wi-Fi toggle: `received_frame 110009`, then
   `runtime_adb_command_sent`. TCP 5555 opened right after.
6. Identity checks passed: `uid=0(root)`, `sun8i`, Android 6.0.1,
   `AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260519:eng/test-keys`.
7. `setprop persist.sys.usb.config mass_storage,adb`. The frame showed up as an ADB `device` over
   USB straight away, and `adb -d shell id` returned root.
8. Cleanup: forgot the Wi-Fi network on the frame **before** restoring the network, turned the
   router's DHCP back on, stopped `dnsmasq` (`sudo kill $(cat <pid-file>)`), then power-cycled the
   frame. USB ADB came back as root, with no `:7806` connection.

Forgetting the network first matters. Otherwise the frame renews its lease from the router later,
gets the router's DNS, and AiMOR reaches the real vendor server again before T8 is done.

## Persistent USB ADB

`/data/property/persist.sys.usb.config` already existed and held `mass_storage` (12 bytes). After
`setprop persist.sys.usb.config mass_storage,adb` it held `mass_storage,adb`, and USB ADB came
back as root after every power cycle. Undo: `setprop persist.sys.usb.config mass_storage`.

## Backup

Over USB ADB, with `/sbin/busybox dd` (BusyBox v1.18.3), in 59 chunks of 256 MiB. Each chunk was
hashed on the frame (`busybox sha256sum`) and on the host, size-checked and checked for `0xCC`
filler. All 59 matched on the first try, in about an hour. Bootloader, env, boot, system,
misc and recovery were then read a second time through `/dev/block/by-name/` with the stock `dd`,
and matched the backup byte for byte. A `gzip -1` image (447 MB) decompressed to the same SHA-256.

26 chunks in the user-data area had identical hashes. They are almost all zeros, with a few bytes
of file-system structure, and the frame computed the same hashes, so they are not reader filler.

## After root

- Rootless Launcher 3.9.1 installed, and Android Settings → Apps reached by hand on the panel.
- AiMOR, `com.yhk.qeota` (`API_10-usaFrame-P-L_Yes-20240603`) and `com.DeviceTest`
  (`YHKSign_20250303`) disabled; `package-restrictions.xml` showed `enabled="2"` for all three
  within a few seconds, and they stayed disabled after a power cycle.
- `wpa_supplicant.conf` held a factory network, `YHK-03`. Removed with
  `wpa_cli -p /data/misc/wifi/sockets -i wlan0 remove_network 0` and `save_config`, because
  `wpa_supplicant` was running and could rewrite an edited file.
- WebView 44 replaced with 106.0.5249.126 following
  [section 6](allwinner-a33-pf1007l.md#6-upgrade-webview-before-using-the-kiosk), with the stock
  tree kept at `/system/homehq-stock-webview`. `cr_LibraryLoader: Successfully loaded native
  library` after the reboot.
- GTS Root R1, GTS Root R4 and ISRG Root X1 were all missing. Added as in the
  [Uhale guide](si006-uhale.md#fonts-and-https-photos); the demo dashboard then loaded with fonts
  and photos.
- Home HQ kiosk built with JDK 17 and build-tools 34, made the Home app through the chooser
  (**Always**). After a power cycle the kiosk showed its "Connect to Wi-Fi?" screen for about 20 s
  until Wi-Fi joined, then loaded the dashboard on its own (`Wi-Fi connected or clock changed,
  retrying now`). The saved network had not been forgotten.
- Display density was already 160.

## Host notes (macOS)

- `brew install --cask temurin@17` failed without an admin password (it is a `.pkg`). A
  Homebrew `openjdk@17` that was already installed worked for `kiosk/build.sh`. A fresh
  `brew install openjdk@17` on this macOS version started building OpenSSL from source, which takes
  a long time; check `/opt/homebrew/opt/openjdk@17/bin/java -version` before installing.
- The repository's Python helpers import their sibling modules, so run them without `python3 -I`.
