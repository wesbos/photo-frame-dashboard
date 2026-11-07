# PF1007L / AiMOR `20260519` on Windows: Wi-Fi-only T3c, exFAT microSD backup, and Home Assistant

One AiMOR PF1007L on `FL-AIMOR-OS.0.20260519`, set up from Windows 11 when USB data never
enumerated on the host. Everything ran over Wi-Fi after a T3c bootstrap, with the firmware backup
written locally on the frame to a 64 GB exFAT microSD card and Home Assistant Companion Minimal
set as the Home app. Observations are kept separate from guesses, and device-unique identifiers
(serial, MAC addresses, SSIDs, and whole-disk hashes) are omitted.

## Unit report

```text
About model / firmware: PF1007L / YHK.F-null-A33-1001-D1024-PF1007L-FL-AIMOR-OS.0.20260519
AiMOR version: 6.0.78
Ports (DC jack, or USB-C only): USB-C, microSD slot
Cable and port that gave USB data (or none): none (several cables tried; Android reported state=DISCONNECTED)
T3 USB IDs seen / adb devices output: none; adb devices empty
T3b network ADB result (port 5555): connection refused (TCP 8086 open), also after toggling the factory test app switch
T4 sunxi-fel version output (or skipped): skipped
T5 check-dump stage / chunks (or skipped): skipped
eMMC size in sectors: 30,777,344 (15,758,000,128 bytes)
Boot partition start sector: 172032 (mmcblk0p6, 65,536 sectors)
Boot image SHA-256 (sector 172032, 31,028 sectors):
  9a6e2456952f3dc2b99e64ea021321397bdc824364b5c8b42f503f847261630a (matches the table)
Route used and result: T3c on native Windows (dns.py --udp-only + server.py) via Google Home custom
  DNS -> root Wi-Fi ADB (uid=0), kept across reboots with persist.adb.tcp.port=5555 and restricted
  with ADB_ALLOW in pf1007l-boot
Host OS: Windows 11 (PowerShell, Git Bash, platform-tools adb, Python 3)
First failed step and its exact output: T3 (no USB device enumerated on Windows); T3b (TCP 5555 refused)
```

## Observations

### 1. Factory test app shortcut (`YHK88888888`) enables USB ADB only

