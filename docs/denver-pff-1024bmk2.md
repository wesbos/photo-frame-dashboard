# Denver PFF-1024BMK2 10.1" Frameo frame (RK3126, Android 6.0.1, 512 MB RAM)

Record of one unit, 2026-10-15, Linux host (NixOS). Observations are kept separate from guesses.
Unique identifiers (serial, MAC, IP) are left out; they live in the ignored `backups/` folder.

**Short version:** a newer sibling of the [Denver PFF-1015](denver-pff-1015.md): same vendor
(Harmony / ZhiHeXing), same partition layout, same 512 MB of RAM, ADB from Frameo's beta settings
and shipped root `su`. It differs in ways that make it easier:

- **No low-RAM mode.** `ro.config.low_ram` is not set, and apps you switch away from are not killed,
  so the PFF-1015's `lowmem_package_filter.xml` edit is not needed.
- **Let's Encrypt roots ship** in the system CA store.
- Wi-Fi chip `rk915` (the PFF-1015 has `ssv6158`), and an `F606C` build like the [Veidoo F10](veidoo-f10.md).

## Observations (read-only unless noted)

### Identity

| | |
| --- | --- |
| About screen | Denver, Frameo v1.32.16 |
| Brand / model | `ro.product.brand=denver`, device and name `PFF_1024`, model `Frame`, manufacturer `Harmony` |
| Firmware | `F606C_ZhiHeXing_Frameo_1004-V1.0.1202405271346.release-keys`, built 2024-05-27 |
| Fingerprint | `rockchip/rk312x/rk312x:6.0.1/MXC89K/user.liubc.20240527.134541:user/release-keys` |
| SoC | Rockchip RK3126 (`ro.board.platform=rk312x`, `ro.hardware=rk30board`), 32-bit (`armeabi-v7a`) |
| Kernel | Linux 3.10.0, built 2024-05-24 |
| Android | 6.0.1, API 23, security patch 2016-07-05, `user` build, `ro.debuggable=0`, `ro.secure=1`, `ro.adb.secure=1` |
| Low-RAM mode | **Off**: `ro.config.low_ram` is not set |
| SELinux | Permissive (`androidboot.selinux=permissive` on the kernel command line) |
| Display | 1280x800, 160 dpi |
| RAM / storage | **512 MB** (`MemTotal: 504424 kB`), 128 MB zram; 15.5 GB eMMC (`mmcblk0`, 30,310,400 sectors) |
| WebView | `com.android.webview` 44.0.2403.119, too old for the dashboard |
| CA store | ISRG Root X1 (`6187b673.0`) and X2 (`8794b4e3.0`) already present; SHA-256 fingerprints match Let's Encrypt's |
| Wi-Fi | Onboard radio works, driver module `rk915` |
| SystemUI | `com.android.systemui` is **disabled**: no status or navigation bar |
| Frameo | `net.frameo.frame`, the HOME app. The system copy (`/system/priv-app/Frameo.apk`) is from 2024; Frameo updated itself to v1.32.16 in `/data/app` as soon as it was online |

### USB, ADB and root

- **ADB:** Frameo → Settings → Beta program → ADB access. USB `2207:0006`, product `PFF_1024`.
- `adb devices` showed `device` (authorized) straight away, with no prompt, and there is no
  `/data/misc/adb/adb_keys` or `/adb_keys`, although `ro.adb.secure=1`. As on the PFF-1015, `adbd`
  appears not to check keys (one computer tested).
- No network ADB: the only TCP listener is Frameo's own (uid of `net.frameo.frame`, a random high
  port). With Frameo disabled there are no listeners.
- **Root:** `/system/xbin/su` (SuperSU, `daemonsu` alongside). `adb shell su -c id` returns
  `uid=0(root)` with no prompt.
- **Frameo holds a root session:** `ps` shows `daemonsu:<Frameo's uid>` while Frameo runs.

### Partition table (eMMC `mmcblk0`, 512-byte sectors)

