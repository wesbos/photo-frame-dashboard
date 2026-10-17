# Pastigio 15-inch Frameo frame (`FRAME157`, RK3326, Android 8.1)

Report from one unit tested on 2026-10-12 using an Apple silicon Mac running
macOS. Original ADB findings: [issue #39](https://github.com/wesbos/photo-frame-dashboard/issues/39).
The related [FRAME156 report](pastigio-frame156.md) covers a different model.

**Verified result:** holding the power button while connecting power and USB
opened Rockchip Loader. After a verified backup, adding the host's public ADB
key gave authorized USB ADB and access to the shipped `su`. CPU `interactive`
scaling at 408–1,008 MHz matched fixed-maximum press performance while spending
most measured idle time at 408 MHz.

## Identity

| Item | Observed value |
| --- | --- |
| Brand / size | Pastigio / 15-inch |
| About model / Android model | `DPF Frame 157` / `FRAME157` |
| Firmware | `FrameO.DP105F.v2026051219` |
| SoC / userspace | Rockchip RK3326 / `armeabi-v7a` |
| Android / security patch | 8.1.0, API 27 / 2020-11-05 |
| Display | 1920×1080, 170 dpi |
| WebView | `com.android.webview` 106.0.5249.126 |
| Storage | 61,071,360 × 512-byte sectors, 31,268,536,320 bytes |
| USB IDs | ADB `2222:0006`; Rockchip Loader/BootROM `2207:330d` |

Frameo initially showed v1.30.19 (69880). After joining the beta program it
updated to v1.32.12_-_OTA_test (78071). The firmware string above was recorded
after that app update.

## USB and Loader access

A USB-A to USB-C data cable through a hub enumerated on the Mac. Direct C-to-C
failed to enumerate with the tested connection. A keyboard worked in the
frame's USB-A host port.

Frameo **Settings → About → Beta Program → ADB Access** was enabled and computer
photo transfer was off. ADB stayed `unauthorized` through replugging and reboot,
without an authorization popup. The saved userdata showed SystemUI installed
but disabled; that is a possible explanation for the missing popup.

The sole power button was the useful boot control. The frame normally starts
as soon as wall power is connected; holding power after shutdown did not start
this unit.

1. Disconnect both wall power and USB.
2. Hold the power button before reconnecting wall power and USB.
3. Confirm USB `2207:330d` and a responding Loader with `rkdeveloptool ld`.
   The display stayed black while Loader was available.

Chip and flash queries confirmed RK3326 and the storage size above. USB/query
results distinguish Loader entry from a blank screen during ordinary startup.

## Verified backup and ADB authorization

> **This is a record of one unit, not a step-by-step procedure.** The patch and write tooling used
> for the userdata `adb_keys` write is not in this repo, and `xrock` was not pinned to a release.
> Before any flash write, try the simpler routes other Frameo owners used: accept Frameo's own ADB
> warning on screen ([FRAME156](pastigio-frame156.md)), and toggle ADB Access off and on with USB
> connected (see the Runxion row in the [device index](devices.md)).

### Reader needed for the full backup

Stock Loader reads returned `0xCC` filler at and beyond sector `0x10000`
(32 MiB), despite reporting success. The official RK3326 USB helper had the
same limit. We used the pairing in `RKBOOT/RK3326MINIALL.ini` from Rockchip rkbin
commit [`89047911f4a630293bb11d4375c0245e138c95d6`](https://github.com/rockchip-linux/rkbin/tree/89047911f4a630293bb11d4375c0245e138c95d6):

| Binary | SHA-256 |
| --- | --- |
| `rk3326_ddr_333MHz_v2.06.bin` | `42df91c81530560ee42940f7fcee2e50847357d8ffc61376dd1d49d1bc5b04ca` |
| `rk3326_miniloader_v1.35.bin` | `a759a5add0db60e5a4dc99cea04cd84be704d07a1e708bda9006ec2e7e06abbc` |
| `rk3326_usbplug_v1.36.bin` | `886b3ff055df92411ceddb9f851cbee753a93203bab55f5711f7c69fd1874f71` |

DDR and miniloader contents matched the stock capture. In this exact USB
helper, changing four bytes at file offset `0x908c` from `ee031032`
(`mov w14, #0x10000`) to `0e008012` (`mov w14, #-1`) raised the shared read limit.
The patched helper's SHA-256 was
`3f27fc0e248d8f1a96c1b5356449b333feafb16caa2b854e5354083cf8649090`.
These bytes and offsets are specific to the pinned helper.

`rkdeveloptool rd 3` entered fresh BootROM, then
`xrock maskrom <DDR binary> <patched USB helper>` uploaded the reader into RAM.
USB transport used RC4 enabled, as described in [xrock's PX30 notes](https://github.com/xboot/xrock#px30).
The reader identified itself as `USB-MSC`; `rkdeveloptool ld` still labeled it
Maskrom. Flash queries and repeated reads established readiness.

The complete addressable-flash capture passed exact byte count, SHA-256/gzip
readback, GPT CRC checks and ten independent device rereads. Boot, recovery,
uboot, system samples and userdata samples were among the matching reads.
Stock boot partition SHA-256:
`434afd333333e3fbb027baa43ebdf1954bf23f840272748f9246d040cb4ceb68`.

### Adding the host's public key

The saved userdata had no `/data/misc/adb/adb_keys`. On a local copy of its ext4
filesystem, we added the host's public ADB key at `/misc/adb/adb_keys`, which
becomes `/data/misc/adb/adb_keys` on Android. Existing trusted keys should be
preserved. File metadata was uid 1000, gid 2000, mode 0640, with SELinux context
`u:object_r:adb_keys_file:s0`.

Filesystem checks and key-file readback passed. Comparing original and edited
userdata produced 14 changed ranges totaling 61,440 bytes. Each range's live
bytes matched the backup before writing; original bytes were retained for undo,
and each write passed device readback. Derive these ranges from the individual
unit's GPT and filesystem: another frame needs its own offsets and original bytes.

After `rkdeveloptool rd 0`, Frameo started normally and these checks passed:

```text
adb get-state        → device
adb shell su -c id   → uid=0(root)
```

Ordinary `adb shell` runs as uid 2000. `/system/xbin/su` supplies root when
requested. Authorized USB ADB also returned after later reboots and a full
power removal.

## CPU scaling

The starting policy for the CPU tests was `userspace` at 600 MHz, with
408–1,008 MHz limits. A matched speed test gave these native-press browser
paint medians, with 36 presses per setting:

| Fixed CPU speed | Median |
| --- | --- |
| 600 MHz | 160 ms |
| 816 MHz | 136 ms |
| 1,008 MHz | 120 ms |

A separate governor comparison kept those limits and the same warm six-row
Solid 2 page on the stock 50 Hz display. Three shuffled rounds measured 36
repeated presses, 12 presses after five seconds quiet, and 90 seconds of idle
residency per condition:

| Policy | Repeated median | After-quiet median | Idle residency at 408 MHz |
| --- | --- | --- | --- |
| Fixed 1,008 MHz (`userspace`) | 112 ms | 144 ms | 0% |
| `interactive` | 112 ms | 144 ms | 97.1% |
| `ondemand` | 112 ms | 144 ms | 92.9% |

We selected **`interactive`, minimum 408000 / maximum 1008000 kHz**, using
frequencies already available on this unit. Peak sampled SoC temperature in the
governor comparison was 58.6°C. Press results are browser Event Timing from
native Android input; idle percentages are `time_in_state` counters. Longer
thermal/power behavior still needs a soak test.

### Apply and undo

First check the unit's identity, supported governors/frequencies, and save its
current governor, limits and `scaling_setspeed` for undo. The CPU files on this
unit are under `/sys/devices/system/cpu/cpu0/cpufreq/`.

The selected live policy was applied with:

```sh
adb shell "su -c 'echo 408000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'"
adb shell "su -c 'echo 1008000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq'"
adb shell "su -c 'echo interactive > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'"
```

Read those three files back to confirm the selection. To restore this unit's
recorded starting policy, retain the same limits and switch back to fixed
600 MHz:

```sh
adb shell "su -c 'echo userspace > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'"
adb shell "su -c 'echo 600000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed'"
```

### Wake and startup

Android's sleep/wake path raised `scaling_max_freq` to 1512000 on this unit.
Our local startup service reapplies the selected CPU policy after boot and
display initialization. An `inotify` watch restores the 1008000 ceiling when a
write raises it, while leaving lower restrictions alone. A temporary 816000
ceiling stayed in place during verification.

The final policy passed normal reboot, subsequent sleep/wake and full
power-removal checks: `interactive`, minimum 408000, maximum 1008000.
A persistent setup also needs its CPU startup writes/watch removed when
restoring the original policy.

## Recovery notes

The ADB repair retained the original bytes for each userdata range as its undo
record. Live rollback of those key-file edits was not exercised. Backups,
original ranges and device identifiers remain in private recovery storage.

## Additional unit: FRAME157 with `2211:0006` USB ID (Windows, 2026-10-17)

A second owner's FRAME157 differed from the unit above in USB IDs and firmware,
but matched its platform, layout and route. Tested from Windows 10 with
platform-tools 37.0.1 over a USB-A to USB-C data cable. Observations only;
identifiers (serial, MAC, IP) are omitted.

| Item | Observed value |
| --- | --- |
| About model / Android model | `DPF Frame 157` / `FRAME157` |
| Firmware | `FrameO.DP105F.v2025122915` (newer than the `v2026051219` above) |
| Fingerprint | `rockchip/rk3326_32bit/rk3326_32bit:8.1.0/OC/150203:user/release-keys` |
| SoC / Android / patch | Rockchip RK3326 / 8.1.0 / 2020-11-05 |
| Display | 1920x1080, 170 dpi |
| WebView | `com.android.webview` 106.0.5249.126 |
| Storage | `mmcblk2`, 61,063,168 x 512-byte sectors; userdata starts at sector 5612544 (same layout as the FRAME156 table) |
| USB IDs | ADB `2211:0006` named `FRAME157` (the unit above reports `2222:0006`; `2211:0006` matches the FRAME156 report) |
| SELinux / boot | Permissive, `ro.boot.veritymode=enforcing`, `ro.boot.flash.locked=1` |
| Frameo | v1.29.13 system app and HOME activity; `com.android.launcher3` already disabled |
| Root | Shipped `su` returns uid 0 with no prompt; shell is uid 2000 |

ADB authorized without a loader: Frameo **Settings -> About -> Beta Program ->
ADB Access** ON, computer photo transfer OFF, then Accept on Frameo's own ADB
warning and one OFF -> ON toggle with USB connected. The first `adb devices`
showed `unauthorized`; after the toggle it showed `device` and the key
persisted across reboots.

Backup over ADB as root (no flash writes): eMMC sectors 0-5612544
(2,873,622,528 bytes raw, ~585 MB gzipped). Exact byte count, gzip readback,
no `0xCC` 1 MiB blocks, and 11 independent partition re-reads
(uboot, trust, misc, resource, kernel, boot, recovery, security, system,
vendor, frp) all MATCH. Two Windows-specific traps: PowerShell `>` redirection
writes UTF-16LE (BOM `FF FE`), which corrupts a base64 capture; and an
unquoted `su -c dd ... | base64` reads the wrong bytes. Capturing `adb
exec-out` bytes directly from Python, stripping `\r`, and quoting as `su -c
'dd ... | base64'` gave byte-exact results (1 MiB and 4 MiB probes matched
device SHA-256 before the full run).

Kiosk from this repo (`com.wesbos.homehq`) installed, set as Home with `cmd
package set-home-activity`, verified by HOME key focus and a reboot that
returned to the kiosk with ADB. `com.muxintu.app.mxota`,
`android.rockchip.update.service` and `net.frameo.frame` disabled with `pm
disable-user` (each reversible with `pm enable`); Frameo needed one
`force-stop` after the reboot and did not restart within 20 s. The kiosk's
two-finger hold to Android Settings was confirmed by hand on the panel before
Frameo was disabled.

Stability note (unexplained): the frame left the USB bus four times in one
day, each time with a black screen; each recovered via wall power + power
button and showed a fresh `uptime`, i.e. reboots, not sleep. Cables were
untouched for the later events. No crash log was found in pstore/last_kmsg.
This does not block the route above, but a unit that reboots on its own
should be watched before being relied on.
