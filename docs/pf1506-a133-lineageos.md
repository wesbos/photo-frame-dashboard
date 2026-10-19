# PF1506 (AiMOR, Allwinner A133): Settings escape to root ADB, then LineageOS 20

A record of **one unit**, the 15.6" frame with AiMOR firmware sold on Amazon US. Frames sold under the same name can use
different boards and firmware, so check the identity values below before running anything here. This is the same
SoC as the [LOOFII C-3](allwinner-a133-loofii-c3.md), but a different board, touch controller and boot path. Don't
run the A33 PF1007L routes, or the LOOFII's `scripts/a133/` flashing tools, on it.

**Tested on:** one unit. The Settings escape was done on the frame's touchscreen. The backup was taken from Windows
(PowerShell, over USB). Unlocking, flashing and everything after were done over USB from a Linux host (Ubuntu, with
`adb`, `fastboot` and e2fsprogs from the distribution), and later work used Wi-Fi ADB from the same host. The end state is a full-screen calendar kiosk that has run for several days. "Not tested"
and "probably" mark guesses.

## Hardware and identity

| | Value seen on this unit |
|---|---|
| Stock firmware | AiMOR 6.0.70, `YHK.F-null-A133-1506-D2048-PF1506-V45-OS-KXW.0.20250813` |
| Vendor fingerprint | `Allwinner/ceres_c3/ceres-c3:10/QP1A.191105.004/12:user/test-keys` (Android 10, patch 2021-01-05) |
| SoC | Allwinner **A133** (`sun50iw10p1`, board `ceres`, fastboot product `ceres-c3`), 4× Cortex-A53 at 1.512 GHz |
| Kernel / userspace | 4.9.170 arm64, **32-bit userspace only**, so the GSI type is `a64` (arm32_binder64) |
| GPU | PowerVR Rogue GE8300, GLES 3.2 |
| RAM / storage | 2 GB / 32 GB eMMC. The data partition is `UDISK` (f2fs, file-based encryption), not `userdata` |
| Display | 1920×1080 at 59 Hz, density 160 |
| Touch | `gslX680`. It reports a 1280×800 grid rotated 270°, which the GSI needs an IDC file for (below) |
| Wi-Fi / BT | AIC8800DC |
| Other | No battery (mains powered), no camera, accelerometer only |
| Buttons, ports | Power button on the back, **no volume keys**, USB-C (device mode, ADB), full-size USB-A host port |
| Partitions | Dynamic partitions, not A/B. `super` is 2,048 MiB with group `sb` capped at 2,040 MiB. Stock `vendor` is 118 MiB |
| Stock security | `ro.adb.secure=0`, SELinux permissive (`androidboot.selinux=permissive` from the bootloader), shipped `su 0` |

## 1. Turning on USB debugging from the stock UI (no SD card, no password)

Stock AiMOR hides Android Settings, and tapping Build number in AiMOR's own About screen opens the factory test
app's password prompt (see #104). This route reaches the real Android Settings app instead. It goes through a crash,
so expect to repeat a step if a dialog doesn't appear the first time.

1. In AiMOR, open the Wi-Fi setup screen and tap into the **Wi-Fi password** field. Type a few characters.
2. Long-press the text to **select** it. In the text-selection menu, choose **Share**.
3. Sharing needs Bluetooth, so Android turns it on. The Bluetooth app then crashes, and a crash dialog appears
   (**"Bluetooth keeps stopping"**). It may come back repeatedly.
4. The dialog has a close button and **App info**. Tap App info: it opens Android's own Settings app, at the
   Bluetooth app's info page.
5. In Settings, use the search (magnifier) and search for **build number**. Open the result and tap **Build number**
   seven times. This one unlocks Android's **Developer options**, not the test app.
6. In Developer options, turn on **USB debugging** and **Rooted debugging**.
7. Connect USB-C to the computer: `adb devices` shows the frame straight away. There's no authorization prompt
   because `ro.adb.secure=0`. Check root with `adb shell su 0 id`, which should print `uid=0(root)`. The stock
   build ships `su`, and the backup below uses `su 0`.