From `mtdparts` on the kernel command line and `/sys/block/mmcblk0/mmcblk0pN/start`; eMMC sector =
loader sector + 8192. Identical to the [PFF-1015](denver-pff-1015.md#partition-table-emmc-mmcblk0-512-byte-sectors)
except for the size of `userdata`.

| Partition | Name | Start | Size (sectors) |
| --- | --- | --- | --- |
| p1 | uboot | 16384 | 8192 |
| p2 | misc | 24576 | 8192 |
| p3 | resource | 32768 | 32768 |
| p4 | kernel | 65536 | 24576 |
| p5 | boot | 90112 | 24576 |
| p6 | recovery | 114688 | 65536 |
| p7 | backup | 180224 | 131072 |
| p8 | cache | 311296 | 262144 |
| p9 | metadata | 573440 | 32768 |
| p10 | kpanic | 606208 | 8192 |
| p11 | system | 614400 | 2097152 |
| p12 | radical_update | 2711552 | 131072 |
| p13 | userdata | 2842624 | 27467776 |

### Backup (verified)

A **partial backup**, like the PFF-1015's: `userdata` was excluded, so it does not meet the repo's
complete-device backup rule, and restore is untested. It covers every partition this record writes to.

eMMC sectors 0-2,842,624 (everything before `userdata`), 1,455,423,488 bytes, streamed with
`adb exec-out "su -c 'dd if=/dev/block/mmcblk0 bs=512 count=2842624'"`. The raw stream SHA-256 equals
the gzip readback; no 512-byte sector is all `0xCC`; independent re-reads of the loader area, `uboot`,
`misc`, `resource`, `kernel`, `boot`, `recovery`, `backup`, `kpanic`, `system` and `radical_update`
from their own block devices match the backup.

| Image | SHA-256 (whole partition) |
| --- | --- |
| `boot` (p5) | `71cc322600c0ca0966bb5fb9f0de7db332098da6f14b85047ab1125aad349a2c` |
| `recovery` (p6) | `880d7717ed5c8f97988ccd95ec674858236a11af158872addcef9dc16e7a69e2` |
| `kernel` (p4) | `536bea183a5f868338e7bf96c73f12e40b7eda0dc8958f767bab72f6c8ddeac9` |

### No low-RAM killing

Tested the PFF-1015's way: open an app, switch away from it, and read the events log.

```sh
adb logcat -b events -c
adb shell am start -n com.android.music/.MusicBrowserActivity; sleep 3
adb shell input keyevent KEYCODE_HOME; sleep 3
adb logcat -b events -d | grep -E "am_kill|am_on_paused"
```

Music was paused and not killed; there was no `user request after error` kill. Processes were only
reclaimed later as ordinary cached processes (`cached #1`). `/system/etc/lowmem_package_filter.xml`
exists, but in the PFF-1015's decompiled framework the kill only runs when `ro.config.low_ram=true` or
`ro.target.product=vr`; neither is set here (this unit's framework was not decompiled). With the kiosk installed, Home HQ stays alive while
Settings is open and its floating Back/Dashboard buttons show over Settings, with no whitelist edit.

## Changes made to the frame (2026-10-15)

All made after the verified backup, one at a time, each with its undo recorded first. The steps of
[biuframe-setup-guide.md](biuframe-setup-guide.md) were run by hand, as on the PFF-1015
(`scripts/biuframe-setup.sh` was not run).

| Change | How | Undo |
| --- | --- | --- |
| Updaters and test apps off | `pm disable` `com.adups.fota`, `com.adups.fota.sysoper`, `android.rockchip.update.service`, `com.DeviceTest`, `com.android.rk`, `com.android.rk.mediafloat` (there is no `com.cghs.stresstest` on this build) | `pm enable` each |
| WebView 44 → 106.0.5249.126 | BIUFRAME `step_webview`: same pinned LineageOS APK, `lib/arm/*.so` extracted, `oat/` removed, `webview.apk.bak` kept | Copy `webview.apk.bak` back, `rm -rf lib`, reboot |
| zram 128 → **256 MB** | `scripts/biuframe-su.d-50zram` with `268435456`, run from a line appended to `/system/bin/install-recovery.sh` (`.bak` kept) | Copy the `.bak` back, `rm -r /system/su.d`, reboot |
| Rootless Pixel Launcher 3.9.1, Home HQ kiosk | `adb install`; Home HQ made the Home app (`--ez home true`, then **Home HQ → Always** in the chooser) | `adb uninstall` |
| Home HQ navigation buttons | `pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS`; `settings put secure enabled_accessibility_services com.wesbos.homehq/com.wesbos.homehq.NavigationService`; `settings put secure accessibility_enabled 1` | Turn it off in Accessibility settings, `pm revoke` |
| Frameo off | `su -c 'pm disable net.frameo.frame'`, after the owner checked by hand that the kiosk's Dashboard and Back buttons and two-finger menu reach Android Settings → Apps | `su -c 'pm enable net.frameo.frame'` (its data is untouched) |

Skipped: Let's Encrypt roots (already present), the `lowmem_package_filter.xml` edit (no low-RAM
mode), Firefox (512 MB RAM), and the navigation-bar `build.prop` line (SystemUI is disabled).

Verified after reboots:
- `versionName=106.0.5249.126`, with `RelroFileCreator` loading `/system/app/webview/lib/arm/libwebviewchromium.so`.
- Swap is `262136` kB, and no updater, test-app or Frameo processes are running.
- `boot` and `recovery` are unchanged against the backup.
- The frame boots straight into Home HQ, and the dashboard loads over HTTPS once Wi-Fi is up.

Same as the PFF-1015 when disabling Frameo:

- **Wait before rebooting.** `enabled="2"` reached `/data/system/users/0/package-restrictions.xml`
  10 s after `pm disable`. Check for it before you reboot.
- **The Home chooser comes back** once, this time as "Use Home HQ as Home". Tap **Always**; after that
  the frame boots straight into the dashboard.

USB ADB keeps working with Frameo disabled (`persist.sys.usb.config=adb`).

## Status against the README phase map

| Phase | State |
| --- | --- |
| 1 Identify | Done. Same vendor and partition layout as the PFF-1015; `F606C` build like the Veidoo F10. |
| 2 ADB | Done: Frameo beta setting, USB. |
| 3 Loader mode | Not needed. Not tested. |
| 4 Back up | Done and verified (partial: `userdata` excluded). Restore untested. |
| 5 Root | Shipped `su` works. |
| 6 Make it useful | Done: Home HQ is the Home app and the frame boots into the dashboard. Frameo is disabled. |
| 7 Networking | Onboard Wi-Fi works. |
| 8 Vendor updates | Done: Adups FOTA and the Rockchip updater are disabled. Frameo had already updated itself once it was online. |
| 9 Security hand-off | Same as the [Rollei 107](rollei-smartframe-107.md#security-notes-for-the-owner): root for any app (Frameo used it), no ADB key check, Android 6 from 2016. |
