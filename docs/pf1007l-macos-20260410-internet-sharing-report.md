# PF1007L / AiMOR 6.0.78 / 20260410 from an Intel Mac: T3c through Internet Sharing, DNS moved to another port

One USB-C-only unit on April `20260410` firmware, set up from an Intel MacBook Pro (T2, USB-C
ports only). Access went the usual April way: no stock ADB, then
[T3c](pf1007l-start-here.md#t3c-temporary-adb-through-the-aimor-connection) and
`persist.sys.usb.config` for root USB ADB, with no boot patch. What is new here:

- **T3c through macOS Internet Sharing when its built-in DNS does not answer.** The router (a
  Telus Technicolor gateway) has no local DNS records, and AiMOR's Wi-Fi screen has no DNS
  setting. The frame joined the Mac's Internet Sharing network, as in
  [#245](https://github.com/wesbos/photo-frame-dashboard/pull/245), but the frame could not resolve
  anything there. A `pf` rule sent the frame's DNS to `dns.py` on port 5300 instead.
- `macos-redirect.sh` from #245 refused to start on this Mac, because `ipconfig getifaddr` printed
  nothing for the sharing bridge.
- A saved factory Wi-Fi network, **`3F-QC-M`**, and a hidden 2013 OpenGL demo in `/system/priv-app`.
- The boot logo `initlogo.rle` is a raw 800×1280 BGRA image, not RLE.
- A Cloudflare custom domain needed **GTS Root R4**, which this unit lacked.

## Unit report

```text
About model / firmware: PF1007L, YHK.F-null-A33-1001-d1024-PF1007L-321-OS-AIMOR.0.20260410
AiMOR version: 6.0.78
Ports (DC jack, or USB-C only): USB-C only, TF slot
Cable and port that gave USB data (or none): the A-to-C cable from the box, in a UGREEN USB-C hub (USB2.0 Hub 05e3:0608) on the Mac. The hub did not enumerate on the first two Mac ports; the third worked.
T3 USB IDs seen / adb devices output: 1f3a:1000 "Android" at 480 Mb/s, `adb devices` empty
T3b network ADB result (port 5555): refused; 8086 open (AiMOR file service)
T4 sunxi-fel version output (or skipped): skipped
T5 check-dump stage / chunks (or skipped): skipped
eMMC size in sectors: 30,777,344
Boot partition start sector: 172032
Boot image SHA-256 (sector 172032, 31,028 sectors): 8ffc2a7d95972422b97ecf7e82da7002011bdacedcbfcc74dd52ae871b98a24e (matches the table)
Route used and result: T3c through macOS Internet Sharing (iPhone USB uplink) with pf redirects of DNS to dns.py on port 5300 and of TCP 7806, then persist.sys.usb.config=mass_storage,adb: root USB ADB (1f3a:1002) after a reboot
Host OS: macOS on an Intel MacBook Pro (T2)
First failed step and its exact output: none
```

## T3c on Internet Sharing when its DNS does not answer

The steps of [#245](https://github.com/wesbos/photo-frame-dashboard/pull/245) were followed until
the frame joined the Mac's network. Three things differed on this Mac.

**The iPhone uplink.** Internet Sharing offered two iPhone interfaces, "iPhone USB" and
"iPhone USB 2". With "iPhone USB" selected as the source, that interface went inactive and the
shared network never came up. With "iPhone USB 2" (a link-local-only interface) selected, the
bridge came up as `bridge103` at `192.168.2.1`, and the Mac's own internet came through
"iPhone USB" as usual. The frame then had an address but no internet, and its Wi-Fi screen showed
error `code002` for both the network and the server connection.

**No DNS on the shared network.** The Mac's sharing DNS on `192.168.2.1:53` did not answer, so
AiMOR never looked up its server and never opened TCP 7806. The 7806 redirect alone did nothing.
Port 53 was already held by macOS, so `dns.py` could not bind it. It ran on another port without
sudo, and `pf` sent the frame's DNS to it:

```sh
/usr/bin/python3 scripts/aimor-network-adb/dns.py --bind 192.168.2.1 --port 5300 \
  --hostname imsconnect.efercro.com --allow-client <frame-ip> --allow-client 192.168.2.1

printf 'rdr pass on bridge103 inet proto { udp tcp } from 192.168.2.0/24 to any port 53 -> 192.168.2.1 port 5300\nrdr pass on bridge103 inet proto tcp from 192.168.2.0/24 to any port 7806 -> 192.168.2.1 port 7806\n' \
  | sudo pfctl -a com.apple/aimor-t3c -f -
sudo pfctl -k 192.168.2.0/24      # drop the frame's existing states so new lookups hit the rules
```

Within a minute AiMOR looked up `imsconnect.efercro.com`, got the Mac's address, logged in
(`110009`), and `server.py` sent the command. `adb connect` gave `uid=0(root)`. No internet was
needed on the frame, as in the [Linux hotspot report](pf1007l-linux-20260416-hotspot-report.md).
Clean up with `sudo pfctl -a com.apple/aimor-t3c -F all` and Internet Sharing off.

**`macos-redirect.sh` from #245.** `ipconfig getifaddr bridge103` printed nothing while
`ifconfig bridge103` showed `inet 192.168.2.1` and `status: inactive`, so the script stopped with
"has no address". Falling back to `ifconfig` fixed it:

```sh
ipconfig getifaddr "$bridge" 2>/dev/null ||
  ifconfig "$bridge" 2>/dev/null | awk '/inet /{print $2; f=1; exit} END{exit !f}' ||
```

Its default `bridge100` was a VM's bridge on this Mac; `BRIDGE=bridge103` was needed. The frame's
address changed after a Wi-Fi toggle (`192.168.2.2`, then `.3`), and `server.py` had to be
restarted for the new one.

Then `setprop persist.sys.usb.config mass_storage,adb` gave root USB ADB right away (`1f3a:1002`),
and it was still there after `adb reboot`.

## Backup

The full eMMC over USB ADB, before any other change, in 59 chunks of 256 MiB with
`/sbin/busybox dd`. Each chunk's byte count and MD5 matched `busybox md5sum` of the same range on
the frame, with no retries. About 50 s per chunk, so about 50 minutes in all. Then: the image's
size, no 1 MiB blocks of `0xCC`, re-reads with the stock `dd` of the bootloader, env, boot, misc,
recovery and system partitions that matched the image, and `gzip -1` with a readback hash that
matched. `mmcblk0boot0` and `boot1` (4 MiB each) were saved too.

## Lock-down and setup

- [T8](pf1007l-start-here.md#t8-lock-it-down-before-the-frame-stays-online): Rootless Launcher
  3.9.1, with Settings → Apps reached by hand on the panel first. Then `com.efercro.os.aimor`,
  `com.yhk.qeota` and `com.DeviceTest` disabled; `enabled="2"` reached
  `package-restrictions.xml` about 10 s later. After a reboot, Rootless was Home and nothing
  listened on 7806, 5555 or 8086.
- **Factory Wi-Fi network.** `wpa_supplicant.conf` held a saved WPA-PSK network named `3F-QC-M`
  (the Linux report found `YHK-03` on its unit). Removed with
  `wpa_cli -i wlan0 remove_network all` and `save_config`, which also removed the Mac's network.
- **"Thomas's room".** The app list showed an app of that name. It is `com.android.gl2jni` at
  `/system/priv-app/tomas/tomas.apk`: a 2013 OpenGL ES demo (`libgl2jni.so`, SDK 7), with only
  storage and wake-lock permissions and no internet permission. It was not running. Disabled with
  `pm disable`.
- **CA roots.** The page is on a Cloudflare custom domain whose certificate chains
  `WE1 → GTS Root R4` (cross-signed by GlobalSign Root CA). This unit had neither GTS Root R4
  (`5acf816d.0`) nor GlobalSign Root CA (`5ad8a5d6.0`), nor GTS Root R1 or ISRG Root X1. The three
  roots in the [Uhale guide](si006-uhale.md#fonts-and-https-photos) were added, checked by SHA-256.
  SELinux was disabled and the existing certificates were `unlabeled`, so no `chcon` was needed.
- **WebView 106** per [section 6 of the guide](allwinner-a33-pf1007l.md#6-upgrade-webview-before-using-the-kiosk).
  `/system` had 405,820 KiB free before. After the reboot, `dumpsys` showed `106.0.5249.126` and
  logcat showed `RelroFileCreator` using `/system/app/webview/lib/arm/libwebviewchromium.so`.
- **The clock** read 1969 until the frame joined the home Wi-Fi. `auto_time` was already 1, and it
  corrected itself once online. The time zone stayed `America/New_York`.
- **Kiosk** built on macOS without installing Java or SDK 34: Android Studio's bundled JBR
  (OpenJDK 25), with `ANDROID_HOME` pointing at a folder whose `platforms/android-34` and
  `build-tools/34.0.0` were symlinks to the installed `android-36` and `36.0.0`. It installed and
  ran. On Android 6 there is no `cmd`, so Home HQ became Home through the chooser (**Always**). The
  single-tap **Menu** button is on.

## Boot logo format

`/system/media/initlogo.rle` (4,096,000 bytes) shows the white "LOVE IS SHARING" screen before the
boot animation. Despite the name it is not RLE565: it is a raw 800×1280 image, 4 bytes per pixel
in BGRA order, rotated 90° because the panel is natively portrait. Its first pixel is
`f8 f0 f7 ff`. A replacement must keep that size and layout. `/system/media/bootanimation.zip`
(1280 800 20, `part0` and `part1`) is the pink-dots animation that follows.

Both were replaced with black versions, the originals kept as `.stock` next to them: an
`initlogo.rle` of the same size filled with `00 00 00 ff`, and a `bootanimation.zip` (stored, not
compressed) whose `desc.txt` is `1280 800 1` / `p 0 0 part0` with one black 1280×800 PNG. After
a reboot the frame came up normally, with Home HQ in front about 25 s after `sys.boot_completed`.