Keep crash dialogs on. Setting `hide_error_dialogs` to `1` removes the App info way out, and with it this route.

Undo: turn USB debugging off in Developer options. The other password-free route, an empty `license.properties` on
an SD card or USB stick plus five taps in the top-left corner, is in #104.

## 2. Backup (do this before anything else)

> **Firmware partitions only.** This backup does **not** include `UDISK`, the data partition (photos, apps and
> settings), or `frp`. Section 3 or 4 erases `UDISK`, so copy off any photos you want to keep first.

[`scripts/pf1506/backup.sh`](../scripts/pf1506/backup.sh) reads every firmware partition over USB ADB with stock
`su 0`, and **stops at the first mismatch**. This unit's backup was taken from Windows PowerShell with the same
method; the script is a bash version of it and hasn't been run against a frame. The method:

- Stream each partition with root `dd`.
- Cut each file to the partition's real size: `dd` appended a short status message (about 82 bytes) to the stream.
- Compare each file with a hash taken on the frame. Hash *outside* `su`, by piping into `sha256sum`: this
  firmware's `su` dropped output when it ran script files.
- Read `super` (2 GiB) as 64 pieces of 32 MiB and check each one. On this unit, the frame restarted partway
  through every full read of `super`, even when copying to its own storage.

`frp` couldn't be read even as root (permission denied). Keep a second copy of the folder on another machine.
`super.img` holds the stock `system`, `vendor` and `product`, which section 7 restores from.

**Host:** a Linux host is easier. On Windows the frame needed extra USB drivers (installed with Zadig), and the
connection was unreliable. On Ubuntu, `adb` and `fastboot` work with only a udev rule for USB vendor IDs `1f3a`
(Allwinner) and `18d1` (Google).

The retained `MANIFEST.sha256.txt` lists image files that remain in the folder and is checked at completion.
`TRANSFER-CHUNKS.sha256.txt` records the verified `super.N` transfers; those temporary pieces are deleted after
numerical concatenation. It is transfer evidence, not a manifest to check against the retained folder.

## 3. Unlock and turn off verification

**Historical manual commands, not a guarded flashing tool.** The commands below and in sections 4, 7 and 8 do
not enforce target identity/size, compare-before-write or device readback. The backup is firmware-only and does not
meet every README backup check. Do not treat this one-unit record as satisfying the repository's write safeguards.

1. `adb reboot bootloader`, then `fastboot oem unlock`. It returned `OKAY` at once, with no confirmation on the
   screen. In this bootloader mode, every other command, including `getvar`, is refused with
   `secure mode,fastboot limited used`. `fastboot flashing unlock` and `flashing get_unlock_ability` fail with
   `unknown cmd`.
2. `fastboot reboot fastboot` to reach **fastbootd** (userspace fastboot). There, `fastboot getvar unlocked` returns
   `yes`.
3. Still in fastbootd: `fastboot --disable-verity --disable-verification flash vbmeta vbmeta.img`, using the
   **stock** 16 MiB `vbmeta.img` from your backup. Fastboot prints `Rewriting vbmeta struct at offset: 0`. Only
   `vbmeta` was flashed; `vbmeta_system` and `vbmeta_vendor` were left stock.

Whether the unlock itself wipes data isn't known. On this unit, the old apps were gone at the first LineageOS boot,
but `UDISK` was also erased around then (section 4). Assume the unlock wipes data.

Later, from Android, reach fastbootd with `adb reboot fastboot`. The host may print "Failed to boot into userspace
fastboot". That's a timeout: wait about a minute, then run `fastboot devices`.

> **Never run `fastboot reboot recovery`.** On this unit it left the frame on a recovery menu with USB dead. The
> menu can't be driven without volume keys, and only a press of the power button got it out.

## 4. LineageOS 20 GSI (Android 13) with the touch fix

