# Frameo 10.1" `BGS-102K-T` (ALONG, Allwinner A33 `astar_xr819`, Android 6.0.1)

Record of one unit, set up on 2026-10-16. Host: macOS 27 on Apple silicon. Observations are kept
separate from guesses. The serial, MAC addresses and network details are left out; they stay in the
owner's ignored `backups/` and `frames/` folders.

**Short version:** USB ADB is on from `/system/build.prop`, but the key check is enforced: the
"Allow USB debugging?" prompt appeared only after Frameo's ADB access switch was toggled with the
cable plugged in. The shipped `/system/bin/su` gives UID 0 with `su 0 <cmd>`, without the
capabilities to remount `/system`. WebView is **44**, so the repo's kiosk can't run, and it can't
be swapped. The end result uses **Firefox 143 as an installed web app** (full screen, no address
bar) started by a small Home app, with Frameo and Adups disabled. Nothing was written to `/system`
or the boot partition.

**Close relative:** [Frameo 102K (ALONG)](frameo-102k-a33.md). Same brand, platform, fingerprint
family and partition starts, but an older firmware (2024-01-10 against 2026-01-13), WebView 44
against 106, low-RAM mode on, and a key check on USB ADB. Compare the fingerprint before you follow
either page.

## Identity

| Item | Observed value |
| --- | --- |
| Listing | Amazon, "Frameo 10.1 Inch WiFi Digital Photo Frame with Built-in 32GB Memory, 1280x800 IPS HD Touch Screen ...". Listing URL not recorded |
| `adb devices -l` | `product:BGS-102K-T model:BGS_102K_T device:BGS-102K-T` |
| Brand / manufacturer | `ro.product.brand=ALONG`, `ro.product.manufacturer=Allwinner` |
| Firmware | `ro.build.display.id=BGS-102K-T-M33-6.0-20240110` |
| Fingerprint | `Allwinner/astar_xr819/astar-xr819:6.0.1/MOB30R/20240110:eng/test-keys`. `ro.build.type` is `user` |
| SoC | Allwinner A33 (`ro.board.platform=astar`, `ro.hardware=sun8i`), 32-bit ARMv7 |
| Kernel | Linux 3.4.39, `#255 SMP PREEMPT`, built 2024-01-10 |
| Android | 6.0.1, API 23, security patch 2016-07-05, `ro.secure=1`, `ro.debuggable=0`, SELinux permissive |
| Display | 1280x800, density 160, `ro.sf.rotation=90` |
| RAM / swap | 1,026,980 kB; zram 327,680 kB. **`ro.config.low_ram=true`** |
| Storage | eMMC `mmcblk0`, 61,472,768 sectors; `/data` 26.8 GB |
| Wi-Fi | XR819 (`xradio_wlan`, `xradio_core`, `xradio_mac`). **2.4 GHz only** |
| Power | `/sys/class/power_supply` has `ac`, `battery` and `usb` entries |
| Frameo | `net.frameo.frame` **v1.18.7**, in `/system/priv-app/Manufacturertest` |
| WebView | `com.android.webview` **44.0.2403.119** in `/system/app/webview` |
| Other packages | `com.adups.fota` (`/system/app/FotaUpdate`, running), `com.along.table` (`AlongTestApk`), stock `Launcher2` and `Browser` |
| FOTA properties | `ro.fota.oem=alongA33_6.0`, `ro.fota.device=BGS-102K-T`, `ro.fota.version` = the firmware string |
| Time zone | `ro.frameo.default.timezone=America/New_York` |

## USB and ADB

- Enumerates as **`1f3a:1001`** (`USB Developer` / `Android`) with a **USB-A to USB-C** data cable
  through a USB-C to USB-A adapter on the Mac. USB-C to USB-C was not tried.
- `/system/build.prop`: `persist.sys.usb.config=adb`, `ro.adb.secure=1`, `persist.service.adb.enable=1`.
  At runtime `sys.usb.config=mtp,adb`. ADB is on before anyone touches Frameo.
- **The key check is enforced.** The frame was already set up with Frameo. `adb devices` showed
  `unauthorized`, and neither restarting the ADB server nor replugging brought up a prompt. Toggling
  **Frameo → Settings → About → Beta program → ADB access** with the cable in did: the prompt
  appeared, and after **Always allow** the host key is in `/data/misc/adb/adb_keys`
  (`system:shell`, `0640`).
- No network ADB: `service.adb.tcp.port` is empty, and nothing on the LAN answered on 5555.
- USB ADB kept working after Frameo was disabled and across reboots.

## Root

