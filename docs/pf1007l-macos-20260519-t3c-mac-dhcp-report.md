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

## Historical network setup

The owner temporarily used macOS `dnsmasq` as DHCP and DNS on the home LAN, with the router's
DHCP switched off for the session. AiMOR's two command hostnames resolved to the Mac; other
names were forwarded normally. The frame took a lease, and a listener bound to the Mac's
address and restricted to the frame's address sent the T3c command within seconds, with a
600-second limit. The reported identity checks returned root, `sun8i`, Android 6.0.1 and the
expected `20260519` fingerprint. Persistent USB ADB then worked across power cycles.

**This is a record, not a recommended DHCP procedure.** The original setup could give other
LAN devices leases pointing to the Mac's temporary DNS server. Stopping that server could leave
those devices without DNS until their leases were repaired. Ping and ARP silence do not prove
that addresses are unused. Running two DHCP servers during a switchover can also disrupt clients.
Use the offline test-app route first, then a controlled isolated network and the canonical
[T3c procedure](pf1007l-20260410-network-adb.md) where needed.

For cleanup, the owner forgot the frame's Wi-Fi network before restoring the router's DHCP,
stopped the temporary service, and power-cycled the frame. Root USB ADB returned with no TCP
7806 connection. Forgetting the network prevented AiMOR from reconnecting to its real vendor
server before T8. This account does not establish rollback for other clients' leases.

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