- In **Settings → About**, tapping **Model** repeatedly opened the **"Open test app"** password
  prompt, and `YHK88888888` (from [#135](https://github.com/wesbos/photo-frame-dashboard/issues/135))
  opened `com.DeviceTest` directly on `20260519` without needing a `license.properties` SD card.
- Switching the test app's debugging control to **"is open"** set
  `persist.sys.usb.config=mass_storage,adb` and `sys.usb.config=mass_storage,adb`, and configured
  `/sys/class/android_usb/android0/` as `1f3a:1002` (`functions=mass_storage,adb`, `enable=1`).
- That switch did **not** start `adbd` on TCP `5555` (`T3b` still refused connections), and
  `/sys/class/android_usb/android0/state` remained `DISCONNECTED` across multiple cables and a
  reboot. Guess: either the USB-C data lines on this unit are unconnected/faulty or none of the
  tested cables/ports satisfied the frame's USB 2.0 data path.

### 2. T3c on native Windows with Google Home DNS

- On Windows 11, `0.0.0.0:53` (TCP) was already bound by a local system service, while UDP `53` on
  the PC's Wi-Fi IP was free. Passing `--udp-only` to `scripts/aimor-network-adb/dns.py` worked on
  Windows the same way as on macOS.
- In the Google Home app (**Wi-Fi → Network settings → Advanced networking → DNS**), setting custom
  primary DNS to the PC's LAN IP redirected `imsconnect.efercro.com` through `dns.py` to
  `server.py`.
- Toggling Wi-Fi off and on on the frame caused the AIC8800 driver to pick a new MAC and DHCP
  address. Updating `clients.json` and restarting `server.py` with the new `--frame-ip` — without
  toggling Wi-Fi a second time — caught AiMOR's automatic retry loop and started root ADB on
  `5555` (`uid=0(root)`).
- With no working USB data path, `setprop persist.adb.tcp.port 5555` was used so root Wi-Fi ADB
  survived reboots (confirmed across two reboots). See the security notes in
  [pf1006-20240910-wifi-only.md](pf1006-20240910-wifi-only.md#4-make-it-persistent-no-flash-write):
  `ro.adb.secure=0` leaves port `5555` unauthenticated, so pair it with `ADB_ALLOW` in
  [pf1007l-boot-fixes.md](pf1007l-boot-fixes.md) and keep the frame on an isolated or trusted LAN.

### 3. Fast local backup to an exFAT microSD card

- Over Wi-Fi ADB, file transfers ran at about `300 KB/s`, which would take nearly two hours for the
  `2,132 MiB` pre-`UDISK` area.
- Inserting a 64 GB **exFAT**-formatted microSD card (`mmcblk1p1`, MBR) while Android 6.0.1 was
  running mounted it automatically at `/mnt/media_rw/extsd` (`fuseblk rw`), with no FAT32 reformat
  needed. (Note: U-Boot for Route U / Route S still requires FAT32, but running Android 6.0.1 on
  `20260519` mounts exFAT via `vold`.)
- Dumping `mmcblk0boot0`, `mmcblk0boot1`, the individual firmware partitions,
  `stock-webview.tar`, and the `2,235,564,032`-byte pre-`UDISK` image (`sectors 0..4366335`)
  directly to `/mnt/media_rw/extsd/` with `/sbin/busybox dd` and verifying independent re-reads
  from the eMMC took about 12 minutes in total.

| Partition | Sectors (start, count) | SHA-256 |
| --- | --- | --- |
| `bootloader` (`mmcblk0p2`) | `73728`, `65536` | `154fbfe9bbb3ebe7a1a3390e31f73c9ef6647c3579ab1b2e19f5505e7c6a6222` |
| `boot` (`mmcblk0p6`, first 31,028 sectors) | `172032`, `31028` | `9a6e2456952f3dc2b99e64ea021321397bdc824364b5c8b42f503f847261630a` |
| `boot` (`mmcblk0p6`, full 32 MiB partition) | `172032`, `65536` | `dd9070343b1f11ab599dd90f254d4e4395644c7e0d5252249ffa5de091498344` |
| `system` (`mmcblk0p7`, 1 GiB) | `237568`, `2097152` | `2de5fbaabc82383ba13cdb0cde3ea8f06f80775c725256e6ee3e30b1997613a3` |
| `recovery` (`mmcblk0p9`, full 32 MiB partition) | `2400256`, `65536` | `2acbd8e4f160211cd0cbc445564a5106601a8f359c893d17fa345ae5fb9fc4d0` |

### 4. Factory Wi-Fi entry, WebView 106, Home Assistant Companion, and boot fixes

- `/data/misc/wifi/wpa_supplicant.conf` contained a saved factory network `ssid="YHK-03"`
  (`scan_ssid=1`), matching the factory SSID pattern noted in #135 and #172. Removed after backing
  up `wpa_supplicant.conf.bak`.
- Stock WebView `44.0.2403.119` was replaced in `/system/app/webview` with the pinned LineageOS
  WebView `106.0.5249.126` (`e2edc1f89ec1608b169da9e7ffc037190b70c7825f0be29694f4cae719980580`)
  and its three extracted `lib/armeabi-v7a/*.so` libraries, with the stock tree kept at
  `/system/homehq-stock-webview` and the three CA roots (`f013ecaf.0`, `5acf816d.0`, `6187b673.0`)
  added to `/system/etc/security/cacerts/`.
- Installed Rootless Launcher `3.9.1` (`7fa44d560dc4577374d45176220de2c0b00a71e09d6d148cdea4e0a52d38404a`)
  and the official **Home Assistant Companion Minimal `2026.8.4`** APK
  (`io.homeassistant.companion.android.minimal`, SHA-256
  `8f58a7df71c61447d3370f5d5956a66e3523625dc4b51c8434bd166d3e731bea`), then enabled
  `io.homeassistant.companion.android.minimal/io.homeassistant.companion.android.launch.LauncherAlias`.
  *(Note: `adb install` of the 52 MB Home Assistant APK over Wi-Fi ADB took about 5 minutes total
  including pushing at `0.3 MB/s` and Android 6 `dex2oat` compilation.)*
- Disabled `com.yhk.qeota`, `com.DeviceTest`, `com.efercro.os.aimor`, and `com.android.gl2jni`,
  confirming `enabled="2"` in `/data/system/users/0/package-restrictions.xml` before rebooting.
- **Boot fixes (`scripts/pf1007l-boot/install.sh`) from Windows Git Bash:**
  - Running `C:\Program Files\Git\bin\bash.exe scripts/pf1007l-boot/install.sh apply` without
    `--login` (`-l`) failed at `shasum: command not found` because Git for Windows places `shasum`
    in `/usr/bin/core_perl/shasum`, which is only added to `PATH` by `/etc/profile` in a login
    shell. Running `bash.exe -lc 'ANDROID_SERIAL=<ip>:5555 scripts/pf1007l-boot/install.sh apply'`
    succeeded.
  - With `WIFI_DEFER=1`, `POWER_FIX=0`, `NTP_SERVER=time.google.com`, `ADB_ALLOW=<subnet>/24`, and
    `KIOSK=io.homeassistant.companion.android.minimal/io.homeassistant.companion.android.launch.LauncherAlias`,
    `adb reboot` completed cleanly (no hang on either reboot on this unit) and `install.sh verify`
    passed: `wlan0` came up at `42.10s` uptime with the pinned MAC, NTP set the clock, and Android
    focused Home Assistant's `LauncherAlias` with no vendor processes or `:7806` connections.
