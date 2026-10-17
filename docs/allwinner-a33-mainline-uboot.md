# Allwinner A33 / PF1007L: root ADB with mainline U-Boot

Tested on one PF1007L on 2026-10-10, from a macOS (Apple silicon) host. The unit is the
**USB-C-only** type described in
[the PF1007L guide](allwinner-a33-pf1007l.md#second-unit-usb-c-only-no-dc-jack): no DC jack,
one USB-C port, a TF slot, an eMMC of exactly 30,535,680 sectors, and the same
`…PF1007L-321-OS-AIMOR.0.20260113` firmware.

The [boot access notes](allwinner-a33-boot-access.md) got root with a custom,
unpublished FEL reader/writer. This guide does the same job with **stock, published tools**:
mainline U-Boot v2025.10, loaded over FEL, exposing the eMMC to the host as a
**read-only** USB disk. That gives a full backup, then a guarded write of the same boot
patch, then root ADB over USB.

Follow the [repository's backup, approval and privacy rules](../README.md#rules-we-learned-the-hard-way)
and read [the AiMOR remote root shell notes](aimor-remote-root-shell.md) first. Everything
below is from one unit. Check each value on your own unit; stop at the first mismatch.

Scripts are in [`scripts/a33-uboot/`](../scripts/a33-uboot).
`emmc-macos.py` also supports Linux: use the bare whole-disk name (for example `sdb`,
not `/dev/sdb`) and the exact byte count from `lsblk -b`, keeping all its identity,
read-only and mount checks. Windows has its own
`-windows.ps1` scripts, see [section 9](#9-windows-host-wsl2--usbipd).

A later [May 2026 macOS unit report](pf1007l-macos-20260529-report.md) reached root
with this route, after locally correcting U-Boot's START STOP handling and adding
write/readback error guards to the generated scripts. Those changes are **not** in
the scripts at the repository revision cited in that report. Read its checks and
limitations before treating the commands below as a tested path for that firmware.

A [May `20260519` Linux report](pf1007l-20260519-linux-report.md) completed a full
user-area backup and post-write comparison with 4-bit / 12 MHz eMMC, a low-power
U-Boot and the START STOP correction. Its source patch is opt-in; the report
records a build-helper SPL-padding limitation, not a change to the default build.

## 1. Get USB data on the USB-C-only unit

The PF1007L guide records this unit type as "the port supplies power only". On this unit,
USB data works. Two things hid it:

| Symptom | Cause | Fix |
| --- | --- | --- |
| USB-C to USB-C from a Mac: no power, no device. `ioreg` shows `ConnectionActive = No` on the port | The frame appears to lack the USB-C CC pull-down resistors, so a USB-C host never detects it or turns on VBUS | Use a **USB-A to USB-C** cable (into a USB-A port, adapter or hub) |
| Frame powered from a hub, but no device on the host | The USB 3 hub's **USB 2.0 half** was missing from the USB tree. The frame is USB 2.0 only | Check that a "USB2.0 Hub" appears in the tree. Moving the hub to the other Mac port brought it back. Then power-cycle the frame |

With a working path, this unit enumerated as:

| State | USB ID |
| --- | --- |
| Stock AiMOR | `1f3a:1000` "Android" |
| FEL (stub card) | `1f3a:efe8`; `sunxi-fel version` → `soc=00001667(A33)` |
| Read-only U-Boot `ums` | "UMS disk 0/1" mass storage |
| After the boot patch | `1f3a:1002`, mass storage + ADB |

On macOS, `ioreg -p IOUSB -l -w0` lists the tree. Vendor `1f3a` is 7994 in decimal.
For a concise tree, use `ioreg -p IOUSB -w 0`. A "Generic Billboard Device" can be
the hub itself; it does not establish that the frame enumerated. A later unit had
intermittent C-to-C data through a hub, but used A-to-C for stable power and data:
see the [cable observations](pf1007l-macos-20260529-report.md#cable-power-and-usb-observations).

## 2. FEL from the SD card (macOS)

Follow section 2 of the [PF1007L guide](allwinner-a33-pf1007l.md#2-use-an-sd-card-for-stable-fel-if-adb-is-absent):
same `sunxi-tools` commit, same stub hash. `sunxi-fel` builds on macOS after
`brew install libusb dtc pkgconf`, and needs no sudo.

The guide's card commands are for Linux. `fel-card-macos.py` is a port with the same
checks (MBR only, no partition before sector 8192, independent re-read, refuses to
overwrite a backup) plus a guard on the exact disk size:

**Use an external USB card reader with this macOS script.** It requires
`Internal=false` and `BusProtocol=USB`. A card in a MacBook's built-in SDXC reader
can be removable but marked internal, and will not appear in `diskutil list
external physical`. Use `diskutil list` and `diskutil info diskN` to diagnose a
missing card, not to bypass the script's target checks. The Windows script's
built-in-reader support does not apply to this macOS port. See the
[additional May-unit observations](pf1007l-macos-20260529-report.md#second-unit-larger-emmc-2026-10-13-access-only-no-backup).

```sh
diskutil list external physical          # before and after inserting the card
diskutil info diskN | grep 'Disk Size'   # the exact byte count
sudo python3 -I scripts/a33-uboot/fel-card-macos.py backup  diskN <exact-bytes>
# With the owner approving this card write:
sudo python3 -I scripts/a33-uboot/fel-card-macos.py write   diskN <exact-bytes>
# Later, to undo:
sudo python3 -I scripts/a33-uboot/fel-card-macos.py restore diskN <exact-bytes>
```

A 32 GB SDHC card worked. On the USB-C-only unit, pulling the USB cable is the power
switch: cable out, card in, cable back. The screen stays dark in FEL.

## 3. Build the read-only U-Boot

`build-uboot.sh` fetches U-Boot v2025.10 (`e50b1e87`, the same base as the boot access
notes), applies [`pf1007l-uboot.patch`](../scripts/a33-uboot/pf1007l-uboot.patch) and builds
it in Docker (Colima works). Output goes to the ignored `diagnostics/a33-uboot-out/`.

```sh
scripts/a33-uboot/build-uboot.sh
```

The patch adds a `pf1007l_backup_defconfig` and a device tree based on the Q8 A33 tablet
reference design:

| Change | Why |
| --- | --- |
| DRAM 456 MHz, ZQ 15291 | The values the boot access notes verified on this board |
| `MMC_SUNXI_SLOT_EXTRA=2` and an 8-bit MMC2 node | The eMMC is on MMC2, 8-bit |
| USB OTG `dr_mode = "peripheral"`, `USB_MUSB_GADGET` | The host must stay the host |
| VBUS drive and `usb0_id_det` removed | The frame is powered **from** the host's VBUS. The stock tablet config can drive VBUS itself |
| `VIDEO_SUNXI` off | The tablet's LCD GPIOs are unverified on this PCB |
| `BOOTDELAY=-2` | No serial console is attached, so noise on the console pin cannot stop autoboot |
| `CRC32_VERIFY` | The write script checks every payload on the device (section 6) |
| **Read-only `ums`**, two layers | `ums_write_sector` refuses all writes, and the LUN reports write-protect to the host |
| DRAM byte lane 0 retrain | On some units (#6) lane 0 comes out of training disabled, so every even byte reads as 0. If a 16-bit bus ends training with lane 0 off, the SPL copies lane 1's config onto it and retrains. A no-op on units where lane 0 trains normally |
| `sunxi-spl-warmup.bin` | A second SPL, built with `-DPF1007L_DRAM_WARMUP`, that returns to FEL right after DRAM init. On #6 the first DRAM init after power-on never trained and the SPL hung; running this first made the next init train (section 4) |

The build prints where the SPL code ends, for both SPLs. Here it was `0x456a`, about 6.6 KB below the
early global-data/stack area. See the boot access notes for why that matters. With the
DRAM changes it was `0x458a`, and `0x45ba` for the warm-up SPL.

The boot access notes say a full RAM-booted U-Boot did not enumerate as a USB disk on
their unit. With the OTG, VBUS and ID changes above, `ums` enumerated on this one.
Which of those changes was decisive was not tested.

## 4. Expose the eMMC read-only and back it up

With the frame in FEL, and the owner approving this RAM payload:

```sh
diagnostics/sunxi-tools/sunxi-fel -v -p uboot diagnostics/a33-uboot-out/u-boot-sunxi-with-spl.bin \
  write 0x43100000 diagnostics/a33-uboot-out/ums-readonly.scr
```

If `sunxi-fel` hangs after loading the SPL on the first run after power-on, the DRAM did not
train. Power-cycle back into FEL and, with the owner approving this RAM payload too, warm the DRAM first:

```sh
diagnostics/sunxi-tools/sunxi-fel spl diagnostics/a33-uboot-out/sunxi-spl-warmup.bin
diagnostics/sunxi-tools/sunxi-fel version     # must answer
```

An answer from `sunxi-fel version` proves only that the warm-up SPL returned to FEL, not that the DRAM
trained. Then run the `uboot` command above. The warm-up SPL only initializes DRAM; it does not touch
storage.

U-Boot runs `ums 0 mmc 0,1`: the SD card and the eMMC appear as two disks. Identify the
eMMC by size. Here it was "UMS disk 1", 15,634,268,160 bytes, **Media Read-Only: Yes**.
If macOS offers to initialize a disk, choose **Ignore**.

Enumeration need not be immediate. On an
[additional May unit](pf1007l-macos-20260529-report.md#second-unit-larger-emmc-2026-10-13-access-only-no-backup),
the first USB and disk checks after `Starting U-Boot` were empty, but the read-only
eMMC appeared on a later check without another power cycle. No exact delay was
measured. Allow a bounded observation period and repeat the read-only USB/disk
checks before declaring failure or sending another RAM payload. `Starting U-Boot`
alone does not prove that UMS is ready. Identify the disk afresh before any backup.

```sh
diskutil list external physical
diskutil info diskN | grep -E 'Media Name|Disk Size|Read-Only'
sudo python3 -I scripts/a33-uboot/emmc-macos.py backup diskN <exact-bytes>
```

`emmc-macos.py` refuses a writable disk, copies the whole eMMC, re-reads it independently,
rejects `0xCC` filler, then gzips it and verifies the readback. Here: about 12.6 MB/s,
two matching passes, zero filler runs, a 372 MB gzip. This is a **full** eMMC backup, not
just system and boot. Keep it private: it holds Wi-Fi credentials and identifiers.

The partition layout matched the tested unit in the PF1007L guide: env at sector 139264,
**boot at 172032**, system (1 GiB ext4) at 237568, **recovery at 2400256**. Parse your own.
`UDISK` (p1) is listed past the end of the eMMC, as the PF1007L guide notes.

### If the UMS disks disappear on macOS

An additional unit lost both read-only disks at about 30 seconds, while its cables
stayed untouched and both hub halves remained enumerated. Null console input alone
did not fix it. A local correction to `do_start_stop()` kept ordinary start/stop
requests from setting `common->eject`; only an unload request ejects. The corrected
build completed two full-device reads. See the [controlled tests and exact source
change](pf1007l-macos-20260529-report.md#ums-disappeared-after-about-30-seconds).
The current build script does not include that correction.
The report includes a [host-only rebuild recipe](pf1007l-macos-20260529-report.md#reproduce-the-ram-only-build)
and a [comparison with other UMS failures](pf1007l-macos-20260529-report.md#distinguish-other-ums-failure-reports).
MMC read errors, loss of power, and a reset into FEL need different evidence from
an idle START STOP exit. Do not copy every board workaround into one build.

If `diskutil info` fails for a previously observed disk, first confirm that the UMS
gadget still exists. After a reload or a script that exposes only eMMC, macOS can
assign a different disk number and U-Boot can label it "UMS disk 0" instead of "1".
Recheck exact size, USB/external identity, media name, and read-only status before
every read. Keep all of `emmc-macos.py`'s guards.

`sudo` may leave the backup files administrator-owned with mode 0600. If tools run
as the owner cannot inspect them, change ownership of only the three backup files,
preserving their private permissions:

```sh
sudo chown "$USER" backups/a33-emmc-full.{img,img.gz,sha256}
```

## 5. Build the boot patch from your own backup

First check the backup offline. `inspect-emmc-backup.sh` touches no device: it reads the image
read-only, and uses Docker with no network for `debugfs`, because macOS has no ext4 tools. It
prints the eMMC size, the partition starts, the T6 boot hash and its firmware-table row, the
`sys.usb.config` triggers in the ramdisk, and the saved USB setting from `/data/property` and
`build.prop`. That last line is the #81 check below, made before the write rather than after it.

```sh
scripts/a33-uboot/inspect-emmc-backup.sh backups/a33-emmc-full.img
python3 -I scripts/a33-uboot/boot-patch.py backups/a33-emmc-full.img <boot-start-sector>
```

`boot-patch.py` only reads your backup. It:

- requires the sector to be a partition start holding a legacy `ANDROID!` image with a
  2048-byte page, no second stage and a matching SHA-1 image ID;
- changes only the `sys.usb.config=mass_storage` action in `init.sun8i.usb.rc`, with the
  same text as the boot access notes, and refuses if the stock action is not there exactly once.
  The frame uses that action only if its saved USB setting is `mass_storage`. On one May unit
  (#81) `/data/property/persist.sys.usb.config` held `ptp`, so the patched image booted with no
  ADB. If a patched frame boots with no ADB, this is the likely cause; the script has no
  `ptp` option yet;
- recompresses the ramdisk and refuses if it does not fit the original slot;
- re-parses both images: exactly one cpio entry may differ, header changes are limited to the
  ramdisk size (bytes 16–19) and image ID (bytes 576–595), nothing after the slot may change;
- writes payloads, `plan.json`, and guarded U-Boot scripts to `diagnostics/a33-boot-patch/`.

**The header write is two sectors, not one.** The image ID ends at byte 595, in the second
sector. Writing only the first 512 bytes would pair a new ramdisk size with the old ID.
Here the ranges were header `[172032, 172034)` and ramdisk `[192004, 203060)`, the same as the
boot access notes.

## 6. Guarded write

`write-boot.scr` runs on the device. It reads the current header and ramdisk slot from the
eMMC, then writes the ramdisk and then the header **only if** all four payloads match their
CRC-32 (`crc32 -v`) **and** the eMMC still holds the original bytes (`cmp.b`). If any check
fails, nothing is written. Either way it ends in read-only `ums`.

The header is written only after the ramdisk write succeeds and reads back equal; the
same holds for restore. This doesn't make the write atomic: a power cut between the two
leaves a new ramdisk with the old header. Editing the `.cmd` without rebuilding and checking
the `.scr` leaves the old commands in the executable image.

With the owner approving **this specific boot-partition write**, power-cycle into FEL and run:

```sh
P=diagnostics/a33-boot-patch
diagnostics/sunxi-tools/sunxi-fel -v uboot diagnostics/a33-uboot-out/u-boot-sunxi-with-spl.bin \
  write 0x50000000 $P/orig-header.bin  write 0x51000000 $P/orig-ramdisk.bin \
  write 0x52000000 $P/new-header.bin   write 0x53000000 $P/new-ramdisk.bin \
  write 0x43100000 $P/write-boot.scr
```

There is no console, so the host verifies the result. When the eMMC reappears read-only:

```sh
sudo python3 -I scripts/a33-uboot/emmc-macos.py verify diskN <exact-bytes>
```

This reads the whole eMMC. Every byte must equal the backup, except the planned ranges,
which must equal the patched payloads. A mismatch does not by itself prove that the
guard refused the write: an operation may have been incomplete. Only a complete
match with the unchanged original proves the original bytes remain. If neither the
full original nor the backup plus exact plan matches, stop and investigate. The whole-disk
check is only exact if Android hasn't booted since the backup; Android changes userdata.
If it has, take a fresh read-only backup before the next write (#81).

A first attempt here read the 5.4 MiB payloads back over FEL before starting U-Boot. The
read timed out (`usb_bulk_recv() ERROR -7`). `sunxi-fel` stopped before "Starting U-Boot",
so nothing was written, and the frame needed a power cycle. The cause was not found. Checking
the payloads with `crc32 -v` on the device avoids the large FEL reads.

**Undo:** `restore-boot.scr` is the mirror image. It writes the original bytes back only if
the eMMC holds exactly the patched bytes. Load the same four payloads with `restore-boot.scr`
at `0x43100000`, then run `emmc-macos.py verify-original`.

## 7. Boot and continue with the PF1007L guide

Unplug, remove the card, plug back in. AiMOR boots as before. Here USB showed `1f3a:1002`,
and `adb -d shell id` returned `uid=0(root)` without `su`. Continue at
[section 3 of the PF1007L guide](allwinner-a33-pf1007l.md#3-confirm-root-adb-before-the-android-setup).
Disable AiMOR and `com.DeviceTest` before the frame spends more time online.

## 8. Notes from this unit after root

Observations from the setup in the PF1007L guide (launcher, WebView 106, kiosk):

- **No SystemUI.** The firmware has no `com.android.systemui`: no status bar, navigation bar or
  notification shade. Settings has no Back button. `qemu.hw.mainkeys=0` in `build.prop`
  (the [BIUFRAME fix](biuframe-setup-guide.md)) has no effect here; it was reverted.
  To leave an app, power-cycle into a Home app or use `adb shell input keyevent KEYCODE_HOME`.
- **Boot broadcasts are filtered.** Allwinner's `BackgroundManagerService` delivers
  `BOOT_COMPLETED` only to a built-in whitelist (AiMOR, the updater, Frameo and others).
  `dumpsys background` shows it. Logcat shows `prevent from boot complete broadcast: <package>`.
  A kiosk with a boot receiver will not start. Declaring the kiosk activity as a
  `HOME` app does work: Android opens Home at boot. Expect the first page load to fail
  until Wi-Fi is up, so retry.
- **Let's Encrypt.** The stock trust store has no ISRG Root X1; the kiosk logged
  `Trust anchor for certification path not found` (`net_error -202`). Adding it as
  `/system/etc/security/cacerts/6187b673.0` (root:root 0644; PEM block first, then the
  `openssl x509 -text -fingerprint -sha1` dump, like the stock files) fixed it. Check the
  SHA-256 fingerprint `96:BC:EC:06:26:49:76:F3:74:60:77:9A:CF:28:C5:A7:CF:E8:A3:C0:AA:E1:1A:8F:FC:EE:05:C0:BD:DF:08:C6`
  against a second source before installing. The guide's alternative, a host proxy, avoids
  changing `/system`.
- **Cloudflare Workers.** On a `FL-AIMOR-OS.0.20260519` unit, the stock trust store also had
  no GlobalSign Root CA (`5ad8a5d6.0`) and no GTS roots. A dashboard deployed to
  `*.workers.dev` failed the same way (`net_error -202`): its chain ends at GTS Root R4,
  cross-signed by GlobalSign Root CA. Adding GTS Root R1 (`f013ecaf.0`), GTS Root R4
  (`5acf816d.0`) and ISRG Root X1 (`6187b673.0`), with the SHA-256 values from the
  [Uhale guide](si006-uhale.md), fixed it. A custom domain on Cloudflare served a Google
  Trust Services certificate too, so it needs the same roots.
- **WebView 106 features**, measured with `CSS.supports` and syntax checks in the kiosk:

  | Missing | Present |
  | --- | --- |
  | `oklch()`, `color-mix()` (Tailwind v4 colours), CSS nesting, `#rrggbbaa`, `:has()` | `@layer`, `@property`, grid, flex `gap`, `aspect-ratio`, container queries, `backdrop-filter`, async/await, `?.`, `??`, `#private`, `Array.at`, `findLast`, `structuredClone`, `fetch`, `EventSource`, `WebSocket`, ES modules |

  Viewport 1280×800, `devicePixelRatio` 1.
- **Time zone.** It shipped as `America/New_York`. `adb shell service call alarm 3 s16 <Area/City>`
  changes it.
- **Two more units (2026-10-11, Linux host, FEL eMMC reads/writes of the boot partition).**
  Both had byte-identical boot partitions (31028 sectors at LBA 172032), so one patched
  image served both. Notes from bringing them to WebView 106 + kiosk-as-Home over network ADB:
  - **Avoid `adb reboot` and `setprop sys.powerctl reboot`.** On both units shutdown hung
    (other reports agree, though one unit rebooted cleanly):
    ADB accepted the command, then the frame stopped answering shell commands (ping and
    port 5555 still up) until it was unplugged. Power-cycle instead. On a hub,
    `uhubctl -l <hub> -p <port> -a off`, wait 8 s, `-a on` worked cleanly and touched nothing else.
  - **First boot after the WebView 106 swap froze a hub-powered unit** about 26 s in, right
    after `Running dexopt ... webview.apk` and `insmod aic8800_fdrv.ko`. Booting once with
    Wi-Fi off (`svc wifi disable` during the short ADB window, then power-cycle; the owner
    set `wifi_on` to `0` in `settings_global.xml` directly, which is riskier) let dexopt finish. `svc wifi enable` afterwards, and
    later boots with Wi-Fi on were fine. The wall-powered unit did not need this.
  - **Clock stuck at 1969.** One unit had `settings get global auto_time` = `null`, so it never
    took network time and the dashboard showed Wednesday, December 31.
    `settings put global auto_time 1` fixed it. Check this before blaming the page.
  - **Random MAC each boot.** Adding `MAC_ADDR=` to
    `/system/vendor/modules/aic_userconfig_8800dc.txt` is read by the driver but ignored
    (only txpwr and xtal settings are parsed), and a one-shot `ip link set wlan0 address` did
    not stick. PR #6's looping `frame-fixmac.sh` is the approach to try for DHCP reservations.
    Otherwise find frames by serial: scan port 5555, then `getprop ro.serialno`.
  - Wi-Fi ADB (`persist.adb.tcp.port 5555`) survived every power cycle, but
    `svc wifi disable` / `enable` killed the listener until the next boot.
- **Speaker.** The A33 `audiocodec` drives a working speaker. The kiosk's
  `setMediaPlaybackRequiresUserGesture(false)` lets a page autoplay audio. No microphone
  feature is declared.

## 9. Windows host (WSL2 + usbipd)

This section runs sections 2 to 7 from Windows 11. The Linux tools (`sunxi-fel`, the U-Boot
build, `boot-patch.py`) run in WSL2. USB devices reach WSL through
[usbipd-win](https://github.com/dorssel/usbipd-win) (4.0 or later). Two PowerShell ports of the macOS
scripts handle the steps where Windows owns the device:

| Script | Port of | Why it runs on Windows |
| --- | --- | --- |
| `fel-card-windows.ps1` | `fel-card-macos.py` | The SD card reader belongs to Windows |
| `emmc-windows.ps1` | `emmc-macos.py` | U-Boot's `ums` disk must stay with Windows (see below) |

They keep the same checks and the same files in `backups/` and `diagnostics/`. `backup`,
`verify` and `verify-original` all work in 1 GiB segments and resume after a dropout, like the
macOS `-resume` modes. Disk reads bypass the Windows cache (`FILE_FLAG_NO_BUFFERING`), so the
second read of each segment comes from the eMMC.

**What was tested.** One unit (#6, Windows 11 Pro, WSL2 Ubuntu, usbipd-win 5.3) went through
FEL over usbipd, a RAM-loaded U-Boot, Windows reading the `ums` disk, and a full backup with
two matching passes. That unit used an earlier, writable U-Boot build (v2025.01, eMMC 4-bit at
26 MHz), not this repository's read-only build. Both scripts were tested against disk images:
backup, gzip readback, resume, the fingerprint, the `0xCC` filler check, verify against a
plan, and card write and restore. Neither has run against a frame yet. The boot-partition
write (section 6) has not been done from Windows.

### Set up the host

Clone the repository inside WSL (for example `~/photo-frame-dashboard`). PowerShell reaches
it as `\\wsl.localhost\<distro>\home\<you>\photo-frame-dashboard`, and the scripts accept that
path. In WSL, build `sunxi-fel` and check the stub as in section 2 of the
[PF1007L guide](allwinner-a33-pf1007l.md#2-use-an-sd-card-for-stable-fel-if-adb-is-absent).
Run `build-uboot.sh` (section 3) in WSL with Docker.

In an Administrator PowerShell:

```powershell
usbipd policy add --effect Allow --operation AutoBind --hardware-id 1f3a:efe8   # FEL may go to WSL
Get-StorageSetting | Select NewDiskPolicy        # note it, to restore later
Set-StorageSetting -NewDiskPolicy OfflineAll     # new disks stay offline: nothing is mounted
```

`OfflineAll` matters. Without it, Windows mounts the frame's partitions as they appear and
offers to format some of them (the MBR labels the ext4 `/data` partition as FAT32).
`emmc-windows.ps1` refuses a disk that is online. Cancel any "format this disk" prompt.

Both settings stay after a reboot. **Undo them when you are done:**

```powershell
Set-StorageSetting -NewDiskPolicy <the value you noted>   # usually OnlineAll or OfflineShared
usbipd policy list                                        # find the 1f3a:efe8 policy's GUID
usbipd policy remove --guid <guid>
```

### FEL card

`fel-card-windows.ps1` has passed backup, write and readback on one real 4 GB card (#98). Windows'
default partition on that card started at 1 MiB; the script needs no partition before 4 MiB
(sector 8192), so recreate the partition at 4 MiB first.

Run these in an Administrator PowerShell from the repository root. `Get-Disk` before and after
inserting the card identifies it (Number, Size).

```powershell
powershell -ExecutionPolicy Bypass -File scripts\a33-uboot\fel-card-windows.ps1 backup  <n> <exact-bytes>
# With the owner approving this card write:
powershell -ExecutionPolicy Bypass -File scripts\a33-uboot\fel-card-windows.ps1 write   <n> <exact-bytes>
# Later, to undo:
powershell -ExecutionPolicy Bypass -File scripts\a33-uboot\fel-card-windows.ps1 restore <n> <exact-bytes>
```

It accepts USB and built-in SD readers, refuses a system or boot disk, and needs an MBR card
whose first partition starts at sector 8192 or later.

### FEL over usbipd

Put the frame in FEL with the card (section 2). In PowerShell:

```powershell
usbipd list                                   # the frame shows as 1f3a:efe8
usbipd attach --wsl --busid <busid>
```

Then, in WSL, `diagnostics/sunxi-tools/sunxi-fel version` must show `soc=00001667(A33)`. Every
power cycle re-enumerates the frame, so attach again each time. On #6, FEL from the reset button
alone, without the card, lasted a second or two: too short to attach.

Two WSL gotchas from #119: clone this repo with `git -c core.autocrlf=false`, because CRLF
checkouts break `build-uboot.sh` and `git apply`; and if Docker Desktop has no WSL integration,
the `docker` in PATH is `docker.exe`, which needs Windows-style paths for `-v` — a small shim that
rewrites `/mnt/<drive>/` to `<DRIVE>:/` lets `build-uboot.sh` run unchanged.

### Load U-Boot and back up

From WSL, load U-Boot as in section 4. The frame drops off WSL and comes back as U-Boot's mass
storage gadget (`1f3a:1010`), which Windows reads directly.

**Never attach `1f3a:1010` to WSL.** On #6, the rebind reset the gadget and it did not come
back until the frame was power-cycled into FEL again. Do not use `usbipd attach --auto-attach`
on the frame's bus ID, because it would attach the gadget as well.

`Get-Disk` lists U-Boot's LUNs as `Linux UMS disk 0` (SD card) and `Linux UMS disk 1` (eMMC).
Identify the eMMC by size, and check that it shows `IsReadOnly` = `True` and `IsOffline` = `True`.
If it is not read-only, the read-only build is not the one running: stop. **Never use
`Set-Disk -IsReadOnly` to get past this check**; if `IsReadOnly` is `False`, stop and report it. Then:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\a33-uboot\emmc-windows.ps1 backup <n> <exact-bytes>
```

On #6 (4-bit, 26 MHz build) Windows read the disk at about 5.7 MB/s, about 45 minutes per pass
over a 15.7 GB eMMC. The script reads each segment twice, so plan on about 90 minutes plus
compression. If the disk drops, the script saves its progress. Power-cycle into FEL, attach,
load U-Boot again, and rerun the same command. The disk number can change, so check `Get-Disk`
again.

### Patch, write and verify

`boot-patch.py` (section 5) runs in WSL on the backup unchanged. For the guarded write
(section 6), attach FEL and run the `sunxi-fel` command from WSL. When the eMMC comes back
read-only, verify from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\a33-uboot\emmc-windows.ps1 verify <n> <exact-bytes>
# after restore-boot.scr instead:
powershell -ExecutionPolicy Bypass -File scripts\a33-uboot\emmc-windows.ps1 verify-original <n> <exact-bytes>
```

After the patch the frame boots as `1f3a:1002`. Either attach it to WSL with `usbipd attach`
and use `adb` there, or use the Windows platform tools directly.
