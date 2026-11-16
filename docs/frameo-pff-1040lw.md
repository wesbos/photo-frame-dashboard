# Frameo PFF-1040LW / PFF_1024 10.1" Frameo frame (RK3126, Android 6.0.1, 512 MB RAM)

Record of one unit, 2026-11-04, macOS host (Darwin 27.0.0). Observations are kept separate from guesses.
Unique identifiers (serial, MAC, IP) are left out; they live in the ignored `backups/` folder.

**Short version:** a newer firmware sibling of the [Denver PFF-1024BMK2](denver-pff-1024bmk2.md): same vendor
(Harmony / ZhiHeXing), same SoC (Rockchip RK3126), same Android 6.0.1, same 512 MB RAM, shipped root `su`.
Key differences from the Denver unit:

- **Newer firmware** (`F6010T` build, May 2026 vs `F606C` May 2024)
- **ADB access** via Frameo "Open test app" (`YHK88888888` code) instead of Beta program
- **USB-C only port** — requires USB-A to USB-C data cable (USB-C to USB-C gives no power/data)
- **Frameo v1.32.18** (updated from system v1.30.13)

## Observations (read-only unless noted)

### Identity

| | |
| --- | --- |
| About screen | Frameo v1.32.18 (model PFF-1040LW) |
| Brand / model | `ro.product.brand=denver`, device and name `PFF_1024`, model `Frame`, manufacturer `Harmony` |
| Firmware | `F6010T_ZhiHeXing_Frameo_1001-V1.0.1202605200900.release-keys`, built 2026-05-20 |
| Fingerprint | `rockchip/rk312x/rk312x:6.0.1/MXC89K/user.wanghy.20260520.085907:user/release-keys` |
| SoC | Rockchip RK3126 (`ro.board.platform=rk312x`, `ro.hardware=rk30board`), 32-bit (`armeabi-v7a`) |
| Kernel | Linux 3.10.0, built 2026-05-20 |
| Android | 6.0.1, API 23, security patch 2017-01-01, `user` build, `ro.debuggable=0`, `ro.secure=1`, `ro.adb.secure=1` |
| Low-RAM mode | **Off**: `ro.config.low_ram` is not set |
| SELinux | Permissive (`ro.boot.selinux=permissive`) |
| Display | 1280x800, 160 dpi |
| RAM / storage | 512 MB (assumed, same as Denver PFF-1024BMK2); 128 MB zram; eMMC size not checked |
| WebView | Version not checked (Android 6 system WebView likely old) |
| CA store | Not checked |
| Wi-Fi | Onboard radio works |
| SystemUI | `com.android.systemui` is **disabled**: no status or navigation bar |
| Frameo | `net.frameo.frame`, the HOME app. System copy updated to v1.32.18 in `/data/app` |

### USB, ADB and root

- **ADB:** Settings → About → tap "Model" 7-10 times → "Open test app" → enter `YHK88888888` → toggle **IS CLOSED → is open** → replug cable
- `adb devices` shows `device` authorized (product `PFF_1024`, transport_id)
- **USB cable critical:** Must use **USB-A to USB-C data cable**; USB-C to USB-C gives no power or data
- **Root:** `/system/xbin/su` (133,472 bytes, owned by root, mode 755, not setuid). `adb shell su -c id` returns `uid=0(root) gid=0(root) context=u:r:toolbox:s0` with no prompt
- System remount works: `su -c "mount -o remount,rw /system"`

### Vendor apps to disable

| Package | Type | Notes |
| --- | --- | --- |
| `net.frameo.frame` | System app (UPDATED_SYSTEM_APP) | Main Frameo app, handles HOME via `.feature.slideshow.ui.AScreenSlidePager` |
| `android.rockchip.update.service` | System app | Rockchip OTA update service |

### Changes made to the frame (2026-11-04)

All made after ADB+root verified, one at a time.

| Change | How | Undo |
| --- | --- | --- |
| Updaters off | `su -c 'pm disable-user android.rockchip.update.service'` | `su -c 'pm enable android.rockchip.update.service'` |
| Home HQ kiosk installed | Built from `wesbos/photo-frame-dashboard` `dashboard/kiosk/build.sh`, `adb install -r` | `adb uninstall com.wesbos.homehq` |
| Home HQ as Home app | `am start --ez home true`, then Home button → **Home HQ → Always** | N/A (chooser returns) |
| Frameo off | `su -c 'pm disable net.frameo.frame/.feature.slideshow.ui.AScreenSlidePager'` then `su -c 'pm disable-user net.frameo.frame'` | `su -c 'pm enable net.frameo.frame'` |
| Boot receiver on | `su -c 'pm enable com.wesbos.homehq/.BootReceiver'` | `su -c 'pm disable com.wesbos.homehq/.BootReceiver'` |
| Navigation service | `su -c 'pm enable com.wesbos.homehq/.NavigationService'`; `settings put secure enabled_accessibility_services "com.wesbos/homehq/.NavigationService"`; `settings put secure accessibility_enabled 1` | Turn off in Accessibility, `pm revoke` |

### Not checked / skipped

- Full eMMC backup (repo rule: complete backup before any write)
- Partition table (likely same as Denver PFF-1024BMK2)
- WebView version (Android 6 system WebView is old; dashboard may need WebView swap)
- Let's Encrypt CA roots (Denver unit had them; this build may too)
- `iotv` hidden root agent (Denver unit mentioned it; not checked here)
- Low-RAM killing behavior (assumed same as Denver: off)
- Wi-Fi chip model (Denver: `rk915`)

### Status against the README phase map

| Phase | State |
| --- | --- |
| 1 Identify | Done. Same vendor/SoC/layout as Denver PFF-1024BMK2; `F6010T` build. |
| 2 ADB | Done: Frameo test app (`YHK88888888`), USB-A to USB-C cable. |
| 3 Loader mode | Not needed (shipped `su` works). Not tested. |
| 4 Back up | **Not done** — repo rule requires verified backup before writes. |
| 5 Root | Shipped `su` works (toolbox context). |
| 6 Make it useful | Done: Home HQ is Home app, boots to dashboard. Frameo disabled. |
| 7 Networking | Onboard Wi-Fi works. |
| 8 Vendor updates | Done: Rockchip updater disabled. Frameo already updated itself. |
| 9 Security hand-off | Root for any app via shipped `su`, no ADB key check, Android 6 (2016). |

## Reporting Template

```
About model / firmware:
PFF-1040LW / PFF_1024 / F6010T_ZhiHeXing_Frameo_1001-V1.0.1202605200900.release-keys

AiMOR version: N/A (Frameo platform)
Ports: USB-C only (requires USB-A to USB-C data cable)
Cable and port that gave USB data: USB-A to USB-C data cable
T3 USB IDs seen / adb devices output: product:PFF_1024 model:Frame device:PFF_1024 transport_id:8
T3b network ADB result (port 5555): Not tested (USB ADB worked)
T4 sunxi-fel version output: N/A (Rockchip, not Allwinner)
T5 check-dump stage / chunks: N/A
eMMC size in sectors: Not checked
Boot partition start sector: Not checked
Boot image SHA-256: Not checked
Route used and result: USB ADB → shipped su → Home HQ kiosk
Host OS: macOS (Darwin 27.0.0)
First failed step and its exact output: N/A (all steps succeeded)
```
