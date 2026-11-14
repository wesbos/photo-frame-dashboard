# Uhale B102KZ access report
UHale B102KZ model unit tested on macOS on 2026-11-12. 
This is a Allwinner A33 and distinctly different from the Rockchip [Uhale 102KZ](uhale-102kz.md).
It also differs from the battery-powered [Uhale A33 report](uhale-a33-astar-d7.md).

This unit was only capable of USB power, no data.  The UHale app's 'PC Trasfer' function reported 'disconnected' when plugged in via USB.
No USB device device enumerated in `dmesg` or `lsusb` on Linux or macOS when connected over the Micro-USB port, including during normal boot, while holding the onboard `RECOVER` button, or when booting with a `fel-sdboot` SD card.

W-Fi ADB was achieved following Route S. See [pf1007l-start-here.md](pf1007l-start-here.md) for the Route S overview.

## Hardware & Firmware

| Field | Value |
| --- | --- |
| **Model (`ro.product.model`)** | `B-102K-Z` |
| **Brand (`ro.product.brand`)** | `ALONG` |
| **Device (`ro.product.device`)** | `B-102K-Z` |
| **Board / PCB** | `exdroid` / `M33-V1.0` (`sun8i`, `astar`) |
| **Build ID (`ro.build.display.id`)** | `B-102K-Z-M33-6.0-20240110` |
| **Fingerprint** | `Allwinner/astar_xr819/astar-xr819:6.0.1/MOB30R/20240110:eng/test-keys` |
| **Android / SDK** | Android `6.0.1` (SDK `23`, `armeabi-v7a`) |
| **Kernel** | `3.4.39` (`#244 SMP PREEMPT Tue Jan 9 19:00:14 CST 2024`) |
| **Preinstalled Frame App** | Uhale (`com.zeasn.frame`, `versionName=5.1.0`, `versionCode=5010030`) |
| **Boot Partition (`P03 boot`)** | Sector `172032` (`14,962,688` bytes / `29,224` sectors; page `2048`, kernel `10,221,784` B, ramdisk `4,735,298` B) |
| **Stock `boot` SHA-256** | `4eb4a3bdf6a14b8239c6870f23bd29715ab1e46fbb4ae996bd5d593377c47b3b` |

## Access Path (Route S)

* **Exact ramdisk changes required for Wi-Fi ADB:**
  1. Added `/adb_keys` and TCP port properties (`default.prop`): Installed `~/.android/adbkey.pub` at `/adb_keys` (`0644`) and appended `ro.adb.secure=1` and `service.adb.tcp.port=5555`

  2. Changed `persist.sys.usb.config=none` to `persist.sys.usb.config=adb` (`default.prop`)

  3. Removed `--root_seclabel=u:r:su:s0` from `service adbd` (`init.rc`): Changed `service adbd /sbin/adbd --root_seclabel=u:r:su:s0` to `service adbd /sbin/adbd` 


  `init.usb.rc` contains `on property:sys.usb.config=none && property:sys.usb.configfs=0 -> stop adbd` 

  With `--root_seclabel=u:r:su:s0` present, `init` logged `Service 'adbd' exited with status 1` in a restart loop because `su` is not defined in `/sepolicy`.


* **Resulting shell:** `adb connect <frame-ip>:5555` authenticates with `/adb_keys` and opens `adb shell` directly as `uid=0(root)` (`context=u:r:toolbox:s0`).

## Partition Map (`sunxi-mbr`)

Extracted from the `softw411` partition table at sector `40960` (`20 MiB`):

| Part | Name | Start Sector | Start (MB) | End (MB) |
| --- | --- | --- | --- | --- |
| `P01` | `bootloader` | `73728` | `36.0` | `68.0` |
| `P02` | `env` | `139264` | `68.0` | `84.0` |
| `P03` | `boot` | `172032` | `84.0` | `100.0` |
| `P04` | `system` | `204800` | `100.0` | `1124.0` |
| `P05` | `misc` | `2301952` | `1124.0` | `1140.0` |
| `P06` | `recovery` | `2334720` | `1140.0` | `1172.0` |
| `P07` | `cache` | `2400256` | `1172.0` | `1940.0` |
| `P08` | `metadata` | `3973120` | `1940.0` | `1956.0` |
| `P09` | `private` | `4005888` | `1956.0` | `1972.0` |
| `P10` | `frp` | `4038656` | `1972.0` | `1972.5` |
| `P11` | `empty` | `4039680` | `1972.5` | `1988.0` |
| `P12` | `alog` | `4071424` | `1988.0` | `2068.0` |
| `P13` | `media_data` | `4235264` | `2068.0` | `2084.0` |
| `P14` | `UDISK` | `4268032` | `2084.0` | `2084.0+` |

## Firmware Notes

* **`/sepolicy` domains:** `strings /sepolicy` shows `adbd`, `init`, `shell`, and `toolbox` (and no `su` domain).
* **BusyBox binaries:** `/sbin/busybox` in the boot ramdisk is a minimal build without `telnetd`, `nc`, or `httpd`; `/system/bin/busybox-smp` includes full networking applets.
* **Recovery check:** `/system/bin/install-recovery.sh` verifies `/dev/block/by-name/recovery` (`15,634,432` bytes, SHA-1 `7d003c8ddd597a6d78e24f40d013d051be52a27f`) and does not overwrite `P03 boot`.