- `/system/bin/su`, setuid root (`-rwsr-sr-x root root`, 17,920 bytes). No `/system/xbin/su`.
- `su 0 id` gives `uid=0(root)`, context `u:r:shell:s0`. `su -c id` fails with
  `invalid uid/gid '-c'`.
- `su 0` keeps only `CAP_SETUID`/`CAP_SETGID` (`CapBnd: ffffffe0000000c0`), as on the
  [102K](frameo-102k-a33.md#root):
  - `su 0 mount -o remount,rw /system` → `mount: Operation not permitted`; `/system` stays `ro`.
    So no WebView swap and no `build.prop` edit without changing the boot image.
  - Files owned by `system` need `su 1000` (for example `/data/system/users/0/package-restrictions.xml`).
  - `su 0 pm disable` works.
- `su` has no manager app and no prompt, so treat every app on this frame as if it has root.

## Partition table

eMMC `mmcblk0`, 512-byte sectors, from `/sys/block/mmcblk0/mmcblk0p*/start` and
`/dev/block/by-name`. Every start matches the [102K table](frameo-102k-a33.md#partition-table);
only `UDISK` is larger (bigger eMMC).

| Partition | Name | Start | Size (sectors) |
| --- | --- | --- | --- |
| p2 | bootloader | 73728 | 65536 |
| p5 | env | 139264 | 32768 |
| p6 | boot | 172032 | 32768 |
| p7 | system | 204800 | 2097152 |
| p8 | misc | 2301952 | 32768 |
| p9 | recovery | 2334720 | 65536 |
| p10 | cache | 2400256 | 1572864 |
| p11 | metadata | 3973120 | 32768 |
| p12 | private | 4005888 | 32768 |
| p13 | frp | 4038656 | 1024 |
| p14 | empty | 4039680 | 31744 |
| p15 | alog | 4071424 | 163840 |
| p16 | media_data | 4235264 | 32768 |
| p1 | UDISK (`/data`) | 4268032 | 57204736 |

## Boot image

Stock, read before any change and never written.

| Item | Value |
| --- | --- |
| Boot partition (16 MiB) SHA-256 | `ae0ce00d9295dc3b252f6b51b3ea7ed6406a3bc8241a468977944e9c4f625896` |
| Header | `ANDROID!`, page 2048, kernel 10,221,784 bytes, ramdisk 4,735,093 bytes, no second stage, cmdline `vmalloc=384M` |
| Android image (first 14,962,688 bytes) SHA-256 | `62d85b36b985187dd1c1543ad4a71fdbaec36b70c448b9c5ff73a5ff82818b9c` |

The kernel and ramdisk sizes differ from the 102K's, so its boot image values don't apply here.

## Backup

Everything before `UDISK` (sectors 0 to 4,268,031, 2,185,232,384 bytes) streamed in 217 s:

```sh
adb exec-out "su 0 dd if=/dev/block/mmcblk0 bs=512 count=4268032 2>/dev/null" | tee >(shasum -a 256) | gzip -1 > pre-userdata.img.gz
```

`/dev/block/mmcblk0` is `root:root 0600`, so `su 0` can read the whole disk even though it can't
open `misc` and `frp` by name. Checks that passed: exact byte count; the gzip readback has the same
SHA-256 as the stream; no aligned 4 KiB block is all `0xCC`; independent re-reads of the first
73,728 sectors, `bootloader`, `env`, `boot`, the first and last 16 MiB of `system`, `misc`,
`recovery`, `metadata`, `private` and `frp` match. User data (photos) was not backed up. Restore
was not tested.

**Trap:** re-reading `media_data` from the whole-disk node with
`dd skip=4235264` returned 0 bytes and `dd: /dev/block/mmcblk0: Invalid argument`. The frame's
32-bit `dd` can't seek past 2 GiB (sector 4,194,304), as on the
[Pastigio FRAME156](pastigio-frame156.md). Read `/dev/block/mmcblk0p16` instead; it matched. A
sequential read from sector 0 is not affected.

## Firmware behaviour that matters

### `BackgroundManagerService`

The same vendor service as on the [QOCEN J1008](qocen-j1008.md#the-firmware-blocks-every-normal-way-to-start-something-at-boot)
is in this build. The log shows `prevent from boot complete broadcast` and
`package not in whitelist: org.mozilla.firefox` / `not whitelist service Intent {...GeckoChildProcessServices$gpu}`.
Firefox still renders the dashboard. Starting something at boot has to go through the **Home**
activity.

### Frameo takes Home back at every boot

With Frameo enabled and a different app chosen as Home with **Always**, the next boot showed
Frameo. `package-restrictions.xml` then listed
`net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted` as the preferred Home, and the log
had a HOME start of Frameo `from uid 0`. Frameo also reset the time zone to its own setting
(`America/New_York`) at boot. After Frameo was disabled, both choices stayed across reboots.

Guess, not verified: the `r.activityInfo.packageName=======` debug lines from `ActivityManager`
next to that start point to a vendor framework patch that forces Frameo as Home.

### Low-RAM mode

`ro.config.low_ram=true`, but the [Denver](denver-pff-1015.md#low-ram-mode-kills-every-app-you-leave)
kill-on-pause did not show: the stock Browser survived pressing Home. Settings was killed later as
`cached #1`, the normal low-RAM trimming of cached processes. There is no
`/system/etc/lowmem_package_filter.xml`.

### SystemUI

`pm list packages -d` was empty at first read. After the first reboot following our changes,
`package-restrictions.xml` had `<pkg name="com.android.systemui" enabled="2" enabledCaller="shell:0" />`.
No command in this session disabled it. No status or navigation bar was visible at any point.
Not explained.

### Wi-Fi

- The XR819 sees 2.4 GHz only. A network that is 5/6 GHz only, or WPA3 only, doesn't appear or
  can't be joined (one nearby network showed as `[WPA2--GCMP-256+CCMP]`).
- On this owner's Wi-Fi 7 router the 2.4 GHz radio had been switched off, and the network still
  appeared now and then in scans. The frame associated once, got no DHCP offer, and was then
  ignored (`CTRL-EVENT-SSID-TEMP-DISABLED ... reason=CONN_FAILED` about 0.6 s after each
  authentication attempt). With the router's 2.4 GHz radio on (802.11n, 20 MHz) it joined and got
  a lease at once. If the frame keeps failing like this, check the router's 2.4 GHz radio before
  the frame.
- No RTC needed in practice: the clock was right once Wi-Fi was up.

## What was set up (approved writes, all in `/data`)

| Change | How | Undo |
| --- | --- | --- |
| Adups FOTA off, before going further online | `su 0 pm disable com.adups.fota`; `enabled="2"` in `package-restrictions.xml` before rebooting; still off after three reboots | `su 0 pm enable com.adups.fota` |
| Time zone Europe/Paris | `su 1000 service call alarm 3 s16 Europe/Paris` (`IAlarmManager.setTimeZone`). Frameo reset it at boot until Frameo was disabled | Same call with the old zone |
| Rootless Pixel Launcher 3.9.1, Firefox 143.0.4 | `adb install`, APKs pinned by the SHA-256 values in [biuframe-setup-guide.md](biuframe-setup-guide.md) | `adb uninstall amirz.rootless.nexuslauncher`, `adb uninstall org.mozilla.firefox` |
| Dashboard as a Firefox web app | In Firefox: menu → **Add app to Home screen** on the dashboard (its manifest has `display: fullscreen`). Then the dashboard opens with no address bar and no status bar from `am start -a mozilla.components.feature.pwa.VIEW_PWA -d <url> -p org.mozilla.firefox` (`ExternalAppBrowserActivity`) | Remove the web app shortcut, or uninstall Firefox |
| A small Home app | Owner-local app, not in this repo: Home activity that waits for a network connection, counts down 5 s, then sends the `VIEW_PWA` intent. It shows **Open now**, **Launcher** and **Android settings** buttons, which are the way back. Chosen with the Home chooser → **Always** | Settings → Apps → the app → Clear defaults, or `adb uninstall` |
| Frameo off | `su 0 pm disable net.frameo.frame`, after the owner checked **by hand on the panel** that the Home app reaches Android Settings → Apps (README rule 9). Then the Home chooser once more (the set of Home apps changed) | `su 0 pm enable net.frameo.frame` |

Result, verified after `adb reboot` with no input: the dashboard is full screen in Firefox about
**151 s** after the reboot command. The time zone stayed on Paris, Frameo and Adups stayed
disabled, and `screen_off_timeout` is `2147483647`, so the screen stays on.

Firefox showing the demo dashboard used about 169 MB (PSS) of the 1 GB.

The way back on this unit: power-cycle the frame, then use the Home app's buttons during the
countdown. USB ADB with the authorized key works throughout.

## Not tested

- A USB-C to USB-C cable, and a second computer (the key check is on, so a new computer needs the
  prompt, which needs SystemUI).
- Whether `com.android.systemui` being disabled stops the "Allow USB debugging?" prompt for a new
  computer.
- WebView 106 through a boot-image change (`/system` is not writable with this `su`).
- Restoring the backup.
- Whether other units from the same listing ship this board.
