# YunQiDeer YQ156001 15.6" Frameo (Allwinner A133, Android 10)

A record of **one unit**, set up on 2026-10-17. Root ADB over USB with no flashing: turn on
Frameo's ADB toggle, accept the prompt, and `adb shell` is already uid 0. The only hard part was
the cable.

**Tested on:** one unit, bought new on eBay for $59.95 ([item 800520985117](https://www.ebay.com/itm/800520985117),
"YunQiDeer FRAMEO Digital Photo Frame 15.6 in IPS Touch Screen"), from a MacBook (M1, macOS 26.6)
with platform-tools 35.0.2.

## Identity

| Field | Value seen on this unit |
| --- | --- |
| About screen | `YunQiDeer YQ156001`, Frameo `v1.22.5 (43680)` |
| USB | `1f3a:1001`, product `ceres-mcx`, vendor string `Frameo` |
| `ro.product.model` / `ro.product.manufacturer` | `ceres-mcx` / `Frameo` |
| `ro.hardware` / `ro.board.platform` | `sun50iw10p1` (Allwinner A133) / `ceres` |
| Android | 10, `user` build, kernel 4.9.170, `armeabi-v7a` userspace |
| `ro.build.display.id` | `ceres_mcx_V01_24071114` |
| `ro.build.fingerprint` | `Allwinner/ceres_mcx/ceres-mcx:10/QP1A.191105.004/20240711-145712:user/release-keys` |
| RAM / storage | 1 GB with `ro.config.low_ram=true` / 32 GB eMMC (61063168 sectors), 25 GiB userdata |
| Display | 1920x1080, density 210 |
| WebView | `com.android.webview` 74.0.3729.186 |
| Home app (stock) | `net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted`; Launcher3 and SystemUI also installed |
| Vendor updaters | `com.adups.fota`, `com.qiot.update` (both running) |
| Boot image | `boot` (p3, 65536 sectors) SHA-256 `c51e5ee772b0dcad36396c87cceb4fa95745670dc679f895614be51fcae00065` |

## Ports and cable

Back panel, left to right: SD/MMC slot, headphone jack, **USB-A** (host, for thumb drives),
**USB-C** (device port, ADB), 12V DC barrel jack. The frame is powered by the 12V jack, not USB.

- **USB-C to USB-C from the Mac does not work.** The Mac's port stayed at `ConnectionActive = No`
  with no transports in `ioreg`, so the frame doesn't present itself as a USB device on the CC
  lines and the Mac never turns the port on.
- **A cable into the USB-A port does nothing.** That port is a host port.
- **Working:** Mac USB-C → USB-C hub (Anker) → USB-A to USB-C data cable → the frame's USB-C port.

## Getting ADB

1. Frameo Settings → About → **Beta Program** on, then **ADB access** on.
2. Connect as above. `adb devices` first showed `unauthorized` with no prompt on screen.
3. Toggling **ADB access** off and on with the cable plugged in brought up the
   "Allow USB debugging?" prompt. After accepting, the frame showed as `device`.

No ADB on port 5555 was found on the LAN, but the frame was not connected to Wi-Fi at the time.

## Root and security state

- `ro.secure=0`, `ro.debuggable=1`: `adb shell id` returns `uid=0(root)` with context `u:r:su:s0`.
- `/system/xbin/su` is setuid root (`-rwsr-sr-x root shell`) and `su 0 id` also returns root.
- `ro.adb.secure=1`: the key check is on.
- `getenforce` reports **Permissive**, though the kernel command line has `androidboot.selinux=enforcing`.
- `ro.boot.verifiedbootstate=green`, `ro.boot.vbmeta.device_state=locked`, and the eMMC user
  area has a `TOC0.GLH` header at byte 8192 (Allwinner secure boot). The `mmcblk0boot0`/`boot1`
  hardware partitions are empty. Patching `boot` is untested and probably fails verified boot;
  root ADB makes it unnecessary.

## Partition layout

512-byte sectors, from `/sys/block/mmcblk0/mmcblk0p*/start` and `size`.

| Name | Device | Start | Size |
| --- | --- | --- | --- |
| bootloader | p1 | 73728 | 65536 |
| env | p2 | 139264 | 32768 |
| boot | p3 | 172032 | 65536 |
| system | p4 | 237568 | 4194304 |
| vendor | p5 | 4431872 | 737280 |
| product | p6 | 5169152 | 737280 |
| misc | p7 | 5906432 | 32768 |
| recovery | p8 | 5939200 | 85536 |
| cache | p9 | 6024736 | 1572864 |
| vbmeta | p10 | 7597600 | 32768 |
| metadata | p11 | 7630368 | 32768 |
| private | p12 | 7663136 | 32768 |
| frp | p13 | 7695904 | 1024 |
| empty | p14 | 7696928 | 31744 |
| dtbo | p15 | 7728672 | 4096 |
| media_data | p16 | 7732768 | 32768 |
| UDISK (`/data`, f2fs) | p17 | 7765536 | 53297599 |

Unlike the [LOOFII C-3](allwinner-a133-loofii-c3.md), this build has no `super` partition:
`system`, `vendor` and `product` are plain partitions.

## Backup

Everything before userdata over root ADB, about 6 minutes at ~13 MB/s:

```sh
adb exec-out "dd if=/dev/block/mmcblk0 bs=4096 count=970692 2>/dev/null" \
  | tee >(shasum -a 256) | gzip -1 > emmc-0-7765536.img.gz
```

`count` is in 4 KiB blocks: 7765536 sectors / 8. A `bs=1M` read would stop short, because
7765536 sectors is not a whole number of MiB. Verified with the exact byte count (3975954432),
a gzip readback against the stream hash, and on-device re-reads of the first 73728 sectors,
`boot`, 16 MiB of `system`, `recovery`, `vbmeta`, `dtbo` and `media_data`, each matching its
range in the image. The backup GPT is the last 33 sectors (from 61063135).

## Guesses, not tested

- The board looks close to the PF1506 (A133, `ceres`, shipped `su`, permissive SELinux) and
  the [VESWWE DP101](veswwe-dp101.md) (`ceres`, Android 10, Frameo + Adups). The
  [DP101 setup](veswwe-dp101.md#setup-that-worked) is the likely next step here.
- WebView 74 is old. A modern dashboard build will need a low browser target or a newer WebView.
- `ro.config.low_ram=true` may kill background apps the way the
  [Denver PFF-1015](denver-pff-1015.md#low-ram-mode-kills-every-app-you-leave) does. Not checked yet.
