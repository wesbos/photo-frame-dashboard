# T3c on macOS with Internet Sharing, no DNS change

Use this for [T3c](pf1007l-start-here.md#t3c-temporary-adb-through-the-aimor-connection) when your
router can't add a local DNS record or hand out another DNS server, and the frame's Wi-Fi screen
has no **Modify network**. It needs a Mac and changes nothing on the home network.

The frame joins the Mac's Internet Sharing Wi-Fi, so the Mac is its gateway. A `pf` rule on the Mac
sends the frame's AiMOR connection (TCP 7806) to `server.py`, whatever address the frame looked up.
No DNS record and no `dns.py` are needed.

Tested on one PF1007L, firmware `20260519`, AiMOR 6.0.78, macOS 27 (see [unit report](#unit-report)).
It should work on any AiMOR frame that T3c works on.

## Steps

1. **Give the Mac a second internet connection.** Internet Sharing can't share Wi-Fi to Wi-Fi.
   Use Ethernet, or an iPhone over USB: Settings → Personal Hotspot → Allow Others to Join, plug it
   in, tap Trust. Check System Settings → Network → **iPhone USB** is Connected.
2. **Turn on Internet Sharing.** Keep the Mac's Wi-Fi on; Internet Sharing stops by itself when
   it's off. System Settings → General → Sharing → Internet Sharing ⓘ: share from Ethernet or
   iPhone USB, to devices using **Wi-Fi**. Set a network name and password under Wi-Fi Options,
   then turn it on. `ipconfig getifaddr bridge100` prints the Mac's address, usually `192.168.2.1`.
3. **Add the redirect.** It asks for your password, and it also cuts any vendor connection the
   frame already has, so the order of steps 3 and 4 doesn't matter:

   ```sh
   scripts/aimor-network-adb/macos-redirect.sh on
   ```

4. **Join the frame to the Mac's network** (AiMOR's Wi-Fi screen). Find its address:

   ```sh
   scripts/aimor-network-adb/macos-redirect.sh status
   ```

5. **Start the listener** after the owner approves the command it sends:

   ```sh
   /usr/bin/python3 scripts/aimor-network-adb/server.py --bind 192.168.2.1 --frame-ip <frame-ip> --seconds 600
   ```

   AiMOR retries on its own. Wait for `runtime_adb_command_sent`, then continue with step 7 of the
   [procedure](pf1007l-20260410-network-adb.md#3-enable-temporary-wi-fi-adb) (`adb connect` and the
   identity checks) and the `persist.sys.usb.config` step in
   [T3c](pf1007l-start-here.md#t3c-temporary-adb-through-the-aimor-connection).
6. **Clean up.** Turn off Internet Sharing, then:

   ```sh
   scripts/aimor-network-adb/macos-redirect.sh off
   ```

## Notes

- **The frame changes its address after a Wi-Fi toggle**, because its MAC changes. The listener
  then logs `rejected_peer` with the new address. Restart it with that `--frame-ip`.
- **The frame has internet on this network.** The rule keeps only TCP 7806, the root-command
  channel, on the Mac. Do T8 before the frame stays online.
- **Joining the Mac's network:** the [PF1006 report](pf1006-20240910-wifi-only.md) saw a frame never
  join it, and the [Linux hotspot report](pf1007l-linux-20260416-hotspot-report.md) saw a frame
  refuse WPA3 and mixed WPA2/WPA3. If the frame doesn't join, set Security to **WPA2 Personal**.
- `server.py` accepts at most 600 seconds. Run it again if it times out.

## Unit report

```text
About model / firmware: PF1007L / YHK.F-null-A33-1001-D1024-PF1007L-FL-AIMOR-OS.0.20260519
AiMOR version: 6.0.78
Ports (DC jack, or USB-C only): USB-C only
Cable and port that gave USB data (or none): USB-A to USB-C cable to the Mac mini
T3 USB IDs seen / adb devices output: 1f3a:1000 ("Android"), adb devices empty
T3b network ADB result (port 5555): connection refused (TCP 8086 open)
T4 sunxi-fel version output (or skipped): skipped
T5 check-dump stage / chunks (or skipped): skipped
eMMC size in sectors: 30,777,344
Boot partition start sector: 172032
Boot image SHA-256 (sector 172032, 31,028 sectors): 9a6e2456952f3dc2b99e64ea021321397bdc824364b5c8b42f503f847261630a (matches the table)
Route used and result: T3c through macOS Internet Sharing (iPhone USB uplink) and a pf redirect of
  TCP 7806, then persist.sys.usb.config=mass_storage,adb: root USB ADB (1f3a:1002) after a power cycle
Host OS: macOS 27, Apple silicon (Mac mini)
First failed step and its exact output: none
```

The frame had joined the Mac's network before the rule was loaded, so AiMOR already had a live
connection to the vendor server. Cutting that connection (the script now does this) and a Wi-Fi
toggle on the frame gave the login and the command within seconds. After T3c the setup followed
the [PF1007L guide](allwinner-a33-pf1007l.md) sections 4 to 7: backup over USB, Rootless Launcher,
T8, WebView 106, the three CA roots and the kiosk. The hosted demo dashboard loads.
