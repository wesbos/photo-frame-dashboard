# Veidoo Frame 10.1" (F10, RK3126, Android 6.0.1)

Record of one unit, started 2026-10-13, Windows host. Observations are kept separate from guesses. Unique identifiers (serial, MAC, IP) live in the ignored `backups/` and `diagnostics/` folders.

Same SoC and Android version as the [BIUFRAME](biuframe.md) and [Rollei Smart Frame 107](rollei-smartframe-107.md), but a different vendor board (`ChipTrip` / `WeiDu`, Wi-Fi chip `rk915`, eMMC storage).


## Observations (read-only unless noted)

### Identity

| Parameter | Value |
| --- | --- |
| Retail name | Veidoo Frame 10.1", IPS touchscreen, 16/32 GB eMMC |
| Brand / Model | `veidoo` / `Frame` (`ro.product.device=F10`, manufacturer `ChipTrip`) |
| Firmware ID | `F606C_WeiDu_Frameo-V1.0.1202603071359.release-keys`, built 2026-03-07 |
| Build Fingerprint | `rockchip/rk312x/rk312x:6.0.1/MXC89K/user.wanghy.20260307.135729:user/release-keys` |
| SoC / Platform | Rockchip RK3126 (`ro.board.platform=rk312x`, `ro.hardware=rk30board`), 32-bit (`armeabi-v7a`) |
| Kernel | Linux 3.10.0 #1 SMP PREEMPT Sat Mar 7 13:56:13 CST 2026 |
| Android | 6.0.1, API 23, security patch 2016-07-05, `user` build, `ro.debuggable=0`, `ro.secure=1` |
| SELinux | **Permissive** (`androidboot.selinux=permissive` on kernel command line) |
| Display | 1280x800, 160 dpi, landscape orientation |
| RAM / Storage | 1 GB RAM, 128 MB ZRAM swap, 30 GB eMMC (`mmcblk0`) |
| WebView | `com.google.android.webview` 107.0.5304.36. Shipped: present on a second unit before anything was installed ([second unit](#second-unit-2026-11-04-macos-host)) |
| Wi-Fi | Onboard radio (`wlan0`), driver module `rk915` |
| SystemUI | `com.android.systemui` is disabled: no status bar or soft navigation keys |
| Shipped Home | `net.frameo.frame` v1.32.15, disabled during onboarding |


### USB, ADB and root

- **ADB:** Frameo Settings → About → Beta Program → ADB Access.
- **USB ADB:** `2207:0006` (MTP/ADB).
- **Network ADB:** on this unit `adbd` also listened on port 5555 (`service.adb.tcp.port=5555`).
  Whether it checks the computer's key was not tested. With the shipped `su`, anything on your
  Wi-Fi may be able to get root. Turn network ADB off when you are done, or keep the frame on a
  trusted network. A second unit with the same firmware did not listen on 5555 (see
  [second unit](#second-unit-2026-11-04-macos-host)), so check yours.
- **Root:** shipped `/system/xbin/su` (SuperSU 2.45). `adb shell su -c id` returns `uid=0(root)`
  with no prompt.

Same family as the BIUFRAME: [`scripts/biuframe-setup.sh`](../scripts/biuframe-setup.sh) and the
[BIUFRAME setup guide](biuframe-setup-guide.md) are the tested route for RK3126 frames. Its BIUFRAME
profile was not run on this unit.

### Vendor packages

Before disabling Frameo (it holds the ADB toggle) and Home, follow README rule 9: confirm USB ADB
still connects with Frameo disabled and that you can reach Android Settings from the kiosk. That
check was not recorded for this unit. SystemUI is disabled from the factory, so there is no
navigation bar; see [the kiosk README](../dashboard/kiosk/README.md#frames-without-home-or-back-buttons).

| Package | How | Undo |
| --- | --- | --- |
| Adups FOTA | `adb shell "su -c 'pm disable-user --user 0 com.adups.fota; pm hide com.adups.fota'"` | `adb shell "su -c 'pm unhide com.adups.fota; pm enable com.adups.fota'"` |
| Adups reboot helper | `adb shell "su -c 'pm disable-user --user 0 com.adups.fota.sysoper; pm hide com.adups.fota.sysoper'"` | `adb shell "su -c 'pm unhide com.adups.fota.sysoper; pm enable com.adups.fota.sysoper'"` |
| Rockchip updater | `adb shell "su -c 'pm disable-user --user 0 android.rockchip.update.service'"` | `adb shell "su -c 'pm enable android.rockchip.update.service'"` |
| Factory test app | `adb shell "su -c 'pm disable-user --user 0 com.DeviceTest'"` | `adb shell "su -c 'pm enable com.DeviceTest'"` |
| Frameo | `adb shell "su -c 'pm disable-user --user 0 net.frameo.frame'"`, after a launcher such as Rootless Launcher ([android-launcher.md](android-launcher.md)) is installed | `adb shell "su -c 'pm enable net.frameo.frame'"` |

Not verified on this unit: the contributor's notes say the Adups packages contain update-server
host names (`fota5p.adups.com`, `fota5p.adups.cn`, `fruet.adups.com`) and can install firmware
remotely, and that the Rockchip updater targets `www.rockchip.com:2300`.

### System CA store (record, not a procedure)

The stock store had 227 certificates, 48 of them expired, and HTTPS to Let's Encrypt sites failed.
On this unit the whole `/system/etc/security/cacerts` folder was replaced with 209 certificates
from several sources, after an archive of the original. The commands, sources and undo were not
published, so don't repeat this. The tested fix is to add only the two ISRG roots, as step 5 of the
[BIUFRAME setup guide](biuframe-setup-guide.md) does, with its undo.

### Performance tuning (record, not a procedure)

These settings were changed on this unit. Nothing was measured before or after, and none of it is
needed for the dashboard. No undo was recorded for the `setprop` and `settings put` changes; a
factory reset clears the `settings` ones. The `/sys` and `sysctl` values go back to
stock at each reboot unless the boot script below runs.

#### 1. Storage Block Layer (`/sys/block/mmcblk0/queue`)
- **I/O Scheduler:** Switched from spinning-disk `[cfq]` to `deadline`.
- **Readahead:** Reduced from `2048 KB` to `512 KB`.
- **Entropy Overhead:** Disabled `add_random` (`0`).
- **Core Affinity:** Set `rq_affinity = 2`.

#### 2. CPU Interactive Governor (`/sys/devices/system/cpu/cpufreq/interactive`)
- **Ramp Threshold:** Lowered `go_hispeed_load` from `99` to `80`.
- **I/O Wait Boost:** Enabled `io_is_busy = 1`.
- **Sample Time:** Set `min_sample_time = 30000` (30 ms) and `above_hispeed_delay = 20000` (20 ms).

#### 3. Virtual Memory & ZRAM (`sysctl`)
- **Swappiness:** Raised `vm.swappiness` from `60` to `80`.
- **Min Free Headroom:** Increased `vm.min_free_kbytes` from `2797 KB` (2.8 MB) to `8192 KB` (8 MB).
- **VFS Cache:** Set `vm.vfs_cache_pressure = 70`.
- **Dirty Flushes:** Set `vm.dirty_ratio = 15` and `vm.dirty_background_ratio = 5`.

#### 4. Background Daemons & CPU Churn
- **Disabled `rild`:** Hardware lacks cellular modem (`ro.baseband=N/A`). Stopped `ril-daemon`.
- **Throttled KSM:** Increased Kernel Samepage Merging (`ksmd`) scan interval from `500 ms` to `2000 ms` (`/sys/kernel/mm/ksm/sleep_millisecs`).
- **Disabled GPS Polling:** Set `location_mode = 0` and cleared `location_providers_allowed` (`ro.factory.hasGPS=false`).

#### 5. 24/7 Display & Android Settings
- **Stay Awake:** Set `global stay_on_while_plugged_in = 3` (AC + USB).
- **Animation Scales:** Configured `animator_duration_scale = 0.5` (was null/1.0), `window_animation_scale = 0.5`, `transition_animation_scale = 0.5`.
- **Forced 2D GPU Acceleration:** Enabled `persist.sys.ui.hw = 1`.
- **Wallpaper Surface:** Enabled `sys.wallpaper.rgb565 = 1`.
- **Disabled Screensaver:** Set `secure screensaver_enabled = 0`.
- **Wi-Fi Background Scans:** Disabled open Wi-Fi notification scans (`wifi_networks_available_notification_on = 0`) and Google captive portal checks (`captive_portal_detection_enabled = 0`).
- **TCP Optimizations:** Configured `net.ipv4.tcp_tw_reuse = 1`, `net.ipv4.tcp_slow_start_after_idle = 0`, and `net.ipv4.tcp_keepalive_time = 300`.

### Boot script (record, not a procedure)

The kernel settings above were put in `/system/su.d/01_optimizations.sh` (root:root, 0755), on the
assumption that SuperSU's `daemonsu` runs `/system/su.d/` at boot. On the BIUFRAME, which uses the
same SuperSU, it **did not** ([biuframe-setup-guide.md](biuframe-setup-guide.md)), and the report
doesn't show that it ran after a reboot here. To check, after a reboot:
`adb shell cat /sys/block/mmcblk0/queue/scheduler` should show `[deadline]`. To remove it:
`adb shell "su -c 'mount -o remount,rw /system; rm /system/su.d/01_optimizations.sh; mount -o remount,ro /system'"`.

```sh
#!/system/bin/sh
# /system/su.d/01_optimizations.sh
# Automatically executed on boot by daemonsu via /system/su.d/

# 1. Stop unnecessary background daemons
# Hardware lacks cellular modem (ro.baseband=N/A); stop polling /dev/ttyACM0
stop ril-daemon

# 2. Storage & Block I/O Optimization (eMMC flash memory)
if [ -e /sys/block/mmcblk0/queue/scheduler ]; then
    echo deadline > /sys/block/mmcblk0/queue/scheduler
fi
if [ -e /sys/block/mmcblk0/queue/read_ahead_kb ]; then
    echo 512 > /sys/block/mmcblk0/queue/read_ahead_kb
fi
if [ -e /sys/block/mmcblk0/queue/add_random ]; then
    echo 0 > /sys/block/mmcblk0/queue/add_random
fi
if [ -e /sys/block/mmcblk0/queue/rq_affinity ]; then
    echo 2 > /sys/block/mmcblk0/queue/rq_affinity
fi

# 3. CPU Interactive Governor Optimization
if [ -e /sys/devices/system/cpu/cpufreq/interactive/go_hispeed_load ]; then
    echo 80 > /sys/devices/system/cpu/cpufreq/interactive/go_hispeed_load
fi
if [ -e /sys/devices/system/cpu/cpufreq/interactive/io_is_busy ]; then
    echo 1 > /sys/devices/system/cpu/cpufreq/interactive/io_is_busy
fi
if [ -e /sys/devices/system/cpu/cpufreq/interactive/above_hispeed_delay ]; then
    echo 20000 > /sys/devices/system/cpu/cpufreq/interactive/above_hispeed_delay
fi
if [ -e /sys/devices/system/cpu/cpufreq/interactive/min_sample_time ]; then
    echo 30000 > /sys/devices/system/cpu/cpufreq/interactive/min_sample_time
fi

# 4. Kernel Samepage Merging (KSM) Rate Limiting
if [ -e /sys/kernel/mm/ksm/sleep_millisecs ]; then
    echo 2000 > /sys/kernel/mm/ksm/sleep_millisecs
fi

# 5. Virtual Memory & ZRAM (sysctl) Tunables
sysctl -w vm.swappiness=80
sysctl -w vm.min_free_kbytes=8192
sysctl -w vm.vfs_cache_pressure=70
sysctl -w vm.dirty_ratio=15
sysctl -w vm.dirty_background_ratio=5

# 6. TCP Network Stack Tunables
sysctl -w net.ipv4.tcp_tw_reuse=1
sysctl -w net.ipv4.tcp_slow_start_after_idle=0
sysctl -w net.ipv4.tcp_keepalive_time=300
```

## Second unit (2026-11-04, macOS host)

A second unit, set up from a Mac over USB. Same firmware ID and build fingerprint as above,
CPU `Rockchip RK3126`, Wi-Fi module `rk915` loaded.

### Observations

- **ADB over USB without the Frameo toggle.** The frame was still on the Frameo first-run
  screen (language picker) and the Beta Program toggle was never used. `adb devices` showed it as
  `device` (authorized) on first connection. Whether an authorization prompt appeared on the
  panel was not recorded. `ro.adb.secure=1`, `persist.sys.usb.config=adb`.
- **Root:** `adb shell su -c id` returned `uid=0(root)` with no prompt, as on the first unit.
- **Network ADB off.** No `service.adb.tcp.port` or `persist.adb.tcp.port` property, nothing
  listening on 5555 in `/proc/net/tcp` or `/proc/net/tcp6`, and the port was closed from the LAN,
  both on Wi-Fi before and after the changes below.
- **WebView 107.0.5304.36 shipped.** It was installed before anything else was.
- **Partition layout** (sectors, from `/sys/block/mmcblk0/mmcblk0pN/start` and `size`):

  | Partition | Start | Size |
  | --- | --- | --- |
  | uboot | 16384 | 8192 |
  | misc | 24576 | 8192 |
  | resource | 32768 | 32768 |
  | kernel | 65536 | 24576 |
  | boot | 90112 | 24576 |
  | recovery | 114688 | 65536 |
  | backup | 180224 | 131072 |
  | cache | 311296 | 262144 |
  | metadata | 573440 | 32768 |
  | kpanic | 606208 | 8192 |
  | system | 614400 | 2097152 |
  | radical_update | 2711552 | 131072 |
  | userdata | 2842624 | 58236928 |

  The eMMC is 61079552 sectors. `boot`, `recovery` and `system` start where the
  BIUFRAME's do, but `userdata` is at 2842624, so `scripts/biuframe-setup.sh` (which has no
  profile for this fingerprint) stops at its fingerprint check. The backup was taken by hand with
  the same method as its `backup` command: `dd` of sectors 0 to 2842624 over `adb exec-out` as
  root, size and gzip-readback checks, then re-reads of `uboot`, `kernel`, `boot`, `recovery` and
  16 MiB of `system` (from sector 647168) that matched. No `0xCC` filler.
- **Running vendor processes before changes:** `com.adups.fota` and
  `android.rockchip.update.service`.

### What was done (in this order)

1. Backup as above.
2. Disabled the updaters and the factory test app with the commands in
   [Vendor packages](#vendor-packages) (both Adups packages also hidden). All four report `enabled=3` and
   stayed disabled across reboots.
3. Installed Rootless Pixel Launcher 3.9.1 from F-Droid (the SHA-256 pinned in
   `scripts/biuframe-setup.sh`). With SystemUI disabled, there was no way back from Settings to
   the launcher on the panel.
4. Built and installed the kiosk from `dashboard/kiosk/` (demo URL). The demo dashboard loaded
   over Wi-Fi with the stock WebView and the stock CA store. The Home HQ navigation accessibility
   service (Settings → Accessibility) gave working floating Back and Dashboard buttons, checked
   by hand on the panel, including Settings → Apps → Frameo. It stayed enabled across reboots.
5. Made the kiosk Home with `--ez home true` and the Home chooser. On this Android 6 chooser,
   tapping **Home HQ** in the list opens it at once as "just once". **Always** appears only
   when the chooser shows a preselected app at the top. If that happens, tap **Always** there.
6. Disabled Frameo (`pm disable-user --user 0 net.frameo.frame`). The saved Home preference
   listed Frameo among its candidates, so Android dropped it and the next boot stopped at the
   Home chooser. After Home HQ was chosen with **Always** again (candidate set now Home HQ and
   Rootless), the following reboot went straight to the kiosk. If the chooser appears after
   disabling Frameo, pick Home HQ with **Always** again.
7. Network ADB turned on at the owner's request: `setprop persist.adb.tcp.port 5555` as root,
   then a power cycle. It survived the reboot, and `su` works over it. An ADB server with a new,
   unknown key stayed `offline` and could not open a shell, so on this unit network ADB checks
   the computer's key. With SystemUI disabled, no prompt to allow a new computer was seen. Don't run `stop adbd; start adbd` in the same `adb shell`: stopping `adbd` kills that shell,
   so `start` never runs and ADB is gone over USB and network until a power cycle.

Not changed: SystemUI, `/system` (no CA, WebView, swap or `build.prop` edits).
