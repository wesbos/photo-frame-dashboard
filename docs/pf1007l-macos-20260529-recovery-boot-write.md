# PF1007L 20260529 (macOS): root ADB over USB, boot patch written in stock recovery, no SD card

One unit, firmware `YHK.F-null-A33-1001-D1024-PF1007L-V10-1680.0.20260529`, AiMOR 6.0.78,
USB-C port only (no DC jack), powered and connected with a USB-A to USB-C data cable, eMMC
30,535,680 sectors. Host: macOS 26.6 (Apple silicon), adb 37.0.1.
Dates: 2026-10-12 and 2026-10-13.

This unit had no stock ADB (T3, T3b) and no SD card. It got root ADB over USB with the
**Route U boot patch**, written over USB in the root-ADB window that stock recovery opens during
an AiMOR factory reset. [#49](https://github.com/wesbos/photo-frame-dashboard/pull/49) found that
window on April firmware and used it to read. This page reports a **write** through it.

**Read this first:**

- One unit, one firmware. Other firmware is untested for this write.
- Each attempt is a factory reset. It erases the frame's user data.
- If a write is cut off, Android may not boot. Then the AiMOR Recovery Mode screen is out of reach
  (it is an app screen), and the only documented repair is Route U or Route S, which need an SD
  card. Have a spare SD card before you write, even though this route does not use one.
- Do T6 first. If your boot image hash is not in the
  [firmware table](pf1007l-start-here.md#known-firmware-and-units), ask in an issue before you write.

## 1. Before root: T1 to T3b on this unit

| Test | Result |
| --- | --- |
| T1 | `…PF1007L-V10-1680.0.20260529`, model `AEEZO`, `ro.es_frame.product` `PF1007` |
| T2 | USB-C port only, no DC jack. All work used a USB-A to USB-C data cable |
| T3 | `1f3a:1000` "Android" (vendor string "USB Developer"), one mass-storage interface (class 8/6/80), `adb devices` empty. **Stock ADB off**, like #16 and #28 |
| T3b | Frame on Wi-Fi, internet paused for that one device on the router. TCP 8086 open (AiMOR file service), **TCP 5555 refused** |
| T4 | Skipped: no SD card |

**Power and cable observations** (one unit):

- The supplied A-to-C cable powered the frame but carried no data (charge-only).
- A data-capable A-to-C cable in the USB-A port of an Apple USB-C Digital AV Multiport Adapter:
  the frame booted, then **shut off at the AiMOR loading screen**, on every attempt. This was the
  same with the adapter on its charger and with screen brightness at minimum. The Mac saw `1f3a`
  only for moments during boot.
- The same data cable on a USB-A wall charger: the frame stayed on.
- The same data cable on a powered dock (Plugable USBC-7400H4): the frame stayed on, with stable
  `1f3a:1000`. Use a direct port or a powered hub, as the start page says.
- Guess, not measured: the adapter port limits current once a data connection is up.

**Reset pin:** holding the reset pin keeps the board in reset (screen black). On release, the
frame boots normally. The `1f3a:efe8` device appears for about 3 s at every power-on, at
480 Mb/s, `bcdDevice` 0xFFFF, one vendor-class interface. `sunxi-fel version` fails with
`usb_bulk_recv() ERROR -1: Input/Output Error`. Real FEL on this family is 12 Mb/s with a dark
screen ([May report](pf1007l-macos-20260529-report.md#cable-power-and-usb-observations)). This
matches #49 section 10: it is not the Boot ROM's FEL.

## 2. Stock recovery's root ADB on this firmware

Same route as #49: hold the reset pin while connecting power, release, then choose
**Factory reset** on AiMOR's Recovery Mode screen. AiMOR asks you to finish setup before it offers
another factory reset.

| | Observed on 20260529 |
| --- | --- |
| USB ID | `18d1:d001`; `adb get-state` reports `recovery` |
| Window | 17 s, 13 s, 13 s, 15 s (four resets, from `18d1:d001` up to gone) |
| First command | Answered at once (a pull started 0 s after the state read `recovery`) |
| Recovery `default.prop` | `ro.secure=0`, `ro.adb.secure=0`, `ro.debuggable=1` |
| File transfer | Works as root: `adb ls`, `adb pull` of block devices, `adb pull` of `/sys/class/block/*` |
| Pull speed | 8.5 MB/s (boot, 33,554,432 bytes in 3.8 s) |

## 3. Find the boot node from sysfs, and push to that node

Two facts decide where a write lands. Both were wrong in this unit's first two write attempts,
and the script's checks stopped both before any byte was written.

**`/dev/block/by-name/*` are symlinks** (`adb ls` mode `0000a1ff`). On Android 6, adbd's push
(`file_sync_service.cpp`, `do_send`) **unlinks** a regular file or symlink before it writes. A
push to `/dev/block/by-name/boot` replaces the link with an ordinary file in recovery's
`/dev` and writes nothing to the eMMC. It still reports success. Push to the real node.

**Read the node number from sysfs** (`/sys/class/block/mmcblk0pN/start` and `size`). This unit has 16 partitions and **no `mmcblk0p4`** in recovery:

| Node | Start sector | Name |
| --- | --- | --- |
| p1 | 4366336 | UDISK |
| p2 | 73728 | bootloader |
| p3 | 1 (2 sectors) | none (extended-partition container) |
| p5 | 139264 | env |
| **p6** | **172032** | **boot** (65,536 sectors) |
| p7 | 237568 | system |
| p8 | 2334720 | misc |
| p9 | 2400256 | recovery |
| p10 to p16 | 2465792 and up | cache, metadata, private, frp, empty, alog, media_data |

Names come from `readlink /dev/block/by-name/*` after root. Recovery's `uevent` files had no
`PARTNAME`, so the script matches on start sector and size. #62 also reports boot as p6.

**How an existing block device is written:** adbd opens it without truncation (`O_EXCL` fails
with `EEXIST`, then it opens `O_WRONLY`) and writes from byte 0. A short file overwrites only its
own length. Closing the device flushes it: Linux 3.4 `__blkdev_put` calls `sync_blockdev` when
the last opener closes. Recovery reboots through `android_reboot()`, which calls `sync()` first.
These come from the Android 6.0.1 and Linux 3.4.39 sources (the frame's kernel is 3.4.39). The
read-back in section 5 is the check on the device.

## 4. What was written

The same patch as Route U: [`boot-patch.py`](../scripts/a33-uboot/boot-patch.py)'s `build()` and
`verify()`, run on the boot partition pulled in the first recovery window. One ramdisk file
changes, `init.sun8i.usb.rc`: the stock `mass_storage` USB action also enables `adb`, selects
product ID `1002` and starts `adbd`. Header changes are limited to the ramdisk size and image ID.

| | SHA-256 |
| --- | --- |
| Original image (sector 172032, 31,028 sectors) | `6c118dc1aa583797884c33cd3ac3796c72b2bd3a3f1fcafd1bf0982ae5f29e2c` |
| Patched image | `8c05b34e4b4b2bd09ea2d6f86b29e0a5b62bfd18d69b1648269a7eee55c7c84b` |

Changed sectors, relative to the partition: `[0, 2)` and `[19972, 31027)`. Absolute:
`[172032, 172034)` and `[192004, 203059)`. These match the Route U ranges in the start page; the
slot's last sector is identical in both images. The 15,886,336-byte image was written, not the
whole 32 MiB partition. Bytes past the image are unchanged.

Two pushes, so the header changes last:

1. **Push A** (15,886,336 bytes): original header and kernel, patched ramdisk slot. Rewriting the
   kernel region writes identical bytes.
2. **Push B** (1,024 bytes): the patched two header sectors.

## 5. The run that worked (2026-10-13)

| Time | Event |
| --- | --- |
| 00:07:01.33 | `18d1:d001`, state `recovery` |
| 00:07:01.83 | Boot node found: `mmcblk0p6`, block device, start 172032, size 65536 |
| 00:07:01.84 to 03.95 | Push A (2.1 s) |
| 00:07:03.98 | Push B done, 2.7 s into the window |
| 00:07:10.25 | Read-back pull done |
| 00:07:10.34 | Read-back SHA-256 = patched image |
| 00:07:16 | Recovery rebooted (window 15 s) |
| 00:07:41 | Android up as `1f3a:1002` |
| 00:08:37 | `sys.boot_completed=1`; `adb -d shell id` → `uid=0(root)`; fingerprint `AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260529:eng/test-keys` |

**How this run differed from the published script** (owner-approved, kept here for honesty):

- It did **not** re-read the boot partition inside the write window before pushing. It relied on
  the copy pulled in the first window (factory reset wipes `/data`, not boot). The published
  script adds that pre-write read, about 4 s, so its pushes land later in the window: about
  6 to 8 s in, against a shortest observed window of 13 s.
- No full eMMC backup existed before the write: only the boot partition (the one written), its
  hash verified by T6. After root, the firmware range (sectors 0 to 4366336) and `mmcblk0boot0/1`
  were backed up with `adb exec-out 'dd … 2>/dev/null'`, and every partition's on-device MD5
  re-read matched the backup (16 of 16).
- Two earlier write attempts aborted before writing: the script looked for `mmcblk0p4`
  (section 3).

After root, the start page's T7 and T8 passed (AiMOR, `com.yhk.qeota` and `com.DeviceTest`
disabled, `enabled="2"` persisted, no `:7806` connection after a power cycle), then WebView 106
per the PF1007L guide.

## 6. Scripts

All three are in [`scripts/a33-uboot/`](../scripts/a33-uboot). Outputs go to the ignored
`diagnostics/`. Run from the repository root.

```sh
# 1. In one factory reset: copy boot (and env, misc, bootloader, recovery) and print the T6 hash.
scripts/a33-uboot/recovery-pull.sh
# Compare the hash with the firmware table. Stop if it is not there.

# 2. On the host: build the patch from that copy. Refuses an image with a different hash.
python3 -I scripts/a33-uboot/recovery-patch-build.py diagnostics/recovery-pull/try1/boot.img <T6-sha256>

# 3. Optional, in another factory reset: identify the node, read boot, classify it. No write.
scripts/a33-uboot/recovery-patch.sh check

# 4. With the owner approving this write, in another factory reset:
scripts/a33-uboot/recovery-patch.sh write
```

Start each script **before** you start the factory reset; they wait for `18d1:d001`.

`recovery-patch.sh write` stops with no write if: the plan's payloads do not match their hashes;
no node has start 172032 and size 65536; two nodes match; the node is not a block device; or the
partition does not hold the original image. After the pushes it reads boot back and reports
patched, original, or neither.

The scripts were checked against a simulated `adb` that models this unit (16 partitions, boot on
p6, symlinked `by-name`, refused pushes, unreadable sysfs, a slow first listing). On the real
unit, the write ran with an earlier version of `recovery-patch.sh` (differences above).

## 7. Undo

- **Patched frame boots (the normal case):** you have root ADB. Write the original image back from
  the running system, no window needed. Each check stops before the write if it fails:
  ```sh
  P=diagnostics/recovery-patch
  want_patched=$(python3 -c "import json;print(json.load(open('$P/plan.json'))['sha256']['patched-image.bin'])")
  want_orig=$(python3 -c "import json;print(json.load(open('$P/plan.json'))['sha256']['original-image.bin'])")
  # 1. The frame must still hold exactly the patched image.
  [ "$(adb -d exec-out 'dd if=/dev/block/mmcblk0p6 bs=512 count=31028 2>/dev/null' | shasum -a 256 | cut -d' ' -f1)" = "$want_patched" ] || echo "STOP: boot is not the patched image"
  # 2. The file you push must be the original, before and after the push.
  [ "$(shasum -a 256 < $P/original-image.bin | cut -d' ' -f1)" = "$want_orig" ] || echo "STOP: original-image.bin changed"
  adb -d push $P/original-image.bin /data/local/tmp/boot-orig.img
  [ "$(adb -d exec-out 'cat /data/local/tmp/boot-orig.img' | shasum -a 256 | cut -d' ' -f1)" = "$want_orig" ] || echo "STOP: push corrupted"
  ```
  Only if none of those printed `STOP`, write and read back:
  ```sh
  adb -d shell 'set -e
  [ "$(cat /sys/class/block/mmcblk0p6/start)" = 172032 ]
  dd if=/data/local/tmp/boot-orig.img of=/dev/block/mmcblk0p6 bs=1048576
  sync'
  adb -d exec-out 'dd if=/dev/block/mmcblk0p6 bs=512 count=31028 2>/dev/null' | shasum -a 256
  ```
  The last hash must be the original image's (`$want_orig`).
- **Patched frame does not boot:** restore with Route U (FEL from the SD card stub) and
  `restore-boot.scr`, or Route S. This route cannot reach recovery without a booting Android.

## 8. Not tested

- Any firmware other than May `20260529` and `20260519` (the second was confirmed by another owner on a
  30,777,344-sector unit, in the PR #65 thread), including April units with recovery ADB (#49).
  `recovery-patch-build.py` refuses other boot images.
- ~~The larger 30,777,344-sector eMMC.~~ Confirmed on 2026-10-14 with the published scripts on a
  30,777,344-sector Humblestead unit from macOS ([report](pf1007l-macos-20260529-humblestead-report.md)):
  window about 18 s, pushes in 5 s, read-back matched, root on the next boot.
- `recovery-patch.sh` as published, on a real frame: the write in this guide used an earlier version;
  the Humblestead report above used the published one.
- A write interrupted mid-push, and the undo in section 7 on a real frame.
- Windows and Linux hosts.

## Report

```text
About model / firmware:  PF1007L, YHK.F-null-A33-1001-D1024-PF1007L-V10-1680.0.20260529
AiMOR version:           6.0.78 (code 78)
Ports (DC jack, or USB-C only): USB-C only (no DC jack); USB-A to USB-C data cable
Cable and port that gave USB data (or none): data A-to-C cable on a powered dock (Plugable USBC-7400H4). Apple USB-C Digital AV Multiport Adapter USB-A port: frame shut off at the AiMOR screen. Supplied cable: charge-only.
T3 USB IDs seen / adb devices output: 1f3a:1000 "Android", mass storage only; adb devices empty
T3b network ADB result (port 5555): refused (TCP 8086 open)
T4 sunxi-fel version output (or skipped): skipped (no SD card); power-on efe8 window: usb_bulk_recv() ERROR -1
T5 check-dump stage / chunks (or skipped): skipped
eMMC size in sectors:    30,535,680
Boot partition start sector: 172032 (node mmcblk0p6)
Boot image SHA-256 (sector 172032, 31,028 sectors): 6c118dc1aa583797884c33cd3ac3796c72b2bd3a3f1fcafd1bf0982ae5f29e2c
Route used and result:   Route U boot patch written over USB in stock recovery's root-ADB window (AiMOR factory reset), no SD card. Read-back matched; next boot 1f3a:1002, uid=0(root).
Host OS:                 macOS 26.6 (Apple silicon)
First failed step and its exact output: none in the final run; two earlier write attempts stopped before writing because mmcblk0p4 does not exist
```
