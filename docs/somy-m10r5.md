# Pastigio / SOMY M10R5 10.1" (Frameo, Allwinner A33 `astar_xr819`, Android 6.0.1)

Record of one unit, tested on 2026-10-30, on macOS on Apple silicon. Observations are kept separate
from guesses. The serial, MAC addresses, eMMC CID and whole-disk hashes are left out. Another
M10R5, on a later firmware, is reported in
[#177](https://github.com/wesbos/photo-frame-dashboard/issues/177).

This is a record, not a procedure. The backup, key edit and write used one-off local tools that
aren't in this repo, and the write ranges only fit this unit. The repo's nearest writer is
[`data-patch-prepare.py`](../scripts/a33-uboot/data-patch-prepare.py), described in
[pastigio-zc002.md](pastigio-zc002.md). It hasn't been run on an M10R5.

**Short version:** ADB was `unauthorized`, as in #177. The 4-bit 26 MHz build that worked in #177
showed no USB disk on this unit, and the no-HS build worked. After a full backup, adding a host key
to userdata gave authorized ADB, with boot and system unchanged. Home HQ runs as Home, and Frameo
is still installed.

## Identity

| Item | This unit | #177 |
| --- | --- | --- |
| About screen | `DPF M10R5` | `DPF M10R5` |
| Firmware | **`M10R5_20260313`** | `M10R5_20260617` |
| Fingerprint | `Allwinner/astar_xr819/astar-xr819:6.0.1/MOB30R/20260313:eng/test-keys` | Same, dated `20260617` |
| Security patch | 2018-08-05 | 2018-08-05 |
| Frameo | v1.29.14 (60300). An offered update was declined | v1.30.19 (69880) |
| Stock boot partition (16 MiB) SHA-256 | `bde00bf535e84a78f7082b6ff03f7668002577c68a5e7980cf5f9634e446e157` | `7c4def9257b3ce76831d5c36811e7b21109a85c5cb5cfa2484326534497c0508` |
| eMMC | **31,268,536,320 bytes** | 31,406,948,352 bytes |
| Userdata | Sector 4268032, 29,083,303,936 bytes | 29,221,715,968 bytes |
| Display | 1280×800, 160 dpi | 1280×800, 160 dpi |
| WebView | 106.0.5249.126 | 106.0.5249.126 |
| SELinux | Permissive | Permissive |
| USB IDs | `1f3a:1001`; FEL reports `soc=00001667(A33)` | `1f3a:1001`, FEL `1f3a:efe8` |

The two eMMCs differ by 138,412,032 bytes, and the two userdata sizes differ by the same amount.
#177's sizes also work out to userdata starting at sector 4268032. So the difference looks like
the end of userdata only, though #177 doesn't state the start directly. Boot is at sector 172032
and system at 204800, 1 GiB, matching the [ZC002 table](pastigio-zc002.md#somy-zc002-unit-identity).

The firmware's boot hash and the eMMC size both differ between units of this model, so check each
one rather than assuming either.

## ADB before the change

- USB showed an ADB interface, and `adb devices` said `unauthorized`.
- The backup showed `ro.adb.secure=1`, `persist.sys.usb.config=adb`, no `adb_keys` file, and
  `com.android.systemui` disabled (state 2). The disabled SystemUI fits #177's finding that no
  authorization prompt appears.
- `/data/misc/adb` is owned by 1000:2000, mode 02750, labelled `u:object_r:adb_keys_file:s0`.

## Getting to a read-only eMMC

The FEL stub on a spare microSD started FEL, and the screen stayed dark. The frame had **only USB
power from the Mac, throughout**. #177 had normal power connected as well.

All RAM builds were U-Boot v2025.10 with the base patch, the START STOP correction and
`SYS_DEVICE_NULLDEV`. Each attempt was made once:

| Attempt | Result |
| --- | --- |
| [4-bit 26 MHz](patches/pf1007l-v2025.10-emmc-4bit-26mhz.patch), eMMC-only `ums` | SPL finished and `sunxi-fel` reached "Starting U-Boot", but no USB disk appeared on repeated checks |
| Same build, `ums` on the SD card only | USB disk appeared, at the card's size, read-only |
| [No-HS](patches/pf1007l-v2025.10-no-mmc-hs.patch) (also 4-bit 26 MHz), eMMC-only `ums` | **USB disk appeared at the eMMC's size, read-only.** The full backup completed |

The SD result rules out U-Boot start-up and USB in general, and points at eMMC start-up. The only
build difference in the last row is the patch that clears the host's high-speed capabilities. USB
power doesn't explain the failure, because the no-HS build ran on the same power.

Guess, not verified: this eMMC needs legacy timing, as in
[the no-HS report](pf1007l-macos-20260529-no-mmc-hs-report.md). The eMMC's identity wasn't compared
with #177's.

A power cycle with the card inserted was needed between RAM loads.

## Backup and key edit

- The whole eMMC was read twice independently, in 1 GiB chunks, and the chunks were hashed and
  stored on a second Mac. It was also rebuilt as one image, and its hash was checked.
- A read-only `e2fsck` on userdata reported one problem: `Padding at end of inode bitmap is not
  set`. It exited with status 4. Recovery wasn't needed.
- The edit was made on a clone. It added the owner's public key at `/data/misc/adb/adb_keys`, uid
  1000, gid 2000, mode 0640, with the directory's SELinux attribute copied exactly, including its
  trailing NUL. `e2fsck -fn` on the clone was then clean.
- The difference was **8 ranges, 27 sectors, 13,824 bytes, all in userdata**, including the bitmap
  repair. #177 had 12 ranges and 16,384 bytes. These are per-unit, so don't reuse them.
- A guarded U-Boot script compared the current bytes, wrote each range and read it back. The eMMC
  was then read through read-only `ums`, and its full hash matched the clone's.
- Undo was tested on full-size image copies only. **It wasn't run on the frame.**

## Result

After a cold USB power cycle with the card removed, ADB was `device`. Boot and system weren't
touched, and `ro.adb.secure` stayed `1`.

```sh
adb shell su 0 sh -c 'id; grep CapBnd /proc/self/status'
```

This gives uid 0 with `CapBnd: ffffffe0000000c0`, so no `CAP_SYS_ADMIN`, the same as #177.

## Home HQ

- Home HQ 1.1 installed over ADB and rendered at 1280×800, both as the bundled demo and from a page
  on the LAN.
- It's the default Home, and came back to the foreground after a reboot.
- Navigation works with `WRITE_SECURE_SETTINGS` granted. The owner confirmed Menu → Android settings
  → floating Dashboard returns on the frame.
- The single-tap Menu button was turned on without testing the two-finger gesture, because the
  two-finger hold didn't open the menu in #177.
- The frame couldn't resolve a `.local` hostname for the dashboard server, so use an IP address.

## Hardware

Android reports no GPS feature or provider and zero cameras. It does report an accelerometer and a
temperature sensor. Whether that sensor measures the room is unknown.