**Image:** Andy Yan's LineageOS 20 TD build, `lineage-20.0-20251021-UNOFFICIAL-a64_bvN.img.gz`, from
<https://sourceforge.net/projects/andyyan-gsi/files/lineage-20-td/>. The file is 769,291,722 bytes, with sha256
`62551575a4134813274ed2b255bc695523e8b5dd991b53269c7019227cb65e4e`. Decompressed it's 1,649,119,232 bytes, with sha256
`d4ed044bcbfbb8352fb1dd8d2ec583f3bccf7181a06b99479723f8517325c733`.

**Stay on Android 13.** Android 14 and later GSIs need eBPF features this 4.9 kernel lacks, and risk losing networking.
Android 13 networking works.

**The system image must stay under about 1,900 MiB.** That's the 2,040 MiB group cap minus `vendor` (118 MiB) and
`product`. Stock `product` is about 178 MiB. The GSI doesn't use it (`/product` points to `/system/product`), so it
was replaced with a 4 MiB empty ext4 image to make room:
`truncate -s 4M empty-product.img && mkfs.ext4 -q -F -O ^has_journal -L product empty-product.img`. Flashed in
fastbootd before `system`, it makes fastboot shrink the `product` logical partition from 178 MiB to 4 MiB
(`Resizing 'product' OKAY`). Files put in `product` have no effect on this GSI, so the touch fix has to go inside the
system image. Whether the frame boots with `product` deleted entirely wasn't tested.

**Build the image offline:** run [`scripts/pf1506/build-system-image.sh`](../scripts/pf1506/build-system-image.sh).
It checks both hashes above, unpacks the image, and adds the files below with `debugfs`, labelled
`u:object_r:system_file:s0`. It then runs `e2fsck`, checks the size limit and checks every added file's label. It
creates only the output image and a temporary work folder. The contributor reported file-for-file agreement for an
earlier build excluding Wi-Fi ADB. That does not establish reproduction of the revised scripts or image contents.

- **Touch fix:** `/system/usr/idc/gslX680.idc` ([file](../scripts/pf1506/gslX680.idc)):
  `touch.deviceType = touchScreen`, `touch.orientationAware = 1`, `touch.orientation = ORIENTATION_270`. Without it,
  touches land rotated. Check with Developer options → Pointer location in all four corners.
- **Boot-time fix** (`entropy_seed`, next section).
- **f2fs wear fix** (`frame-tuning.sh`, next section).
- **Optional Wi-Fi ADB** (`frame-adb-wifi.sh`, next section): only with `--wifi-adb`. Off by default.

`entropy_seed` is a static armv7 binary built from [`entropy_seed.c`](../scripts/pf1506/entropy_seed.c) with the
Android NDK (r27): `armv7a-linux-androideabi29-clang -O2 -static -o entropy_seed entropy_seed.c`.

**Flash** (keeps data):

```bash
adb reboot fastboot          # wait ~1 min
fastboot devices
fastboot flash product empty-product.img   # first time only: frees room in super
fastboot flash system pf1506-system.img
fastboot reboot
```

