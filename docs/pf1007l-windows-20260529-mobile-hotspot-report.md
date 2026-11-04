# PF1007L / May `20260529`: T3c through a Windows Mobile Hotspot

One Humblestead 10.1-inch frame with a PF1007L board, reported in
[#261](https://github.com/wesbos/photo-frame-dashboard/issues/261). This is a record of the owner's
setup, not a new network or system-write procedure. Use the
[start-here guide](pf1007l-start-here.md), including the offline test-app route before T3c.

| Field | Reported result |
| --- | --- |
| Firmware | `YHK.F-null-A33-1001-D1024-PF1007L-V10-1680.0.20260529` |
| AiMOR | 6.0.78 |
| Ports | USB-C only; the cable also supplies power |
| Host | Native Windows ADB 37.0.1 and Python 3.14; WSL2 Ubuntu 24.04 with interop off |
| Cable | UGREEN USB-A to USB-C data cable, into the PC's USB-A port |
| Stock USB / network ADB | `1f3a:1000`, no ADB; TCP 5555 closed |
| After T3c | `1f3a:1002`, root USB ADB without an authorization prompt |
| eMMC | 30,777,344 sectors |
| Boot partition start | Sector 172032 |
| Boot hash | Owner reported prefix `6c118dc1…` for the first 31,028 sectors; matches the known firmware's prefix, not a full hash comparison |

## Windows hotspot observation

The owner used Windows Mobile Hotspot over 2.4 GHz Wi-Fi with WPA2. Its first setting shared over
Bluetooth instead, and DNS checks timed out until Wi-Fi was selected.

The ICS DNS proxy (`SharedAccess`) already held UDP 53, so the repository's DNS helper could not
bind there. Temporary entries in the PC's hosts file redirected AiMOR hostnames to the hotspot
address; ICS answered from that file. A temporary inbound TCP 7806 firewall rule let the T3c
listener accept the frame. The owner removed the hosts entries, firewall rule and hotspot afterward.
The issue does not provide a complete, peer-restricted configuration, so these observations should
not be copied as a replacement for the [T3c procedure](pf1007l-20260410-network-adb.md).

`persist.sys.usb.config=mass_storage,adb` then kept USB ADB available without a boot write.
Network ADB was root without authentication during T3c. Keep it on a controlled network and
complete [T8](pf1007l-start-here.md#t8-lock-it-down-before-the-frame-stays-online).

## Backup and setup observations

Wi-Fi ADB transferred about 570 KiB/s, so the owner used USB ADB at about 6.5 MiB/s for the backup.
BusyBox `dd` read the eMMC in 59 chunks of 256 MiB, each compared with an on-device MD5. No all-`0xCC`
MiB blocks were found. Independent re-reads of p2 and p5 through p9 matched. The stock `dd`
returned nothing past 2 GiB.

**The report does not record a full-image SHA-256 or gzip readback. It therefore does not establish
all of README rule 2's backup checks. Complete those checks before any system or flash write.**

The owner reported Rootless Launcher 3.9.1, vendor apps disabled across reboot with no TCP 7806
connection, WebView 106.0.5249.126, and Home HQ as Home. The stock WebView tree was retained.
SELinux was disabled and system files were unlabeled. BusyBox 1.18.3 lacked `grep -x` and `stat`;
its `df` wrapped long device names onto a second line.

The existing boot-fixes installer ran through Git Bash and passed its verification. Deferred Wi-Fi
started at 59.9 seconds on this unit, later than the 40–44 seconds recorded on other units.
