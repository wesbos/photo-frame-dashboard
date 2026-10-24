# Skylight Calendar 150-CAL, newer factory firmware (DDR v1.26)

One unit, new in the box, tested 2026-10-24 from a Linux host (Omarchy, Arch-based). It is the same
product as the unit in [next-session.md](next-session.md), but its idbloader carries a newer DDR
build, so `load-usb-reader.py` refuses it by default. This unit reached ADB and a kiosk **without
writing to flash**: a read-only backup, the manufacturer code from the backed-up app, then the
hidden menu. Observations are separate from guesses; guesses are marked.

The frame was never put on Wi-Fi before the vendor app was disabled, so the app could not update
itself first.

## Identify it

Settings → About was not checked on this unit. On the documented unit it was not reachable before
activation, and the setup screen's info icon showed only the MAC address
([research-log.md](research-log.md)). Identify the unit over USB instead (micro-USB **data** cable,
plugged directly into the computer):

| Check | This unit |
| --- | --- |
| Normal boot, `lsusb` | `2207:0007` "D156", MTP only; `adb devices` empty. That is a locked `user` build. Firmware `D156.V0.10` shows ADB instead ([skylight-d156.md](skylight-d156.md)). |
| Loader mode | Hold **Volume −** before plugging in wall power. Black screen, `2207:350a` "USB download gadget". An RK3562 unit needed Volume + ([#222](https://github.com/wesbos/photo-frame-dashboard/issues/222)). |
| `rkdeveloptool rci` | `38 36 35 33` (RK3568 family, as documented) |
| `rkdeveloptool rfi` | **30785536** sectors (the documented unit: 30539776) |
| `rkdeveloptool rcb` | `15 03 …`, as documented |
| Partition table | Same layout and LBAs as documented (`boot` 51200, `recovery` 182272) |
| idbloader at sector 64 | `RKNS` (unsigned v2 format; the RK3562's was `RKSS`, signed), two images, SHA-256 hashes, both copies identical |
| DDR stage | `ddr-v1.26-1e5d6e92ad`, build stamp `26/09/15`, 59,392 bytes, SHA-256 `be6e22b1f4484e5967df85c3a5f5b2bde691e91121d9717296a87a6659a42e02` |

The DDR stage is not byte-identical to any public rkbin v1.26 binary (rkbin commit
`03393656a4bfe05d6e79612597ec54e32c234a4c`). The closest is `rk3568_ddr_1056MHz_v1.26.bin`: 30 bytes
differ, in the build tag, the build date and two 2-byte values.

From the backup afterwards:

- Build fingerprint `rockchip/D156/D156:12/AndroidS/skylightOS-D156-user-release-keys-20250311.212629:user/release-keys`
- Stock `boot` partition SHA-256 `2b9067413dd6e2d8274b2f417499469eb1f09fc76e35c9684d8726c897a10fb8`
- `/system_ext/priv-app/Skylight/Skylight.apk` SHA-256 `af529b5fee62e944e571d3556b606ebcc860fa384bee3e0abd190ef342cf854f`: the same factory 9.29.3 APK
  as [app-analysis.md](app-analysis.md), so its code references apply.

## Back up (read-only)

Same route as [loader-research.md](loader-research.md), with the frame's own DDR stage:

1. Enter Loader mode, then `rkdeveloptool rd 3`. `rkdeveloptool ld` must report `Maskrom`.
2. Prepare the patched helper with `scripts/patch-usb-reader.py`, as documented.
3. `python3 scripts/load-usb-reader.py --frame-ddr --patched`, without `--load`, checks local files
   only. `--frame-ddr` takes the DDR stage from the frame's own idbloader in
   `backups/first-32MiB.img`. It refuses unless the header hash, every image hash and both copies
   check out. It reads the expected sector count from the GPT and saves the DDR stage under
   `diagnostics/stock-loader-research/`.
4. Add `--load` to upload the DDR stage and the patched usbplug v1.14 to RAM. Nothing is written to
   flash.
5. `scripts/probe-reader.py`, then `scripts/backup-flash.py --sectors 30785536`, then
   `scripts/extract-partitions.py`.

Results on this unit. The first backup used an equivalent local script; the `--frame-ddr` code
in this repo was then run on the same unit from Linux (upload, the `rfi` check, `probe-reader.py`,
and a second `--load` that saw the helper and sent nothing):

- The helper answered `rfi` with the expected sector count.
- The probe reads past 32 MiB returned real data, and recovery started with `ANDROID!`.
- The full backup (15,762,194,432 bytes) passed its gzip readback in about 8 minutes.
- Separate re-reads of `boot`, `vbmeta`, a 64 MiB slice of `super`, the last 1 MiB of the disk
  and the first 32 MiB matched the backup.

DDR v1.26 with usbplug v1.14 has been tested on this one unit only. Rockchip's own
`RK3568MINIALL.ini` pairs v1.26 with usbplug v1.17. If the helper doesn't answer, stop. The untested
fallback would be usbplug v1.17 with a new read-limit patch.

### Linux host notes

- `android-udev` doesn't cover Loader/MaskROM mode. Add
  `SUBSYSTEM=="usb", ATTR{idVendor}=="2207", ATTR{idProduct}=="350a", TAG+="uaccess"` to
  `/etc/udev/rules.d/70-rockchip-loader.rules`, then `udevadm control --reload` and
  `udevadm trigger --subsystem-match=usb --attr-match=idVendor=2207` (or replug).
- `scripts/usb-status.py` reads sysfs on Linux.
- The host tools build with gcc against `libusb-1.0`, in their checked-out source folders:

  ```sh
  # rkdeveloptool at 304f073752fd25c854e1bcf05d8e7f925b1f4e14, after scripts/rkdeveloptool-rd6.patch
  echo '#define PACKAGE_VERSION "1.32-304f073"' > config.h
  g++ -O2 -fno-strict-aliasing -D_FILE_OFFSET_BITS=64 -D_LARGE_FILE -DHAVE_CONFIG_H -I. \
    $(pkg-config --cflags libusb-1.0) main.cpp crc.cpp RKBoot.cpp RKComm.cpp RKDevice.cpp \
    RKImage.cpp RKLog.cpp RKScan.cpp $(pkg-config --libs libusb-1.0) -o rkdeveloptool
  # xrock at 50effcef229a7e8ff85fde916e635cdd58fe8c09
  gcc -O2 $(pkg-config --cflags libusb-1.0) -I. *.c $(pkg-config --libs libusb-1.0) -o xrock
  ```

- `scripts/probe-reader.py` reads recovery at LBA 182272, which matches this unit's GPT. Check
  that against your own GPT first.

## ADB from the hidden menu

1. Extract the app from the backup: `lpunpack -p system_ext backups/extracted/super.img <dir>`,
   then `debugfs -R 'dump /priv-app/Skylight/Skylight.apk Skylight.apk' system_ext.img`.
2. Decompile with jadx and read the code check described in [app-analysis.md](app-analysis.md).
   On Linux, jadx 1.5.6 names the files differently from that doc's Mac run: search for
   `compiled from: ManufacturersMenuSubViewModel.kt` (package `p357xb` on this run). The code stays
   out of the repo.
3. On the setup screen, before Wi-Fi: tap the top-left corner five times, enter the code, then
   **Enable ADB** in Dev Tools.

Result: USB ADB as shell (uid 2000) with the normal key prompt, `ro.secure=1`, no root. That was
enough for everything below. The boot-image root route in [debug-ramdisk-research.md](debug-ramdisk-research.md)
was not needed.

## Differences from the documented unit

- **Onboard Wi-Fi works.** Scans found 2.4 and 5 GHz networks, and it connected on 5 GHz with the
  stock radio firmware; no USB dongle was needed.
- **No `skylight.watchdog` and no `skylight.keyboard`.** The only vendor package is `com.skylight`
  (system UID). The default keyboard is AOSP `com.android.inputmethod.latin`.
- `ro.config.low_ram=true`, with no `/system/etc/lowmem_package_filter.xml`. A couple of hours in,
  with the kiosk showing a Home Assistant dashboard, about 640 MB was free and the kiosk hadn't
  been killed.
- The system time zone was GMT.
- The clock chip is a HYM8563 (`rtc0`). On first boot the clock was about six weeks behind. Guess:
  it doesn't keep time without power, so the frame needs network time after a power cut.

## Make it a kiosk

As in [skylight-d156.md](skylight-d156.md#make-it-a-kiosk), but with shell ADB only:

1. Install the kiosk, then make it the Home app ([kiosk README](../dashboard/kiosk/README.md#start-at-boot)).
   `cmd package set-home-activity` failed once ("Failed to set default home") and worked a few
   seconds later, after the Home alias registered.
2. Turn on the navigation service. Check by hand on the panel that the controls reach Android
   Settings.
3. `pm disable-user --user 0 com.skylight`.
4. Then join Wi-Fi in Android Settings. Doing it in this order means the vendor app is never
   online.
5. Set the time zone in Android Settings. As shell, `cmd time_zone_detector
   suggest_manual_time_zone` fails with a `SecurityException`.

On a network without internet access, see
[the kiosk README](../dashboard/kiosk/README.md#networks-without-internet-access). Without that
setting, Android 12 stopped rejoining the frame's Wi-Fi after a reboot.

## Undo

`pm enable com.skylight`, choose Skylight as the Home app, and turn off the navigation service
(`settings delete secure enabled_accessibility_services`). Nothing was written to flash.
