# PF1007L: root ADB over Wi-Fi from an SD card

This procedure gives root ADB over Wi-Fi on a PF1007L photo frame (Allwinner A33).
It does not use USB. It uses the TF (microSD) slot only.

The procedure has four parts:

1. Make an SD card that boots U-Boot on the frame.
2. Dump the first 2 GiB of the eMMC to the card. Verify the dump on the PC.
3. Build a patched boot image from the dump. The patch adds ADB over Wi-Fi with key authentication.
4. Write the patched boot image to the eMMC from the SD card.

## 1. Applicability

This procedure was done on one unit. Use it only on a unit with these values:

| Item | Value |
| --- | --- |
| About screen, model | PF1007L |
| About screen, firmware | `YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113` |
| Ports | One USB-C port, one TF slot, one power/reset button. No DC jack. |
| SoC | Allwinner A33 |

The scripts stop if the boot partition is not the tested one.
`build-write.sh` refuses any original boot image that is not in its `TESTED` list (for this unit,
`d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4`).

### Other boards with the boot partition at sector 172032

The same scripts have been used on a [SOMY M10R7](somy-m10r7.md) and an
[ALONG/Uhale B-102K-Z](uhale-b102kz.md). On both, p6 also starts at sector 172032 but holds a
different boot image. Both images are in the `TESTED` list. The B-102K-Z image also gets two extra
ramdisk edits ([section 2](#2-what-the-patch-changes)). Everything else in this guide is unchanged.

1. **4-bit eMMC.** If the dump reports `emmc_dev: ok` but `st_00=FAIL first read`, rebuild with
   the eMMC at 4-bit, 26 MHz: `A33_EMMC_4BIT=1 bash scripts/a33-sdboot/build-macos.sh` (or the same
   variable with `build.sh`). On macOS, run `card-macos.py clean` **before** rebuilding, because it
   only recognises the build that is on the card; then delete `a33.scr` and `a33-status.txt` from
   the card and run `prepare` again.
2. **Your boot image's length and hash.** After a verified dump, print them:

   ```sh
   python -I scripts/a33-sdboot/patch-boot.py --inspect
   ```

   It also says whether the image is a tested one. If it is, pass the two values it prints to
   `patch-boot.py` (`--boot-len N --expect-sha256 H`), then run `build-macos.sh apply` (and
   `restore`) as usual. `patch-boot.py` stops if the kernel or the header outside the ramdisk size
   and boot id would change. If the image is not tested, `build-write.sh` refuses it: don't edit
   the list locally. Open a PR with the `--inspect` output and `REPORT.txt` instead.

The patch assumes `/default.prop` and `/init.rc` in the ramdisk and no second/dt sections;
`patch-boot.py` stops if that is not so. Don't use `--boot-len` to point the write at a
different sector: the start sector is fixed in `boot-write.cmd.in`.

## 2. What the patch changes

The patch changes only the ramdisk in the boot partition (eMMC p6).
It does not change `/system` or `/data`.

| File in the ramdisk | Change |
| --- | --- |
| `/default.prop` | Adds `ro.adb.secure=1` and `service.adb.tcp.port=5555` at the end. |
| `/init.rc` | Adds an `on boot` action with `start adbd` at the end. |
| `/adb_keys` | New file, mode 0644, owner root. It holds one line: your `adbkey.pub`. |
| `/default.prop`, `/init.rc` (B-102K-Z image only) | `persist.sys.usb.config=none` becomes `adb`; `--root_seclabel=u:r:su:s0` is removed from `service adbd`. `patch-boot.py` stops unless each line occurs exactly once. |

The stock firmware already sets `ro.secure=0` and `ro.debuggable=1`. Thus, `adbd` runs as root.
The kernel command line sets SELinux to disabled.

The stock firmware does not start `adbd`. The new `on boot` action starts it at each boot.
`adbd` listens on TCP port 5555 on all interfaces.
`adbd` accepts the key in `/adb_keys`. The frame has no SystemUI, so it cannot show a prompt for other keys.

## 3. Equipment and software

For macOS, use the [macOS steps below](#macos).

- A Windows PC with Python 3 and the Android platform tools (`adb`).
- WSL with Ubuntu 24.04, or a Linux PC, to build U-Boot.
- A new microSD card, 4 GB minimum, 256 GB maximum. Use this card only for the frame.
  It must have an MBR partition table. Partition 1 must be FAT32 and start at 1 MiB or later.
  A new card, or a card formatted by Windows, has this layout. The dump needs 2.2 GB of free space on it.
- A card reader.

The scripts are in this repository:

| Script | Function |
| --- | --- |
| `scripts/a33-sdboot/a33.config` | U-Boot settings for this board |
| `scripts/a33-sdboot/build.sh` | Builds U-Boot and the dump script |
| `scripts/a33-sdboot/emmc-dump.cmd` | U-Boot script: reads the first 2 GiB of the eMMC to the card |
| `scripts/a33-sdboot/fel-sdcard.py` | Writes the U-Boot image to the boot area of the card (Windows) |
| `scripts/a33-sdboot/check-dump.py` | Verifies the dump on the PC and copies it to `backups/pf1007-emmc/` |
| `scripts/a33-sdboot/patch-boot.py` | Builds the patched boot image from the dump |
| `scripts/a33-sdboot/build-write.sh` | Builds the guarded U-Boot write script |
| `scripts/a33-sdboot/boot-write.cmd.in` | Template for the write script |

All output goes to `backups/` and `diagnostics/`. Do not publish these folders.
They contain firmware, serial numbers and Wi-Fi passwords.

## macOS

Use these steps in place of sections 4 to 9. Install Python 3 and the Android platform
tools (`adb`). Start Docker Desktop or another Docker engine. Run the commands at the
repository root.

1. Build U-Boot and the dump script:

   ```sh
   bash scripts/a33-sdboot/build-macos.sh
   ```

   The helper downloads the pinned U-Boot source and builds the Docker image. It then
   runs `build.sh` with no network access and with the source mounted read-only.

2. Insert a spare 4–256 GB card in a removable USB reader. Find its disk number, then
   replace `diskN` below. **Prepare erases the card.** Check the printed size and name
   before you type `ERASE diskN`.

   ```sh
   diskutil list external physical
   diskutil info diskN | grep 'Disk Size'   # <exact-bytes> is the number of bytes shown
   sudo python3 -I scripts/a33-sdboot/card-macos.py prepare diskN <exact-bytes>
   ```

   The helper makes an MBR/FAT32 partition, saves the card identity and boot-area backup
   in `diagnostics/a33-sdboot/macos-card/`, and checks each write by reading it back.
   It then ejects the card. Keep that folder with the card.

3. Disconnect frame power, insert the card, then connect power. Do not press the power
   button. The screen stays dark. Wait 30 minutes, disconnect power, and put the card
   in the Mac. Check its disk number again, then verify and save the dump:

   ```sh
   diskutil list external physical
   python3 -I scripts/a33-sdboot/card-macos.py backup diskN <exact-bytes>
   ```

   All 32 chunks must pass. The helper uses `check-dump.py` to save and verify the copy
   in `backups/pf1007-emmc/`, then ejects the card. Make a second copy on another disk.
   This is the first 2 GiB, not a full-device backup. Dump verification also works on
   April `20260410` units.

4. Build the patch and both write scripts. **The write build accepts only the January
   boot hash from section 1.** It stops on April and other boot images.

   ```sh
   adb devices
   python3 -I scripts/a33-sdboot/patch-boot.py --pubkey ~/.android/adbkey.pub --out diagnostics/pf1007/patched
   cat diagnostics/pf1007/patched/REPORT.txt
   bash scripts/a33-sdboot/build-macos.sh apply
   bash scripts/a33-sdboot/build-macos.sh restore
   ```

   Check that the report shows the original hash from section 1, two 15,886,336-byte
   images, and `True` for the kernel and header checks. Keep the restore files.

5. Reinsert the card. Copy the apply files to it, then eject it. The dump files can stay.

   ```sh
   cp diagnostics/pf1007/patched/sdcard-apply/{a33.scr,boot-patched.img} /Volumes/FRAMEBOOT/
   diskutil list external physical
   diskutil eject diskN
   ```

   With frame power disconnected, insert the card and connect power. **Do not disconnect
   power during the write.** Wait 5 minutes, disconnect power, and return the card to the
   Mac. Read `/Volumes/FRAMEBOOT/a33-write-status.txt`. Use the result table in section 9;
   only `OK_WRITTEN_AND_VERIFIED` or `ALREADY_APPLIED_NO_WRITE` is a pass. Then continue
   at section 10. To undo the patch, use the restore files as described in section 13.

To reuse the card after you no longer need it for a restore, run
`sudo python3 -I scripts/a33-sdboot/card-macos.py clean diskN <exact-bytes>`. This restores its saved
boot area and ejects it. It does not restore the card contents erased by `prepare`.

## 4. Prepare the build tools

Do these steps in WSL or Linux, at the repository root.

1. Install the packages:

   ```sh
   sudo apt install gcc-arm-linux-gnueabihf bison flex swig libssl-dev libgnutls28-dev \
     python3-dev python3-setuptools python3-pyelftools bc device-tree-compiler make gcc git
   ```

2. Get the U-Boot source at the tested commit (v2025.10):

   ```sh
   git clone https://github.com/u-boot/u-boot.git ~/u-boot
   git -C ~/u-boot checkout e50b1e8715011def8aff1588081a2649a2c6cd47
   ```

3. Build:

   ```sh
   bash scripts/a33-sdboot/build.sh ~/u-boot
   ```

   The script stops if the source is not at the tested commit.
   It stops if a setting from `a33.config` is not in the final configuration.
   The output is in `diagnostics/a33-sdboot/`:
   `u-boot-sunxi-with-spl.bin`, `a33.scr` (the dump script) and `SHA256SUMS`.

## 5. Make the SD card

Do these steps in an elevated PowerShell on Windows, at the repository root.

1. Put the card in the card reader.
2. Find the disk number of the card:

   ```powershell
   python -I scripts/a33-sdboot/fel-sdcard.py list
   ```

3. Write U-Boot to the boot area of the card. Replace `<n>` with the disk number:

   ```powershell
   python -I scripts/a33-sdboot/fel-sdcard.py prepare <n> diagnostics/a33-sdboot/u-boot-sunxi-with-spl.bin
   ```

   The script refuses system disks, disks larger than 256 GB, GPT disks,
   partitions that start before 1 MiB and cards that already hold a boot image.
   It makes no backup of the card.
   Type `WRITE <n>` to continue.
   The script writes from byte 8192 to the end of the image, then reads the area back and compares it.
   The FAT partition does not change.

4. Copy `diagnostics/a33-sdboot/a33.scr` to the root of the FAT partition on the card.

## 6. Dump the eMMC

The dump only reads the eMMC. It writes 2 GiB of files to the card.

1. Disconnect the power from the frame.
2. Put the card in the TF slot of the frame.
3. Connect the power.
   The screen stays dark. U-Boot has no display output. This is correct.
4. Wait 30 minutes. Then disconnect the power.
5. Put the card in the PC.
6. Verify the dump. Replace `G:\` with the drive of the card:

   ```powershell
   python -I scripts/a33-sdboot/check-dump.py G:\
   ```

   The first line must show `stage: finished` and `emmc_dev: ok`.
   All 32 chunks (`00` to `1f`) must show `ok`.
   The script compares each chunk with the SHA-256 that U-Boot calculated on the frame.
   U-Boot reads each chunk two times and compares the reads before it calculates the hash.
   The script rejects chunks with `0xCC` filler.
   It copies the verified chunks to `backups/pf1007-emmc/` and writes `SHA256SUMS` there.
   It then shows the partition table.

7. If the stage is not `finished`, put the card back in the frame and do steps 1 to 6 again.
   The dump script writes all chunks again.

8. Make a second copy of `backups/pf1007-emmc/` on a different disk.

This dump contains the boot partition (p6), `system` (p7) and `recovery` (p9).
It does not contain `/data` (p1). It is not a full-device backup.

## 7. Build the patched boot image

1. Make sure that `~/.android/adbkey.pub` exists on the PC.
   `adb` makes this key the first time that it starts. To start it, run `adb devices`.
2. Build the patched boot image:

   ```powershell
   python -I scripts/a33-sdboot/patch-boot.py --pubkey $HOME\.android\adbkey.pub --out diagnostics\pf1007\patched
   ```

   The script reads p6 from the dump. It checks each chunk against `SHA256SUMS`.
   It stops if the ramdisk already has `/adb_keys` or the ADB properties.
   It proves that its cpio writer makes the stock ramdisk again, byte for byte, before it changes anything.

3. Read `diagnostics/pf1007/patched/REPORT.txt`. Make sure that:
   - `original` is `d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4  15886336 B`.
   - `patched` is `15886336 B`. The hash is different for each key.
   - `kernel region identical: True`.
   - `header identical except size/id: True`.

## 8. Build the write script

Do these steps in WSL or Linux, at the repository root.

1. Build the apply script:

   ```sh
   bash scripts/a33-sdboot/build-write.sh apply
   ```

   The output is `diagnostics/pf1007/patched/sdcard-apply/`: `a33.scr` and `boot-patched.img`.

2. Build the restore script now. Keep it for the undo procedure:

   ```sh
   bash scripts/a33-sdboot/build-write.sh restore
   ```

   The output is `diagnostics/pf1007/patched/sdcard-restore/`.

The write script does these checks on the frame, in this sequence:

1. The image file on the card has the correct size and SHA-256.
2. p6 on the eMMC has the SHA-256 of the original image.
   If not, the script does not write.
3. If p6 already has the SHA-256 of the new image, the script does not write.
4. The script writes 31,028 sectors at sector 172,032 (p6).
5. The script reads p6 back and compares it with the image by SHA-256 and byte by byte.

## 9. Write the boot image

WARNING: DO NOT DISCONNECT THE POWER WHILE THE WRITE SCRIPT RUNS.
AN INTERRUPTED WRITE LEAVES P6 IN A STATE THAT NEITHER SCRIPT ACCEPTS.
THE FRAME THEN DOES NOT BOOT ANDROID.

1. On the card, delete `a33.scr`, `a33-status.txt` and the `emmc-*.bin` files.
   Do this only after step 6 of section 6 is complete and the second copy exists.
2. Copy `a33.scr` and `boot-patched.img` from `diagnostics/pf1007/patched/sdcard-apply/`
   to the root of the FAT partition on the card.
3. Disconnect the power from the frame.
4. Put the card in the TF slot.
5. Connect the power. The screen stays dark.
6. Wait 5 minutes. Then disconnect the power.
7. Put the card in the PC. Open `a33-write-status.txt`. Read the `result` line.

| `result` | Meaning | Action |
| --- | --- | --- |
| `OK_WRITTEN_AND_VERIFIED` | p6 has the patched image. | Continue at section 10. |
| `ALREADY_APPLIED_NO_WRITE` | p6 already had the patched image. | Continue at section 10. |
| `REFUSED_P6_NOT_EXPECTED_CONTENT` | p6 is not the original image. Nothing was written. | Stop. Compare p6 with your dump. |
| `REFUSED_FILE_HASH`, `REFUSED_FILE_SIZE`, `FAIL_FATLOAD` | The image on the card is incorrect. Nothing was written. | Copy the files again. Do step 2 again. |
| `FAIL_READ_P6` | U-Boot could not read p6. Nothing was written. | Stop. |
| `FAIL_MMC_WRITE`, `FAIL_READBACK`, `FAIL_VERIFY_HASH`, `FAIL_VERIFY_COMPARE` | The write started. p6 can be damaged. | Do not boot Android. The scripts in this repository cannot repair this state. |
| no `result` line, or `a33_stage` not `finished` | The script did not finish. | Do not disconnect the power so soon. Put the card back. Wait longer. |

## 10. Connect

1. Remove the card from the frame.
2. Connect the power. Android starts as before.
3. On the frame, connect to Wi-Fi in Settings.

   CAUTION: WHEN THE FRAME IS ON A NETWORK, AIMOR CONNECTS TO THE VENDOR SERVER.
   THE SERVER CAN SEND ROOT SHELL COMMANDS. BEFORE THIS STEP, BLOCK OUTBOUND TCP PORT 7806
   FROM THE FRAME ON YOUR ROUTER, OR DO SECTION 11 AS YOUR FIRST ACTION AFTER STEP 5.
4. Set a static IP address on the frame (Settings, Wi-Fi, Modify network, Advanced options).
   The Wi-Fi chip on this frame gets a random MAC address at each boot.
   Thus, DHCP gives a different address at each boot.
5. On the PC, connect. Replace `<ip>` with the address of the frame:

   ```sh
   adb connect <ip>:5555
   adb -s <ip>:5555 shell id
   ```

   The result must be `uid=0(root)`.

6. Make sure that the patch is active:

   ```sh
   adb -s <ip>:5555 shell getprop service.adb.tcp.port
   adb -s <ip>:5555 shell getprop ro.adb.secure
   adb -s <ip>:5555 shell cat /adb_keys
   ```

   The results must be `5555`, `1` and the content of your `adbkey.pub`.

## 11. Do these steps immediately after you connect

The AiMOR app (`com.efercro.os.aimor`) runs root shell commands from a vendor server.
The connection has no encryption. Read [aimor-remote-root-shell.md](aimor-remote-root-shell.md) and do its recommended actions.

## 12. Security of the result

- Any device on your network can connect to TCP port 5555.
  Only the private key that matches the public key in `/adb_keys` can authenticate.
  The key pair is `~/.android/adbkey` and `~/.android/adbkey.pub` on the PC that you used in section 7.
- A person with a copy of `~/.android/adbkey` has root on the frame. Keep the key private.
- If you lose the key, you lose ADB. To use a new key:
  1. Restore the original boot image with the restore script from section 8 (see section 13).
  2. Do sections 7 to 9 with the new key.

  The apply script refuses to write over a patched p6. It accepts only the original.

## 13. Undo

The restore script writes the original boot image back to p6.
It writes only if p6 has the SHA-256 of your patched image.

1. Copy `a33.scr` and `boot-original.img` from `diagnostics/pf1007/patched/sdcard-restore/`
   to the root of the FAT partition on the card.
2. Do steps 3 to 7 of section 9. The `result` must be `OK_WRITTEN_AND_VERIFIED`.
3. Remove the card. Android starts without ADB.

The card keeps U-Boot in its boot area. Keep the card with the frame for the next restore.

## 14. April 20260410 firmware

Sections 7 to 9 refuse April firmware, because its boot image has a different SHA-256
(`8ffc2a7d95972422b97ecf7e82da7002011bdacedcbfcc74dd52ae871b98a24e`). That is the guard working.
Do not edit it. Two units on this firmware were rooted with this card route and an April patch
builder instead: #17 and unit G below.

### Where the April patch builder is

The builder is `scripts/pf1007l-macos/build-root.py` in an earlier version of PR #14, commit
[`f91f4c3`](https://github.com/wesbos/photo-frame-dashboard/tree/f91f4c3acb8acaf5a6f0ef3087d4d3c7ad6a10a7).
It accepts only the April hash above. It reuses `patch-boot.py` and `boot-write.cmd.in` from this
folder, so the ramdisk change, the on-frame guards and the undo are the same as in sections 2, 8 and 13.
PR #14 was later reduced to macOS card helpers and no longer contains this builder.
It was never merged, so it has had less review than the scripts on `main`.

### Unit G

Tested 2026-10-12. Host: Windows 11 with WSL 2, Ubuntu 24.04.3.

| Item | Observed |
| --- | --- |
| About model / firmware | PF1007L / `YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260410` |
| AiMOR | 6.0.78 |
| Ports | USB-C only, TF slot, button. Powered from a USB-A port with an A-to-C cable |
| USB data, stock network ADB (T3, T3b) | Not tested. The frame was never connected to the PC over USB |
| Card | 64 GB SDXC, MBR, one 31 GB FAT32 partition starting at 16 MiB |
| Section 6 dump | `stage: finished`, `emmc_dev: ok`, all 32 chunks `ok` |
| Partition starts | env 139264, boot 172032, system 237568, recovery 2400256 |
| Boot image SHA-256 | `8ffc2a7d…`, same as #13, #17, #20 and #27 |
| eMMC size | Not measured. The dump covers only the first 2 GiB |
| Patch report | `kernel region identical: True`, `header identical except size/id: True` |
| Write result | `OK_WRITTEN_AND_VERIFIED`, `h_before` = `8ffc2a7d…` |
| After boot | `uid=0(root)` over Wi-Fi on port 5555, no prompt on the frame. Still root after a reboot |
| Fingerprint | `AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260410:eng/test-keys` |

What was different from sections 4 to 9:

1. The builder runs `mkimage` in Docker. Unit G used the `mkimage` that section 4 builds
   (`diagnostics/a33-sdboot/build/tools/mkimage`) instead. No other line of the builder was changed.
2. Section 7's key came from Windows (`%USERPROFILE%\.android\adbkey` and `.pub`). It was copied
   into `~/.android/` in WSL for the builder, so both the Windows and the WSL `adb` can connect with it.

After root, unit G followed [aimor-remote-root-shell.md](aimor-remote-root-shell.md): AiMOR,
`com.yhk.qeota` and `com.DeviceTest` disabled, `enabled="2"` saved. After a reboot there was no
vendor process and no `:7806` socket. WebView 106, the ISRG Root X1 certificate and the kiosk came
from the same PR #14 commit (`install.py`). After a reboot WebView reported `106.0.5249.126`.

### AiMOR connects quickly

The owner paused the frame's internet in the router app (eero) right after it joined Wi-Fi.
When ADB first connected, `netstat` already showed an `ESTABLISHED` connection to a vendor host on
port 7806. It is not known whether that connection was made before the pause took effect.
`iptables -I OUTPUT -p tcp --dport 7806 -j REJECT` and `am force-stop com.efercro.os.aimor` closed
it, and AiMOR was disabled next.

eero can pause a device but can't block one outbound port. The pause also does not survive a
reboot, because the frame's Wi-Fi MAC changes at each boot.

Not tested, a suggestion only, and **only with persistent ADB like Route S's**: if your router can't
block port 7806, disable AiMOR as your first ADB command, before you install a launcher. Never do
this when your only ADB is temporary (T3c): see T8 in the [start page](pf1007l-start-here.md#t8-lock-it-down-before-the-frame-stays-online). On unit G, AiMOR was disabled while it was still the
only Home app. Settings was then opened with `am start -a android.settings.SETTINGS`, and the frame
kept working until the kiosk was installed.

### Windows and WSL problems on unit G

| Problem | What fixed it |
| --- | --- |
| `build.sh` stopped with `set: pipefail: invalid option name` | Git for Windows had checked the scripts out with CRLF. Clone inside WSL instead (`git -c core.autocrlf=false clone …` into `~`) |
| U-Boot build from a Windows folder whose path has a space | Build in the WSL clone, then copy the outputs to the Windows clone for `fel-sdcard.py` |
| Windows will not format FAT32 larger than 32 GB | One FAT32 partition of 31 GB on the 64 GB card. Section 3's 4 to 256 GB range already allows this |
| The kiosk build needs `zip`, which WSL's Ubuntu does not ship | A small Python script that does `zip -qj`, to avoid another `sudo apt install` |
| `yes \| sdkmanager --licenses` exits with 141 under `set -o pipefail` | `(yes \|\| true) \| sdkmanager … \|\| true` |
| Git Bash rewrote `/data/local/tmp/…` in `adb pull` | `MSYS_NO_PATHCONV=1` |
