# MQQC AST01 10.1" Frameo frame (SciShion P200, RK3126, Android 6.0.1)

Record of one unit, 2026-11-02, macOS host (Apple silicon). Observations are kept separate from
guesses. Unique identifiers (serial, MAC, IP) are left out.

**Short version:** sold as MQQC AST01; Android reports a SciShion `P200` made by `ChipTrip`. It is
an `F606C` + `rk915` build like the [Denver PFF-1024BMK2](denver-pff-1024bmk2.md) and the
[Veidoo F10](veidoo-f10.md), with the same partition starts as the Denver PFF-1015, Rollei 107 and
[Runxion RK3126](runxion-zn-dp1002-rk3126.md). ADB from Frameo's settings, no prompt, shipped
root `su`. **Only a USB-A to USB-C data cable worked**: USB-C to USB-C, wireless ADB and the reset
button gave no connection.

**It ships the hidden root agent `iotv`**, a newer build than the one recorded on the Runxion
RK3126. See [iotv on this unit](#iotv-on-this-unit). Check for it before the frame goes online.

## Observations (read-only)

### Identity

| | |
| --- | --- |
| Listing / box | MQQC AST01, 10.1" Frameo (where bought: not recorded) |
| About screen | Frameo version shown as `v.32.12` (owner's reading; the package reports v1.30.13, below) |
| Brand / model | `ro.product.brand=SciShion-frameo`, model `P200`, manufacturer `ChipTrip`, device and name `rk312x` |
| Firmware | `F606C_RK915_SciShion_Frameo_P200-V1.0.1202604071435.release-keys`, built 2026-04-07 |
| Fingerprint | `rockchip/rk312x/rk312x:6.0.1/MXC89K/user.yuys.20260407.143456:user/release-keys` |
| SoC | Rockchip RK3126 (`ro.board.platform=rk312x`, `ro.hardware=rk30board`), 32-bit (`armeabi-v7a`) |
| Kernel | Linux 3.10.0, built 2026-04-07 |
| Android | 6.0.1, API 23, security patch 2016-07-05, `user` build, `ro.debuggable=0`, `ro.secure=1`, `ro.adb.secure=1` |
| Low-RAM mode | Off: `ro.config.low_ram` is not set |
| SELinux | Permissive |
| Display | 1280x800, 160 dpi |
| RAM / storage | 1 GB (`MemTotal: 1023552 kB`), 128 MB zram; 16 GB eMMC (`mmcblk0`, 30,777,344 sectors) |
| WebView | `com.android.webview` 107.0.5304.36 |
| CA store | ISRG Root X1 (`6187b673.0`) present; X2 (`8794b4e3.0`) absent |
| Wi-Fi | Driver module `rk915` (SDIO) |
| SystemUI | `com.android.systemui` is disabled: no status or navigation bar |
| Frameo | `net.frameo.frame` v1.30.13 in `/system/priv-app/Frameo.apk`, the Home app. Default time zone `America/New_York` (`ro.frameo.default.timezone`) |
| Vendor updaters | `com.adups.fota`, `com.adups.fota.sysoper`, `android.rockchip.update.service` |

### USB, ADB and root

- **The only way in that worked was a USB-A to USB-C data cable** (USB-A end in a hub on the Mac).
  These all failed:
  - **USB-C to USB-C cable:** no USB device enumerated on the Mac at all.
  - **Wireless ADB:** no connection (owner's test). A scan of TCP 5555 on the LAN also found
    nothing, but the frame was not on Wi-Fi at that moment.
  - **Reset button:** no connection (owner's test; exact sequence not recorded). Loader mode was not
    reached.
- **ADB:** Frameo → Settings → Beta program → ADB access, USB `2207:0006`, product `P200`. `adb devices` showed
  `device` (authorized). There is no `/data/misc/adb/adb_keys` or `/adb_keys`, although
  `ro.adb.secure=1`: as on the Denver frames, `adbd` appears not to check keys (one computer tested).
- **Root:** `/system/xbin/su` (SuperSU, `daemonsu` started by `init`). `su 0 id` and `su -c id`
  return `uid=0(root)` with no prompt.
- **Frameo holds root sessions:** two `su` processes owned by Frameo's uid while it runs.

### Partition table (eMMC `mmcblk0`, 512-byte sectors)

From `/sys/block/mmcblk0/mmcblk0pN/start` and `size` and `/dev/block/platform/1021c000.rksdmmc/by-name`.
Starts match the [Denver PFF-1024BMK2](denver-pff-1024bmk2.md) exactly; only the `userdata` size
differs.

| Node | Name | Start | Size |
| --- | --- | --- | --- |
| mmcblk0p1 | uboot | 16384 | 8192 |
| mmcblk0p2 | misc | 24576 | 8192 |
| mmcblk0p3 | resource | 32768 | 32768 |
| mmcblk0p4 | kernel | 65536 | 24576 |
| mmcblk0p5 | boot | 90112 | 24576 |
| mmcblk0p6 | recovery | 114688 | 65536 |
| mmcblk0p7 | backup | 180224 | 131072 |
| mmcblk0p8 | cache | 311296 | 262144 |
| mmcblk0p9 | metadata | 573440 | 32768 |
| mmcblk0p10 | kpanic | 606208 | 8192 |
| mmcblk0p11 | system | 614400 | 2097152 |
| mmcblk0p12 | radical_update | 2711552 | 131072 |
| mmcblk0p13 | userdata | 2842624 | 27934720 |

### Backup (verified)

A **partial backup**, like the Denver and Runxion ones: `userdata` was excluded, so it does not meet
the repo's complete-device backup rule. It covers every partition this record writes to. Restore is
untested.

eMMC sectors 0–2,842,623 (everything before `userdata`), 1,455,423,488 bytes, streamed over USB
in 3 min 48 s (about 6.4 MB/s raw) with:

```sh
adb exec-out "su -c 'dd if=/dev/block/mmcblk0 bs=1048576 count=1388 2>/dev/null'" \
  | tee >(shasum -a 256 > emmc.sha256.raw) | gzip -1 > emmc-0-2842624.img.gz
```

- Raw stream SHA-256 equals the gzip readback SHA-256; byte count as expected.
- No aligned 4 KiB block is all `0xCC`.
- Independent re-reads on the frame (`md5sum` of the area before `uboot` and of each partition
  `uboot` through `radical_update`) match the backup for all 13 regions.
- `boot` (p5) SHA-256: `b5ba7e06ed1802d2f38ba934e134f313728aa503757b316a49887395bc741a1c`.

### iotv on this unit

Same mechanism as on the [Runxion RK3126](runxion-zn-dp1002-rk3126.md#hidden-root-agent-iotv):
`init.rk30board.rc` (boot image) defines `service run_iotv /system/bin/sh /system/bin/run_iotv.sh`
(`class main`, `oneshot`, `disabled`) and starts it at boot; the script runs
`/system/bin/iotv -MAC <wlan0 address>`. `iotv` was running as root before any change.

| File | This unit | Runxion RK3126 record |
| --- | --- | --- |
| `/system/bin/iotv` | 982,324 bytes, dated 2026-04-07, MD5 `ff2b91aca984f657d9317a5ada710e34`, SHA-256 `633b41a58b9272fba8b28af7d26dccad85722df8ede28e08e4044dd6d5e86f1a` | 982,392 bytes, dated 2025-09-26, different hashes |
| `/system/bin/run_iotv.sh` | 113 bytes, SHA-256 `f2adb1e0939c351cf4c284e644b55fa21c23ca893e8ef512451d2a65718cc3a8` | Identical |

- `/system/etc/resolv.conf` lists only public resolvers (Google, Cloudflare, OpenDNS), set to
  `0444` by the same `init` block that sets up `iotv`.
- Not observed: what it connects to. The frame was not on Wi-Fi, and `iotv` had no open sockets.
  It is a newer build, so the server and behaviour may differ from the Runxion record.

## Changes made to the frame (2026-11-02)

> **Record, not a procedure.** Done by hand on one unit, one step at a time, each approved by the
> owner. The commands are not a script in this repo.

All made after the verified backup, with copies of the removed files on the host (MD5 checked
against the frame).

| Change | How | Undo |
| --- | --- | --- |
| Stop and remove `iotv` | `kill <pid from ps>` (not `pidof`; see the Runxion pitfall); `mount -o rw,remount /system`; `rm /system/bin/iotv` | Copy the saved file back (`chmod 755`, owner `root:shell`), or write `system` back from the backup |
| Neutralize the start script | `run_iotv.sh` replaced (not deleted) with `#!/system/bin/sh` + `exit 0`, mode 755; then `mount -o ro,remount /system` | Copy the saved `run_iotv.sh` back |
| Updaters off | Disabled `com.adups.fota`, `com.adups.fota.sysoper` and `android.rockchip.update.service` individually with root `pm disable` (one package per command). `enabled="2"` reached `package-restrictions.xml` a few seconds later; checked before rebooting | `pm enable` each |

Verified after a reboot: no `iotv` process; `init.svc.run_iotv=stopped` (the no-op ran); the
updaters are still disabled; `su` works; Frameo starts as before.

## Status against the README phase map

| Phase | State |
| --- | --- |
| 1 Identify | Done. `F606C`/`rk915` build, Denver PFF-1024BMK2 partition layout, 1 GB RAM. |
| 2 ADB | Done: Frameo ADB access, USB-A to USB-C cable only. USB-C to USB-C and wireless ADB failed. |
| 3 Loader mode | Not needed. The reset button gave no connection (owner's test). |
| 4 Back up | Done and verified (partial: `userdata` excluded). Restore untested. |
| 5 Root | Shipped `su` works. |
| 6 Make it useful | Not started. `iotv` and the updaters removed or disabled; Frameo still the Home app. |