The first boot after a system flash is slow, because it recompiles apps. If you came from stock, wipe data once, using
the partition names this board uses (`fastboot -w` targets `userdata`, which doesn't exist here):
`fastboot erase UDISK`, then `fastboot erase cache`. Android reformats the data partition on the next boot.

Resulting build: `google/lineage_a64_bvN/tdgsi_a64_ab:13/TQ3A.230901.001/...:userdebug/test-keys`. `adb root`
works, and SELinux stays permissive (set by the bootloader).

## 5. Fixes for this board (all in `scripts/pf1506/`)

- **Boot stalls about 67 s on the RNG.** The 4.9 kernel has no hardware RNG (`CONFIG_HW_RANDOM` unset), so the
  kernel's CRNG initialised only about 75 s after power-on. `boringssl_self_test32` (init.rc `on init`) blocks boot
  until then. `entropy_seed` borrows the idea of systemd-random-seed, in a much simpler form that isn't
  equivalent to it:
  - Once boot completes, it saves 512 random bytes to `/metadata/entropy_seed`. `/metadata` is mounted in first
    stage, before `early-init`.
  - At the next `early-init` it deletes the file and syncs the deletion to storage, and only then credits the
    bytes with `RNDADDENTROPY`. If the delete or sync fails, it doesn't credit them. So a crash can't make this
    device credit the same file twice. That doesn't cover copies: restoring `/metadata` from a backup, or cloning
    it to another frame, would credit a seed that was already used. Don't copy or restore
    `/metadata/entropy_seed`.

  Result: `random: crng init done` at 8 s instead of 75 s, and `sys.boot_completed` at about 46 s instead of about
  135 s. A boot that never completes leaves no seed, so the next boot just takes the old time once. Check with
  `adb root; adb shell dmesg | grep entropy_seed`. The same rc sets `debug.sf.nobootanimation 1`, so the
  bootloader logo stays up until the home app draws.
- **eMMC wear from f2fs background GC.** This unit's eMMC already reported 10–20% wear. With `/data` about 4% full,
  f2fs background garbage collection rewrote about 1.4 GB a day (measured on this unit), with little to gain at that fill
  level. `frame-tuning.sh` remounts `/data` with `background_gc=off` at boot. Foreground GC still
  runs if free space ever gets low.
- **Wi-Fi ADB is open root.** The GSI also has `ro.adb.secure=0`, so anything that reaches TCP 5555 gets root without
  a prompt. Don't turn on Wireless debugging. If you need ADB over Wi-Fi, build with `--wifi-adb` and set
  `persist.frame.adb_allow` to your computer's address: `adb root; adb shell setprop persist.frame.adb_allow <your-ip>`,
  then request init reconfiguration with `adb shell setprop ctl.start frame-adb-wifi` (the ADB session disconnects).
  `frame-adb-wifi.rc` runs a single init-owned service; do not run the shell script from an ADB shell.
  - The rc sets the runtime TCP property to `-1` at `early-init` and starts reconfiguration after persistent properties
    load. This requires the rc to be imported before `early-init` and no other init rule to enable TCP independently.
    **That boot baseline and the absence of an early listening window have not been verified on the frame.** Keep the
    optional build off until those assumptions and closure checks are verified locally on the intended firmware.
  - The service puts dedicated DROP-chain jumps first in IPv4 and IPv6 INPUT, stops `adbd`, clears both runtime and
    persistent TCP properties and checks daemon state plus known-port listening sockets before rebuilding.
  - The new IPv4 allow hook precedes broad ACCEPT and ESTABLISHED rules; IPv6 stays blocked. Only dedicated chains
    and their hooks change. Successful reapplication is idempotent; normal USB access is restored when disabled or
    no allow list exists. Each reconfiguration briefly disconnects both ADB transports.
  - Setting `persist.frame.adb_wifi 0` requests reconfiguration through init. If settings change during an active run,
    it fails closed; request `ctl.start frame-adb-wifi` again after it exits. A stale lock needs local investigation.
  - A failure returns nonzero, keeps/reinstalls guards where possible and attempts to stop `adbd`. **USB may also be
    unavailable; failed commands cannot guarantee network closure.** Inspect locally rather than assuming USB-only.

  This is an address allow list, not authentication: anything that can use an allowed address gets root.
- **2 s beep on every touch.** Interface sounds play as a long beep through this audio driver. Turn them off:
  `settings put system sound_effects_enabled 0`, `lockscreen_sounds_enabled 0`, `dtmf_tone 0`, and
  `settings put global charging_sounds_enabled 0`.
- **WebView.** Same as the LOOFII: LineageOS's 32-bit prebuilt
  ([commit `170e8996`](https://github.com/LineageOS/android_external_chromium-webview_prebuilt_arm/tree/170e8996e41ef542769b5479297ab91072b487e2),
  `webview.apk` sha256 `e744cd81ea83cfa6bda3da471ce58a5d9eac5d32260ad0ef98b8c9f49348f20e`, 155.0.8059.39). Re-sign it
  with AOSP's public testkey (`build/target/product/security/testkey.pk8` / `.x509.pem`) using `apksigner`, then
  `adb install -r`. The GSI is testkey-signed, so it installs as a normal system-app update. Undo:
  `adb shell pm uninstall-system-updates com.android.webview`.

## 6. Kiosk notes

- **No navigation bar:** `adb shell setprop persist.sys.phh.mainkeys 1`, then reboot. This is a phh/TrebleDroid
  property that the GSI honours.
- **The touchscreen sleeps with the display.** Once the screen is truly off, touch can't wake it (no proximity sensor
  or camera), only the power button can. For "tap to wake", dim to black over the page and keep the display on.
- **Calendar kiosk app:** [`scripts/pf1506/kiosk/`](../scripts/pf1506/kiosk/README.md) is the app this unit runs,
  as source.
  - It shows a week view and a detailed Today panel, weather, and optional per-person chore lists.
  - **It needs no server:** it reads your calendars' secret iCal addresses itself. You add those from a phone,
    through a PIN-protected setup page the frame serves on your Wi-Fi for a while after power-on.
  - **URL mode** shows a page you host instead, which lets the frame stay off the internet. This unit runs in URL
    mode against a calendar server on the LAN.
  - It's made device owner over adb (the frame has no accounts), pins itself in lock-task mode with no system UI,
    dims to black instead of turning the screen off, and turns the screen fully off overnight with an exact alarm.
  - Build and install steps are in its README. The repo's `dashboard/kiosk/` app is the general-purpose alternative.
- Turn off what a wall calendar doesn't need: Bluetooth, Wi-Fi and BLE background scanning, location,
  `captive_portal_mode 0`, the screensaver, animations (`window_animation_scale` etc. `0`), and the lock screen
  (`locksettings set-disabled true`).
- **Boot logo.** The power-on logo is `bootlogo.bmp`, a 24-bit 1920×1080 BMP on the FAT16 `bootloader` partition.
  [`make_logo.py`](../scripts/pf1506/make_logo.py) draws a plain title card in that format, for example
  `python3 make_logo.py DejaVuSans.ttf logo.bmp "Family Calendar"`.
  [`patch_logo.py`](../scripts/pf1506/patch_logo.py) then writes it into a new copy of your backed-up
  `bootloader.img`:
  - It accepts only the stock format: 54-byte header, 1920×1080 bottom-up, 24-bit, uncompressed, all pixel bytes
    present.
  - It rewrites only the pixel bytes, in the logo file's existing clusters.
  - It reads the logo back, and checks that no byte outside it changed, before writing the copy.

  The logo is cosmetic, with no effect on boot time. Flashing the bootloader partition is the riskiest write in this
  guide, so flash only a copy that `patch_logo.py` accepted. Undo: flash the original `bootloader.img`.

## 7. Undo and rollback

- **Each GSI layer:** flash an earlier `system` image the same way. Between the layers in this guide (same GSI build,
  files added), data was kept. A different or older GSI build may not read data written by a newer one; wipe `UDISK`
  if it doesn't boot.
- **Back to stock Android 10** (**not run on this unit**). Cut stock `system` and `product` out of the backed-up
  `super.img`, using the extents in its LP metadata (`lpdump super.img`; on this unit, `system` was 1,386,640 sectors
  at sector 2,048 and `product` 364,560 sectors at sector 1,634,304). Then flash `system`, then `product`, then the
  stock `vbmeta.img` without the disable flags. Finish with `fastboot erase UDISK` and `fastboot erase cache`. Stock
  has WebView 74. A matching-unit report describes a persistent boot animation after changing the Home app; the cause
  wasn't established (#118). Don't
  relock the bootloader with a modified image installed.

## What did not work / open

- **Recovery:** the recovery menu needs a keyboard to navigate (no volume keys). A USB keyboard in the USB-A port is
  probably the answer, but that's not tested.
- **FEL:** no FEL or reset-pinhole route was found or tried on this board. There's no published rescue for a PF1506
  with no USB access (#118).
- **Power cut:** the frame powers on by itself when power returns.
