# Runxion 10.1" Frameo frame: SSA ZN-DP1002 board (RK3126, Android 6.0.1, eMMC)

Record of one unit, 2026-10-15, macOS host (Apple silicon). Observations are kept separate from
guesses. Unique identifiers (serial, MAC, Wi-Fi, URLs) are left out; they live in the ignored
`backups/` folder.

**Short version:** sold as the [Runxion 10.1" Frameo, 32 GB](https://amzn.to/4B38DQ0), which the
[device index](devices.md) lists as RK3326 / Android 8.1. **This unit is not that board.** It is an
SSA ZN-DP1002 with a Rockchip **RK3126**, **Android 6.0.1** and **eMMC**: the same family as the
[Akimart ZN-DP1002 (RK3126)](biuframe-setup-guide.md#akimart-zn-dp1002-rk3126), but a newer build
(2025-09-26) with different vendor apps (Adups instead of Muxintu) and a different partition layout.
[`biuframe-setup.sh`](../scripts/biuframe-setup.sh) refuses it, correctly, because the fingerprint
does not match its Akimart profile. ADB comes from Frameo's beta settings, `su` gives root without a
prompt, and WebView is already 107, so the dashboard kiosk needs no WebView swap. Frameo, Adups
FOTA, Rockchip's updater and the factory test apps were removed from `/system` after a verified
backup; the frame now boots straight into the kiosk. The frame has no clock battery, which broke
HTTPS for the first minute after every power-up until the kiosk learned to wait for the clock.
**The firmware also runs a hidden root program, `/system/bin/iotv`**, that is not an app and does
not show in `pm list packages`. It is UPX-packed, starts at every boot, passes the Wi-Fi MAC address
and kept a connection to a server on a rented cloud machine, moving about 60 MB an hour in each
direction. See [Hidden root agent: iotv](#hidden-root-agent-iotv).

## Observations (read-only unless noted)

### Identity

| | |
| --- | --- |
| Sold as | Runxion 10.1" Frameo, 32 GB (Amazon US) |
| About screen | Frameo v1.27.5 |
| Brand / model | `ro.product.brand=SSA`, manufacturer `Shenzhen SSA`, model `Frame`, device `ZN-DP1002` |
| Firmware | `SSA-ZN-DP1002-V1.0.1202509261611.release-keys`, built 2025-09-26 |
| Fingerprint | `rockchip/rk312x/rk312x:6.0.1/MXC89K/user.wanghy.20250926.161043:user/release-keys` |
| SoC | Rockchip RK3126 (`ro.board.platform=rk312x`, `ro.hardware=rk30board`), 32-bit (`armeabi-v7a`) |
| Kernel | Linux 3.10.0, built 2025-09-26 |
| Android | 6.0.1, API 23, security patch 2016-07-05, `user` build, `ro.debuggable=0`, `ro.secure=1`, `ro.adb.secure=1`; `ro.config.low_ram` not set |
| SELinux | Permissive (`getenforce`) |
| Display | 1280x800, 160 dpi |
| RAM / storage | 1 GB (`MemTotal: 1023552 kB`), zram swap; 32 GB eMMC (`mmcblk0`, 30,310,400 sectors), `/data` 27 GB |
| WebView | `com.google.android.webview` **107.0.5304.36** in `/system/app/webview` |
| Wi-Fi | Onboard, driver module `rk915` (the same as the Akimart RK3126 profile) |
| SystemUI | `com.android.systemui` is **disabled** (`enabled=2`): no status or navigation bar |
| Frameo | `net.frameo.frame` v1.27.5, `/system/priv-app/Frameo.apk`, the HOME app |
| USB (ADB) | `2207:0006`, vendor string `Shenzhen SSA`, product `Frame`, 480 Mb/s |

### USB, ADB and root

- **ADB:** Frameo → Settings → About → **Beta Program** (on) → **ADB access** (on). The switch is
  not visible until Beta Program is on. Done offline: Wi-Fi was skipped in Frameo's first-run setup.
- `adb devices` showed `device`, product `ZN-DP1002`, and `/data/misc/adb/adb_keys` existed.
- **adbd does not check keys.** After the factory reset below, `adb_keys` was gone (no
  `/adb_keys` either) and the Mac was still accepted at once, with `ro.adb.secure=1`. USB ADB is also
  on by default after a reset (`persist.sys.usb.config=adb`, `persist.service.adb.enable=1`), with no
  Frameo setting touched. With the no-prompt `su` below, **anyone with a USB cable gets a root
  shell**, before or after a reset. Network ADB (`adb tcpip`) would extend that to the whole
  Wi-Fi network, so it was not enabled on this unit.
- **One USB drop:** the connection dropped and came back once in the first minute (the transport id
  changed); it stayed up for the rest of the session, including the backup.
- **Root:** `su -c id` and `su 0 id` both return `uid=0(root)` immediately, with no prompt
  (`/system/xbin/su`, 133,472 bytes, dated 2025-09-26). `adb root` was not tried.
- Through this `su`, `adb exec-out` is byte-clean: a 4 KiB read of `boot` and a 1 MiB read of
  `system` matched on-device `md5sum` exactly (no LF to CRLF changes, unlike SuperSU on the
  [VESWWE](veswwe-10.1.md#root-adb-and-backup-transport)).

### Vendor apps

`pm list packages -f`, outside `com.android.*`:

| Package | Path | What it is |
| --- | --- | --- |
| `net.frameo.frame` | `/system/priv-app/Frameo.apk` | Frameo, the HOME app |
| `com.adups.fota` | `/system/app/FotaUpdate` | **Adups FOTA** over-the-air updater |
| `com.adups.fota.sysoper` | `/system/app/FotaUpdateReboot` | Adups helper (reboot) |
| `android.rockchip.update.service` | `/system/app/RKUpdateService` | Rockchip OTA updater |
| `com.DeviceTest` | `/system/priv-app/DeviceTest` | Factory test app |
| `com.cghs.stresstest` | `/system/priv-app/StressTest` | Factory stress test |
| `jp.co.omronsoft.openwnn` | `/system/app/OpenWnn` | Japanese keyboard |
| `com.google.android.webview` | `/system/app/webview` | WebView 107 |

The Akimart RK3126 profile expects `com.muxintu.app.mxota` and `com.szclink.app.cldevicetest`
instead; neither is present here.

`com.android.rk` (`/system/app/RkExplorer`, v4.1.5_20160704) is Rockchip's file manager. It runs as
the system user with internet, storage and boot permissions, but has no service.

This list covers apps only. Native programs started by `init` do not appear in it; see the next
section.

### Hidden root agent: iotv

Found on 2026-10-15 while checking which processes use the network, after Frameo had been removed.

| | |
| --- | --- |
| File | `/system/bin/iotv`, 982,392 bytes, dated 2025-09-26, MD5 `00e797d509074f05d757e6367308f1ef` |
| Format | 32-bit ARM ELF, statically linked, packed with UPX (no readable strings) |
| Started by | `init.rk30board.rc` (in the boot image): `service run_iotv /system/bin/sh /system/bin/run_iotv.sh`, `class main`, `oneshot`, `disabled`, and `on property:sys.boot_completed=1` → `start run_iotv` |
| `run_iotv.sh` | `/system/bin/iotv -MAC $(… < /sys/class/net/wlan0/address …)`: the Wi-Fi MAC address is its only argument |
| Runs as | root (uid 0) |
| Connection | TCP to `172.235.49.87:8086`, an Akamai/Linode cloud machine (`172-235-49-87.ip.linodeusercontent.com`), reconnecting every few seconds; seen in `/proc/net/tcp`, owner found through `/proc/<pid>/fd` |
| Traffic | `xt_qtaguid` for uid 0 on `wlan0`: about 180 MB received and 178 MB sent in the first 3 hours after boot. The kiosk used 3 MB and 0.5 MB in the same time. Nothing else on the frame used the network |

What it sends could not be read: the program is packed and the traffic was not decrypted. The even
volume in both directions fits a relay or tunnel better than a status check, but that is a guess.
Whatever it is, a root program can read everything on the frame, so it was removed before any
family photos were put on it.

**Pitfall:** this build's `pidof` prints **every** process ID when nothing matches. A first attempt,
`kill $(pidof iotv)`, also stopped the SuperSU daemon and root was gone until a reboot (`daemonsu` is
started by `init`, not by `iotv`). Kill by the PID from `ps` instead.

### eMMC partition map

Read from `/sys/block/mmcblk0/mmcblk0p*/start` and `size` and `/dev/block/platform/*/by-name`, in
512-byte sectors. The layout differs from the Akimart RK3126 profile (there, `recovery` starts at
122880, `system` at 630784 and `userdata` at 2859008).

| Node | Name | Start | Size |
| --- | --- | --- | --- |
| mmcblk0p1 | uboot | 16384 | 8192 |
| mmcblk0p2 | misc | 24576 | 8192 |
| mmcblk0p3 | resource | 32768 | 32768 |
| mmcblk0p4 | kernel | 65536 | 24576 |
| mmcblk0p5 | boot | 90112 | 24576 |
| mmcblk0p6 | recovery | 114688 | 65536 |
| mmcblk0p7 | backup | 180224 | 131072 |
| mmcblk0p8 | cache | 311296 | 262144 |
| mmcblk0p9 | metadata | 573440 | 32768 |
| mmcblk0p10 | kpanic | 606208 | 8192 |
| mmcblk0p11 | system | 614400 | 2097152 |
| mmcblk0p12 | radical_update | 2711552 | 131072 |
| mmcblk0p13 | userdata | 2842624 | 57778176 |

### Verified firmware backup

Taken before any change, read-only, with `biuframe-setup.sh`'s method, by hand with this unit's
bounds (the script refuses the unit):

```sh
adb exec-out "su -c 'dd if=/dev/block/mmcblk0 bs=1048576 count=1388 2>/dev/null'" \
  | tee >(shasum -a 256 > emmc.sha256.raw) | gzip -1 > emmc-0-2842624.img.gz
```

- Scope: eMMC sectors 0–2,842,623, everything before `userdata` (1388 MiB exactly).
- Raw size 1,455,423,488 bytes, as expected; 351 MB compressed; 235 s over USB.
- Stream SHA-256 matched the gzip readback SHA-256.
- No aligned 4 KiB block consisted entirely of `0xCC`.
- Independent re-reads from the frame (`dd … | md5sum` on the device) matched the backup for all 13
  regions: the area before `uboot`, and `uboot` through `radical_update`.
- `boot` partition (12 MiB) SHA-256:
  `89fb56ecba9dc13884e5e82440095bb5a0369a586461a045f84de71fe5a4efe5`.

This is a logical capture of everything before `userdata`, not a `userdata` snapshot. Restoring it
has not been tested.

## Setup performed

Each step was approved separately by the owner, after the verified backup. The dashboard address is
written `https://<dashboard>/` below.

| Step | Command | Result | Undo |
| --- | --- | --- | --- |
| Factory reset (wipes `userdata` only) | `su -c 'mkdir -p /cache/recovery; printf -- "--wipe_data\n--locale=en_US\n" > /cache/recovery/command; sync; reboot recovery'` | Back in about 2 minutes with no input needed; Frameo's data was new (about 1 MB) and `adb_keys` gone; USB ADB still on and accepted (see above) | None needed |
| Wi-Fi | `am start -a android.settings.WIFI_SETTINGS`; network chosen and password typed on the panel | Connected; the dashboard host resolved and answered `ping` | Forget the network |
| Time zone | `su -c 'setprop persist.sys.timezone America/Chicago; service call alarm 3 s16 America/Chicago'` | The build shipped set to Pacific time; network time (`auto_time=1`) was already on | The same with the old zone |
| Kiosk | `adb install -r dashboard/kiosk/build/homehq.apk` | Installed (v1.1); WebView 107 rendered the dashboard | `adb uninstall com.wesbos.homehq` |
| Kiosk URL and HOME | `am start -n com.wesbos.homehq/.MainActivity --es url https://<dashboard>/ --ez home true` | Saved URL is the plain address (checked in `shared_prefs/kiosk.xml`) | `--ez home false` |
| Sign-in | `am start -a android.intent.action.VIEW -d 'https://<dashboard>/?key=…' -n com.wesbos.homehq/.MainActivity`, then `logcat -c` | A VIEW link is shown, not saved, so the key is not stored on the frame; the site's session cookie is. After `am force-stop` and a restart the dashboard still opened signed in | Clear the kiosk's data |
| Navigation buttons | On the panel: two-finger hold → Android settings → Accessibility → Home HQ navigation → on. Then `pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS` | Floating Back and Dashboard buttons. **Way back proven by hand:** Settings → Apps reached and Dashboard returned, before anything was removed | Turn the service off; `pm revoke` the same |
| Remove vendor code from `/system` | Files copied to the host first (22 files, MD5 checked against the frame). Then `su -c 'mount -o rw,remount /system; rm -rf /system/priv-app/Frameo.apk /system/lib/Frameo /system/app/FotaUpdate /system/app/FotaUpdateReboot /system/app/RKUpdateService /system/priv-app/DeviceTest /system/priv-app/StressTest; sync'`, reboot | After the reboot `/system` mounted `ro`; none of `net.frameo.frame`, `com.adups.fota`, `com.adups.fota.sysoper`, `android.rockchip.update.service`, `com.DeviceTest`, `com.cghs.stresstest` was listed, and Android had removed their data directories. The kiosk was the only HOME app and came up on its own; Wi-Fi rejoined by itself (unlike [the S101 Frameo](frameo-rk3326-s101.md#frameo-and-wi-fi)); time zone and navigation service kept | Copy the saved files back the same way (`mount -o rw,remount /system`, `cp`, `chmod 644`, reboot), or write `system` back from the verified backup |
| Remove `iotv` | `iptables -I OUTPUT 1 -d 172.235.49.87 -j REJECT`, then `kill <pid from ps>`; files copied to the host first (MD5 checked); `mount -o rw,remount /system; rm /system/bin/iotv` | After a reboot no `iotv` process and no connection to port 8086 | Copy the file back the same way, or write `system` back from the verified backup |
| Firewall at boot | The boot image keeps starting `run_iotv.sh` as root, so that file was replaced (not deleted) with a script that adds an `OUTPUT` chain: loopback, the kiosk's uid, DNS, DHCP, ICMP, and network time and Android's connection check for the system uid are allowed; everything else is logged (`hq_out refused:` in `dmesg`) and refused. IPv4 and IPv6 | Survived a reboot; root still worked. In 10 minutes afterwards only the kiosk talked to the dashboard (104 KB in, 18 KB out), the system uid renewed DHCP, and uid 0 used 8 KB in and 6 KB out (DNS). Nothing was refused | `iptables -D OUTPUT -j hq_out` (and `ip6tables`); put the original `run_iotv.sh` back |
| Disable the file manager | `pm disable com.android.rk` (as root) | `enabled="2"` in `/data/system/users/0/package-restrictions.xml`. A first attempt was lost because the frame rebooted within seconds, before Android saved the setting | `pm enable com.android.rk` |

`mount -o ro,remount /system` right after the removal failed with `Device or resource busy`; the
reboot mounted it read-only.

Frameo traces left after that, and what was done:

| Trace | Action |
| --- | --- |
| `/data/media/0/frameo`, `/data/media/0/frameo_files`, `/data/media/0/Android/data/net.frameo.frame` (made during Frameo's first run after the reset) | Deleted |
| `/data/dalvik-cache/arm/system@priv-app@Frameo.apk@classes.dex` (orphaned) | Deleted |
| `settings secure enabled_notification_policy_access_packages=net.frameo.frame` | `settings delete` |
| `ro.frameo.default.*` in `/system/build.prop` (language, brightness, notify volume, time zone `America/Los_Angeles`) | Left: read only by Frameo |
| `/system/media/bootanimation.zip`: the Frameo logo (870x433, 4 parts) | Left for now |
| `logo.bmp` and `logo_kernel.bmp` (800x1280, Frameo logo) in the `resource` partition, next to `rk-kernel.dtb` | Left: rewriting `resource` risks the device tree the kernel boots with |

After this, `find / -xdev -iname '*frameo*'` and `find /data -iname '*frameo*'` found nothing, and no
file in `/data/system/users/0/` mentioned Frameo.

### No clock battery: wrong date at every power-up

After a cold reboot the frame starts with a fixed date (logcat showed **May 14, 2021**) until
network time arrives, about 20 seconds after Wi-Fi joins. During that window every HTTPS
certificate fails as not yet valid (`SslError` 4, `SSL_DATE_INVALID`). The kiosk used to show
"This site isn't trusted on this frame" and stop there, so a power cut left the frame on that
screen. Seen once by chance (the first reboot after the removal), then reproduced on purpose
(`settings put global auto_time 0; su -c 'date 010112002020'`).

Fixed in the kiosk: a certificate error that is about the date, or that comes within 10 minutes of
boot, now shows "Setting the clock…" and retries every 15 s, and a clock or time-zone change
retries at once. The error is still never bypassed (`handler.cancel()`). A second bug made this
miss the first load after start: the error arrives before `onPageStarted`, so the kiosk did not yet
know it was the main page; it now remembers the URL it asked to load. Verified with a cold reboot:
DNS failure, then the date error and "Setting the clock…", then "Clock changed, retrying now" and
the dashboard, about 75 s after power-on.

## Guesses, not confirmed

- The Runxion listing may ship either the RK3326 / Android 8.1 board in the device index or this
  RK3126 / Android 6.0.1 board; the listing does not say which.
- With SystemUI disabled, the "Allow USB debugging" prompt should not be able to appear, yet the key
  was authorized. How this build accepts keys was not examined.

## Not yet checked

- A full comparison of `/system` and the boot image's `init` scripts against stock AOSP 6.0.1, to find
  any other vendor program. The kernel and its modules (Wi-Fi `rk915`, GPU) are closed and were not
  examined.

- `adb root` (not needed: `su` works).
- Restoring the firmware backup.
- Memory use over days on 1 GB.

HTTPS to the dashboard (Cloudflare `workers.dev`) worked on this Android 6 certificate store with no
extra roots once the clock was right.
