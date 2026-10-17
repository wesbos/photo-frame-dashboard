# Frameo "Digital Photo Frame 102k" (KJM, Rockchip RK3326): ADB, cleanup and kiosk

Tested on one unit on 2026-10-11. Hosts: macOS (Apple silicon) for most of the work, and a
Windows PC for the one step that needed USB. This frame runs the **Frameo** app. It is not
the RK3126 BIUFRAME in the video or the Allwinner A33 PF1007L, so their boot patches and
scripts do not apply here. The [VESWWE DP100](veswwe-10.1.md) uses the same S101 board but
runs Android 8.1 and ships `su` and `adb root`; this one runs Android 11 and has no root. Compare
the build strings in section 1 before you follow this page.

An Allwinner A33 frame with the same `Digital Photo Frame` model and a `102K` product name is in
[frameo-102k-a33.md](frameo-102k-a33.md). Both boards have come from listing B088NHSVJN: the A33
from Amazon.ca, this one from Amazon México. Before ADB is on, the USB vendor ID tells them
apart: `2207` (Rockchip, manufacturer `KJM`) is this frame; `1f3a` is the Allwinner one.

No exploit is needed. Frameo has an official ADB switch, and every step below runs as the
normal ADB shell user. This unit has no root.

Follow the [repository's approval and privacy rules](../README.md#rules-we-learned-the-hard-way).
Everything below is reversible. Undo commands are listed with each step.

## 1. Identify the frame

Frameo: Settings → About shows the Frameo version. The rest comes from `adb shell getprop`
(section 2).

| Item | Observed value |
| --- | --- |
| Sold as | "Digital Photo Frame 102k", Frameo app v1.29.13 |
| `ro.product.brand` / `model` | `KJM` / `Digital Photo Frame` |
| Build ID | `S101-C-KJM-BND-20260106` |
| Build fingerprint | `KJM/Digital-Photo-Frame/Digital-Photo-Frame:11/RQ3A.210705.001/eng.zcx.20260106.102227:user/release-keys` |
| Vendor fingerprint | `rockchip/rk3326_rgo/rk3326_rgo:11/RQ3A.210705.001/zcx01061022:user/release-keys` |
| Device tree | `Rockchip rk3326 S101 101 avb board`, compatible `rockchip,rk3326-s101-aic8800` |
| SoC | Rockchip RK3326: 4× Cortex-A35 at 1.5 GHz, Mali-G31. Userspace is 32-bit (`armeabi-v7a`) |
| Android | 11 (SDK 30), Android Go build (`rk3326_rgo`), `user` / `release-keys`, security patch 2022-03-05 |
| Kernel | 4.19.193, built 2026-01-06 |
| RAM | 1 GB (984,052 kB) |
| Storage | Raw NAND (`/dev/block/rknand0`), not eMMC. `/data` is 25 GB |
| Wi-Fi / Bluetooth | AICSemi AIC8800 on SDIO (`aic8800_fdrv`, `aic8800_bsp`). Wi-Fi country code `CN` |
| Display / touch | 1280 × 800, density 160. Touch `gslX680-d708`, plus a `gsensor` |
| Ports | One USB-C (device mode, UDC `ff300000.usb`), microSD slot, reset button |
| WebView | 106.0.5249.126, the version the [dashboard](../dashboard) already targets |
| Bootloader | `ro.boot.flash.locked=0`, `ro.boot.verifiedbootstate=orange`. Looks unlocked; not tested |
| Time zone | Ships as `America/New_York` |

`BND` in the build ID matches the package of the Adups updater it ships, `com.bnd.update`
(section 4).

## 2. Get ADB

1. On the frame: **Settings → About → Enable Beta Program**. An **ADB access** switch then
   appears. Turn it on. This is
   [Frameo's documented route](https://support.frameo.com/hc/en-us/articles/6126183308434--How-to-Enable-ADB-on-Your-Frame).
2. Connect a **USB-A to USB-C** data cable from a USB-A port on the computer to the frame, and
   run `adb devices`. Accept the "Allow USB debugging" prompt on the frame.
   This build has SystemUI, so the prompt does appear.
3. Run `adb tcpip 5555`. From then on, `adb connect <frame-ip>:5555` works from any computer on
   the same network. Accept the prompt again for each new computer.

Cables, as observed:

- **USB-A to USB-C from a Windows PC's USB-A port: works.** USB ADB came up.
- **USB-C to USB-C from a Mac: nothing.** No USB device appeared on the Mac in either plug
  orientation, and `adb devices` was empty. USB-A to USB-C from the Mac was not tried. The Mac
  had no USB-A port or adapter.
- **USB-A to USB-C from a Mac's USB-A port: works** ([second unit](#second-unit-amazon-méxico)).
  It enumerated as `2207:0007` (MTP), then `2207:0006` once ADB access was on.
- This matches the [PF1007L](pf1007l-start-here.md#the-usb-a-to-usb-c-rule): use a USB-A to
  USB-C cable. On a USB-C-only computer, use a USB-C to USB-A adapter or hub.
- Before `adb tcpip`, port 5555 was closed on the network. ADB over Wi-Fi needs one USB
  session first.

### Keep network ADB on across reboots

`adb tcpip` stops at the next reboot. On this build the shell user can set two persistent
properties that bring it back:

```sh
adb shell setprop persist.internet_adb_enable 1   # Rockchip hook, see below
adb shell setprop persist.adb.tcp.port 5555       # read by adbd at start
```

`/vendor/etc/init/hw/init.rk30board.rc` contains Rockchip's "Internet adb" hook:
`on property:persist.internet_adb_enable=1` sets `service.adb.tcp.port 5555` and restarts
`adbd`. After a reboot, port 5555 was open again within about a minute, without USB. Verified
once on this unit.

`ro.adb.secure=1`, so only computers whose key you already accepted can connect. The port is
still open to anything on the local network. Consider a guest or IoT Wi-Fi network for the
frame.

Undo: `setprop persist.internet_adb_enable 0` and `setprop persist.adb.tcp.port ""`.

## 3. Root: not available

- `/system/xbin/su` exists, mode `-rwsr-sr-x root shell`. From the ADB shell it fails:
  `su 0 id` gives `setgid failed: Operation not permitted`, and `su -c` is not supported.
- `ro.debuggable=0`, `ro.secure=1`. `adb root` does not apply.
- SELinux reports `Permissive`.
- The bootloader properties above suggest a Magisk-patched boot image flashed with fastboot
  could work. **Not tried.** It needs a USB data connection and a full backup first, and no
  backup procedure for this NAND layout is documented yet.

An app may still be able to use that setuid `su`. Treat every app on this frame as if it has
root.

## 4. Vendor apps

`pm list packages -s` shows 147 system packages. Apart from AOSP and Google WebView, these
stand out:

| Package | Path | What it is | Notable granted permissions |
| --- | --- | --- | --- |
| `net.frameo.frame` | `/system/priv-app/Frameo` | Frameo, the default Home app | |
| `com.bnd.update` | `/product/priv-app/FotaUpdate` | **Adups FOTA** 5.30. The dex contains `https://fota5p.adups.cn` and `https://fota5p.adups.com`. Flag `PERSISTENT` | `REBOOT`, `RECOVERY`, `WRITE_SECURE_SETTINGS`, `RECEIVE_BOOT_COMPLETED`, `INTERNET` |
| `android.rockchip.update.service` | `/system/app/RKUpdateService` | Rockchip OTA updater, runs as `system` | `REQUEST_INSTALL_PACKAGES`, `DELETE_PACKAGES`, `RECOVERY`, `READ_LOGS` |
| `com.cghs.stresstest` | `/system/priv-app/StressTest` | Factory stress test, runs as `system`. Flag `PERSISTENT` | Same set as RKUpdateService |
| `com.DeviceTest` | `/system/priv-app/DeviceTest` | Factory test app, runs as `system` | Same set as RKUpdateService |
| `org.chromium.webview_shell` | `/product/app/Browser2` | WebView test browser. Its `WebViewAnimationTestActivity` was in the foreground once after a boot | `INTERNET` |

Adups is the updater that Kryptowire reported in 2016 for sending texts, contacts and call logs
from budget phones to servers in China, and for remote app installs. We did **not** capture its
traffic on this frame. We only checked its URLs and permissions.

No user-installed apps, accessibility services, notification listeners or device admins were
present.

### Remove them for the user

`pm disable-user` is enough for most of these. **It is not enough for `PERSISTENT` apps.**
After a reboot, `com.bnd.update` and `com.cghs.stresstest` were running again while still
marked disabled, and Adups crash-looped, restarting about every 3 seconds. Removing them for
user 0 stopped Adups at once and kept both off after the next reboot:

```sh
adb shell pm disable-user --user 0 android.rockchip.update.service
adb shell pm disable-user --user 0 com.DeviceTest
adb shell pm disable-user --user 0 org.chromium.webview_shell
adb shell pm uninstall -k --user 0 com.bnd.update
adb shell pm uninstall -k --user 0 com.cghs.stresstest
```

A running `system`-uid process (the stress test) cannot be stopped from the shell. It stays up
until the next reboot.

Undo: `pm enable <package>`, or `cmd package install-existing <package>` for the two removed
ones. The APKs stay in `/system` and `/product`.

### Frameo and Wi-Fi

`adb shell pm disable-user --user 0 net.frameo.frame` worked. Right after it, the ADB
connection dropped. When the frame came back, Wi-Fi was enabled but not connected, and `wlan0`
had no address. The cause is not known; Frameo may manage the saved network. Rejoining from
ADB fixed it, and the network stayed saved through later reboots:

```sh
adb shell cmd wifi status
adb shell cmd wifi connect-network "<ssid>" wpa2 "<password>"
```

If you disable Frameo, do it while you still have USB ADB, or be ready to rejoin Wi-Fi from
Android Settings.

## 5. Dashboard kiosk

The [kiosk app](../dashboard/kiosk) runs on this WebView 106 as is. Build and install it as in
the [kiosk guide](../dashboard/kiosk/README.md). On macOS, Homebrew's `openjdk@17` works if the
Temurin cask cannot install without sudo.

To boot into the dashboard, the kiosk has to be the Home app. [#43](https://github.com/wesbos/photo-frame-dashboard/pull/43) adds that as an opt-in, plus a
saved dashboard URL. With it, this unit rebooted straight into the dashboard:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity --ez home true --es url https://your-dashboard/
adb shell cmd package set-home-activity com.wesbos.homehq/.Home
```

At boot the kiosk can start before DNS works. On this unit the first three loads once got
`ERR_NAME_NOT_RESOLVED`. The kiosk's retry on failed loads covers that.

With `org.chromium.webview_shell` disabled, the kiosk is the only app that handles `http(s)`
links. If another app opens a sign-in page, it appears in the kiosk.

## Second unit (Amazon México)

A second unit, ASIN B088NHSVJN, set up on 2026-10-17 from an Intel Mac (macOS 12.7.6). The
build ID, both fingerprints, WebView and Frameo versions match section 1, and `su 0 id` fails
the same way.

- **ADB without Wi-Fi:** Wi-Fi was not connected when ADB access was turned on and the vendor
  apps and Frameo were removed or disabled.
- **Adups did not stop at once:** `com.bnd.update` and `com.cghs.stresstest` were still running
  right after `pm uninstall -k --user 0`, and were gone after the next reboot.
- **Home app:** `cmd package set-home-activity com.wesbos.homehq/.Home` printed
  `Error: Failed to set default home.` while Frameo was enabled, and `Success` after
  `pm disable-user --user 0 net.frameo.frame`. Whether timing played a part is not known.
- **Network ADB:** `setprop persist.internet_adb_enable 1` (see
  [Keep network ADB on across reboots](#keep-network-adb-on-across-reboots)) restarted `adbd`
  and dropped USB ADB for a few seconds. After a reboot, 5555 was listening again.

## Open questions

- Whether a USB-C-only Mac works through a USB-C to USB-A adapter. USB-C to USB-C did not; a
  Mac's built-in USB-A port did.
- Whether a Magisk-patched boot image works, and how to back up the `rknand` partitions first.
- What Adups actually sends when it is left on.
- Why Wi-Fi lost its network after Frameo was disabled.
