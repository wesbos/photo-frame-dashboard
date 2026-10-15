# PF1007L / AiMOR May 2026 (`20260519`) firmware: T3c on macOS, no boot patch

This PF1007L reached persistent root ADB over USB with
[T3c](pf1007l-start-here.md#t3c-temporary-adb-through-the-aimor-connection) and
`persist.sys.usb.config`. Nothing was written to the boot or system partitions to get access. This
is the first `20260519` unit reported with T3c; earlier `20260519` units used Route U or Route S.

**One unit, tested once.** Run T1 to T3b on your own unit first, and follow the
[T3c procedure](pf1007l-20260410-network-adb.md) and its identity checks.

## Unit report

```text
About model / firmware: PF1007L / YHK.F-null-A33-1001-D1024-PF1007L-FL-AIMOR-OS.0.20260519
AiMOR version: 6.0.78
Ports: USB-C only, TF slot
Cable and port that gave USB data: USB-A to USB-C cable into the USB-A port of an Apple USB-C
  Digital AV Multiport adapter on the Mac. The Mac has USB-C ports only; a USB-C to USB-C
  cable gave no power and no USB device
T3 USB IDs seen / adb devices output: 1f3a:1000 ("Android"), adb devices empty
T3b network ADB result (port 5555): connection refused (TCP 8086 open)
T4 / T5: skipped
eMMC size in sectors: 30,777,344
Boot partition start sector: 172032
Boot image SHA-256 (sector 172032, 31,028 sectors):
  9a6e2456952f3dc2b99e64ea021321397bdc824364b5c8b42f503f847261630a (matches the table)
Route used and result: T3c (root ADB over Wi-Fi until reboot), then
  persist.sys.usb.config=mass_storage,adb: root ADB over USB (1f3a:1002) after every reboot
Host OS: macOS 27, Apple silicon
First failed step: none
```

## How T3c ran on this unit

- **The frame's Wi-Fi screen had no advanced options.** There was no static IP or DNS setting
  when joining a network, and no **Modify network**. So DNS could not be pointed at the Mac from
  the frame, and `dns.py` was not needed.
- **The router redirected the hostname instead.** The Verizon router's
  **Advanced → Network Settings → DNS Server** page has **Add DNS Entry**, a local host
  record. An entry for `imsconnect.efercro.com` pointing at the Mac's LAN address made the router
  answer that one name with the Mac. Every other name resolved normally for every device, so no
  router-wide DNS change was needed. Check it from the Mac with
  `dig @<router-ip> imsconnect.efercro.com A +short` before the frame joins Wi-Fi. Delete the
  entry once AiMOR is disabled.
- **The frame joined Wi-Fi with DHCP before `server.py` was running.** AiMOR's first connection
  went to the Mac's closed port 7806 and failed, and the screen showed **error code 002**. That
  gave the frame's address for `--frame-ip` without AiMOR reaching the vendor server.
- **AiMOR retried on its own** after `server.py` started, with no Wi-Fi toggle, and the command
  was sent. In that time the frame changed its Wi-Fi MAC and DHCP address (`.241` to `.242`): the
  login came from the old address, and ADB answered on the new one. Rescan for TCP 5555 after the
  command is sent.
- Identity checks passed: UID 0, `sun8i`, Android 6.0.1,
  `AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260519:eng/test-keys`.

## Persistent USB ADB

`/data/property/persist.sys.usb.config` did not exist before; the default `mass_storage` came from
the build. After `setprop persist.sys.usb.config mass_storage,adb`, the frame came back as
`1f3a:1002` with root ADB after each reboot and power cut. This unit's `init.sun8i.usb.rc` maps
`mass_storage,adb` to `1f3a:1002` and starts `adbd`. Undo: delete that file, or set it back to
`mass_storage`.

## Backup

- Over the T3c Wi-Fi ADB session, reads ran at about **290 KB/s**, too slow for a full backup:
  the first 116 MiB took 7 minutes.
- Over USB ADB, `/sbin/busybox dd` read about **6 MB/s**. The full eMMC took about an hour in
  256 MiB chunks, and the frame re-read each chunk with `busybox sha256sum` to check it. All 59
  chunks matched, and the first 116 MiB matched the earlier Wi-Fi read.

## After root

The steps followed section 5 of the [PF1007L guide](allwinner-a33-pf1007l.md) and section 6.

- Rootless Launcher was installed, and Settings → Apps was checked by hand on the panel.
- AiMOR, `com.yhk.qeota` and `com.DeviceTest` were disabled; `package-restrictions.xml` showed
  `enabled="2"` within 5 s. After a reboot there was no `:7806` connection.
- WebView 44 was replaced with 106.0.5249.126, with the stock tree kept at
  `/system/homehq-stock-webview`.
- The Home HQ kiosk was made the Home app, with the navigation service enabled.
- `adb reboot` worked on this unit (about 45 s to `sys.boot_completed=1`).

One kiosk note for your own pages: a page that scales a fixed 1280×800 layout with
`window.innerWidth / 1280` was drawn at 1.5× in the kiosk. `innerWidth` read 1600, while
`document.documentElement.clientWidth` read 1280. Scaling from `clientWidth` and `clientHeight`
fitted the screen.
