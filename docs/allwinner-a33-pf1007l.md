# Allwinner A33 / PF1007L: recovery and dashboard setup

Tested on one PF1007L on 2026-10-09, using a Linux host. This frame was sold as a
BIUFRAME but has an **Allwinner A33**, not the Rockchip RK3126 in the existing
[BIUFRAME guide](biuframe-setup-guide.md). The brand name is not a hardware check.

This guide provides commands for identifying the device, entering stable FEL,
and setting up an **already rooted** unit. The stock unit had no ADB. Getting
root required a custom, board-specific RAM reader/writer and boot-ramdisk patch;
the [boot access notes](allwinner-a33-boot-access.md) describe that work and its
limits. That reader/writer is not included here. **The FEL stub card alone does
not enable ADB or root.** Two later routes use published tools instead:
[root ADB with mainline U-Boot](allwinner-a33-mainline-uboot.md) over USB, and
[root ADB over Wi-Fi from an SD card](allwinner-a33-sdcard-adb-wifi.md) without USB.
To choose a route and test your unit first, see [pf1007l-start-here.md](pf1007l-start-here.md).

If USB data is present but `adb devices` is empty, try [ADB with no additional tools required](#adb-with-no-additional-tools-required) before FEL or an SD card. That path needs a data cable and `adb` only.

**Security:** the AiMOR app runs root shell commands from a vendor server over an
unencrypted connection. Read [aimor-remote-root-shell.md](aimor-remote-root-shell.md)
before you connect the frame to your network.

Follow the [repository's backup, approval and privacy rules](../README.md#rules-we-learned-the-hard-way).
Do not run `scripts/biuframe-setup.sh apply`, `rkdeveloptool`, Rockchip loaders,
or Rockchip partition offsets on an Allwinner unit.

## 1. Identify the board and firmware

Record Settings → About before changing anything. On this unit:

| Item | Observed value |
| --- | --- |
| About-screen model | PF1007L |
| Firmware | `YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113` |
| AiMOR version | 6.0.78 — the app version, **not** the Android version |
| PCB | EFERCRO `PF1007L_MB_V1.0` |
| SoC | Allwinner A33; confirmed by FEL, not just the firmware name |
| Android after ADB access | 6.0.1 / SDK 23 / `armeabi-v7a` |
| Android model / product / device | `AEEZO` / `astar_m86_8723cs` / `astar-m86_8723cs` |
| Build fingerprint | `AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260113:eng/test-keys` |
| RAM / display | 1 GiB / 1280 × 800, density 160 |
| Storage | Samsung `KLMAG2WEMB-B031`, nominal 16 GB eMMC |
| Stock USB | `1f3a:1000`, mass storage only |
| Stable FEL USB | `1f3a:efe8`; `sunxi-fel version` identifies A33 |
| USB after the boot patch | `1f3a:1002`, mass storage + ADB |

The board was opened to confirm markings. Opening it is not needed to read the
About screen or try the SD recovery route. There is no verified disassembly
procedure in this guide; do not pry off shields or short storage pins to enter FEL.

### Second unit: USB-C only, no DC jack

A second PF1007L has the same About-screen model and the same firmware string.
Its hardware is different:

| Item | First unit | Second unit |
| --- | --- | --- |
| Power | DC jack | No DC jack. Power comes through the USB-C port. |
| Ports | DC jack, USB device/OTG port | One USB-C port, one TF (microSD) slot, one power/reset button |
| USB data | `1f3a:1000` stock, `1f3a:efe8` in FEL | None. The port supplies power only. |
| eMMC | Samsung `KLMAG2WEMB-B031` | Samsung `AGND3R`, 30,535,680 sectors |

The second unit never shows a USB device on the host.
This is true in stock Android, with the reset button, and in FEL from the stub card.
The screen stays dark with the stub card, so the Boot ROM does read the TF slot.
Thus, USB ADB and the `sunxi-fel` steps in section 2 do not apply to this unit.

The TF slot is the only data path at boot.
A U-Boot image on the SD card can read and write the eMMC without USB.
A boot ramdisk patch that sets `service.adb.tcp.port=5555` and starts `adbd` at boot
gives root ADB over Wi-Fi. With this property set, `adbd` does not use USB.
After that, use `adb connect <frame-ip>:5555`.
Replace `adb -d` with `adb -s <frame-ip>:5555` in all commands in this guide.

A third PF1007L of this USB-C-only type (same firmware, same 30,535,680-sector eMMC)
**did** show USB data: stock `1f3a:1000` and FEL `1f3a:efe8`. A USB-C to USB-C cable from
a Mac gave nothing, not even power, but a USB-A to USB-C cable worked, through a hub
port with a working USB 2.0 path. Try that before ruling out USB. See
[root ADB with mainline U-Boot](allwinner-a33-mainline-uboot.md#1-get-usb-data-on-the-usb-c-only-unit).

On the second unit, the MBR says that `UDISK` (`/data`, p1) ends at sector 30,633,984.
The eMMC ends at sector 30,535,680. The kernel cuts p1 at the end of the disk.
Do not read past sector 30,535,680.

The first unit, as tested:

Use a USB **data** cable and the device/OTG port, with the normal DC supply:

```sh
lsusb
adb devices -l
```

Disconnect other Android devices. Later commands use `adb -d`, which selects a
USB device and refuses multiple USB targets. If ADB is already available, verify
the properties in section 3 and skip FEL. If it says `unauthorized`, accept the
debugging prompt on the frame; that state is different from no ADB interface.

## ADB with no additional tools required

Do this before FEL, an SD card, a boot patch, or putting the frame on the network.
The stock image already contains the ADB switch. The earlier note that the Test App
password dialog was not a usable route stopped because the password was not known.
It did not show the dialog rejecting this password.

Reported from one PF1007L in [#135](https://github.com/wesbos/photo-frame-dashboard/issues/135):
About firmware ending `20260529`, Android 6.0.1 `eng`/`test-keys`, AiMOR 6.0.78, Windows host.
The frame was not on Wi-Fi. No card was in the TF slot. Nothing was written to the boot partition.
A later comment on that issue confirmed the same About path on a PF1007 and a PF1506.
Another May `20260529` report on the issue, from macOS, used the same steps. After the switch
that host saw `1f3a:1002` rather than `1f3a:1009`. Treat the USB id as a clue, and treat
`adb devices` plus a root shell as the pass condition.

You need:

- a USB-A to USB-C **data** cable
- `adb` on the computer

You do not need an SD card, a FEL stub, U-Boot, a boot-image patch, a network
connection, or the vendor shell on TCP 7806.

### 1. See that ADB is not up yet

Boot the frame to the AiMOR screen and plug in the data cable.

```sh
adb devices -l
```

On the Windows report the host saw USB `1f3a:1008` (PTP) and `adb devices` printed no device.
The macOS report on the same issue saw stock `1f3a:1000` ("Android") and an empty `adb devices`
list. Either result is the starting point, not a reason to open the frame or write a card.

### 2. Open the test app from About

1. Open **About**.
2. Tap **Model Number** until the dialog titled **Open test app** appears. The prompt is **Please enter password**.
3. Enter `YHK88888888`.

That opens `com.DeviceTest` / `com.DeviceTest.FirstRun`.

### 3. Turn the ADB switch on

On that screen, tap the control that reads **IS CLOSED**. It changes to **is open**.
Leave it on **is open**.

Unplug and replug the data cable if the computer does not re-enumerate.

```sh
adb devices -l
adb shell id
adb shell getprop persist.sys.usb.config
adb shell settings get global adb_enabled
```

**Pass:**

| Check | Result on the Windows report in #135 |
| --- | --- |
| USB id | `1f3a:1009` (PTP + ADB). The macOS report on #135 saw `1f3a:1002` instead |
| `adb devices` | the frame listed as `device` |
| `adb shell id` | `uid=0(root)` |
| `persist.sys.usb.config` | `mass_storage,adb` |
| `adb_enabled` | `1` |

Reboot from the panel, or with `adb reboot`, and run the same commands again.
On that unit they were unchanged, including after a power cut in the macOS report.
ADB is then persistent. Stop here. Do not continue to the SD-card section.

**Fail:** the dialog rejects the password, or USB never exposes ADB after **is open**.
Continue with [pf1007l-start-here.md](pf1007l-start-here.md). Route U and Route S
are for that case.

### Where the password is

`YHK88888888` is not in `DeviceTest.apk`. On the unit in #135 it is the string compared by
`com.yhk.rabbit.settingslibrary.fragment.AboutFragment.showCheckOpenTestPwdDialog`
in `launcher_aimor.odex`. A match starts DeviceTest. The APK SHA-256 is the same
6.0.78 hash already published in
[aimor-remote-root-shell.md](aimor-remote-root-shell.md):

`abc4e274940e21729de7b9dbaf1f7969efdf427955d0c4881a319611942fb65d`

A matching APK does not prove every unit's odex is byte-identical. The panel accepted
the password, and the **is open** switch is what made `adbd` appear.

An empty `license.properties` file on a FAT card can also open the manufacturer
tools. That still needs a card. This section does not.

## 2. Use an SD card for stable FEL, if ADB is absent

The recessed Reset button exposed `1f3a:efe8` for about three seconds during
startup, but version queries failed. The Android recovery menu and keyboard-settings detour did not provide a usable ADB route. The Test App password dialog does. The password was not known when this page was written. See [ADB with no additional tools required](#adb-with-no-additional-tools-required). A USB
identity alone is not proof that the Boot ROM protocol is responding.

A spare SD card containing the official FEL boot stub gave **persistent,
queryable FEL**. It does not modify internal eMMC. Removing it and cold-booting
returns to the normal internal boot path.

The [linux-sunxi FEL documentation](https://linux-sunxi.org/FEL#Through_a_special_SD_card_image)
explains this method. The eGON stub requires non-secure boot; it is not guaranteed
to work on another board or a secure-boot unit.

### Build the host tool and verify the stub

You need Git, a C compiler, make, pkg-config, and the libusb/libfdt development
headers. Install those using your host distribution's package manager. The
following pins the upstream revision used for this unit:

```sh
git clone https://github.com/linux-sunxi/sunxi-tools.git diagnostics/sunxi-tools
git -C diagnostics/sunxi-tools checkout d7bbd172a5da601a08f94479de308c6fb714a19a
make -C diagnostics/sunxi-tools sunxi-fel
python3 - <<'PY'
from pathlib import Path
import hashlib
p = Path('diagnostics/sunxi-tools/bin/fel-sdboot.sunxi')
b = p.read_bytes()
assert len(b) == 8192
assert b[4:12] == b'eGON.BT0'
assert hashlib.sha256(b).hexdigest() == '2ccec08a026840571f3804671ba72afae840db27112a43f2b1f122075bc808bc'
print('Verified official 8192-byte FEL SD stub')
PY
```

### Prepare only a positively identified spare card

These are **Linux host commands**. Do not substitute a guessed disk name. Use
`lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS` before and after inserting the reader,
identify the **whole card**, and unmount each of its partitions. The following
procedure is restricted to an MBR card whose partitions begin at or beyond 4 MiB,
matching the layout tested here. It rejects GPT and earlier partition starts.
If that check fails, stop; do not overwrite the partition table to force a match.

Set `FEL_SD_CARD` to the card's whole-device path, not a partition:

```sh
export FEL_SD_CARD=/dev/REPLACE_WITH_SPARE_SD_CARD
sudo env FEL_SD_CARD="$FEL_SD_CARD" python3 - <<'PY'
import gzip, hashlib, json, os, stat, struct, subprocess
from pathlib import Path

card = Path(os.environ['FEL_SD_CARD']).resolve(strict=True)
os.umask(0o077)
assert stat.S_ISBLK(card.stat().st_mode), 'Not a block device'
tree = json.loads(subprocess.check_output(
    ['lsblk', '--json', '-o', 'NAME,MOUNTPOINTS', str(card)], text=True))
def check_unmounted(nodes):
    for node in nodes:
        assert not any(node.get('mountpoints', [])), 'Unmount the card first'
        check_unmounted(node.get('children', []))
check_unmounted(tree['blockdevices'])
stub = Path('diagnostics/sunxi-tools/bin/fel-sdboot.sunxi').read_bytes()
assert len(stub) == 8192
assert hashlib.sha256(stub).hexdigest() == '2ccec08a026840571f3804671ba72afae840db27112a43f2b1f122075bc808bc'
fd = os.open(card, os.O_RDONLY)
try:
    before = os.pread(fd, 4 * 1024 * 1024, 0)
    assert len(before) == 4 * 1024 * 1024
    assert before[510:512] == b'\x55\xaa', 'Expected MBR'
    parts = [before[446+i*16:462+i*16] for i in range(4)]
    active = [p for p in parts if p[4]]
    assert active and all(p[4] != 0xee for p in active), 'GPT/empty layout not supported'
    assert all(struct.unpack_from('<I', p, 8)[0] >= 8192 for p in active), 'Partition too close to stub'
    assert os.pread(fd, len(before), 0) == before, 'Independent reread differs'
finally:
    os.close(fd)
out = Path('backups/a33-fel-card-prefix.bin.gz')
out.parent.mkdir(exist_ok=True)
with gzip.open(out, 'xb') as f:
    f.write(before)
assert gzip.decompress(out.read_bytes()) == before
print('Card prefix backed up; SHA-256:', hashlib.sha256(before).hexdigest())
PY
```

The backup step deliberately refuses to overwrite an existing backup. Keep it
with a private note identifying the card. Recheck `lsblk` immediately before the
write; unplug/replug or disk-name changes invalidate the target selection.
With the owner approving this card write and boot-code execution:

```sh
sudo dd if=diagnostics/sunxi-tools/bin/fel-sdboot.sunxi of="$FEL_SD_CARD" bs=1024 seek=8 count=8 conv=notrunc,fsync
sudo env FEL_SD_CARD="$FEL_SD_CARD" python3 - <<'PY'
import gzip, os
from pathlib import Path
before = gzip.decompress(Path('backups/a33-fel-card-prefix.bin.gz').read_bytes())
stub = Path('diagnostics/sunxi-tools/bin/fel-sdboot.sunxi').read_bytes()
expected = before[:8192] + stub + before[16384:]
with open(os.environ['FEL_SD_CARD'], 'rb') as f:
    assert f.read(len(before)) == expected, 'Card readback mismatch; stop'
print('Exactly 8192 bytes changed at byte offset 8192')
PY
```

1. Unplug **both DC power and USB** from the frame.
2. Insert the prepared card, then reconnect power and the USB data cable.
3. Run `lsusb`, then `diagnostics/sunxi-tools/sunxi-fel version` with only this
   Allwinner device connected. Expected output includes `soc=00001667(A33)`.
4. If permissions fail, fix host USB access; do not treat it as a firmware failure.
   If the query hangs or identifies another SoC, stop and retain the backup.

Keep the recovery card. To undo its preparation, identify/unmount that **same
card**, restore the saved 4 MiB prefix, and reread it to compare with the backup.
To boot Android, disconnect both power sources, remove the FEL card, and reconnect.

**At this point you have recovery access, not root.** `sunxi-fel read` reads
CPU-addressable memory; a Boot ROM or SRAM dump is not an eMMC/Android backup.
The [boot access notes](allwinner-a33-boot-access.md) explain the missing storage
reader and the patch that eventually enabled root ADB on the tested unit.
[Root ADB with mainline U-Boot](allwinner-a33-mainline-uboot.md) continues from here
with published tools: a read-only `ums` backup, then a guarded boot write.

## 3. Confirm root ADB before the Android setup

The [January Windows unit report](pf1007l-windows-20260113-usb-adb-report.md)
reached USB root ADB with a verified one-sector `build.prop` edit after bulk
U-Boot reads failed. Its boot image remained original. It also records the
Windows raw-disk, console-pause, and binary `exec-out` pitfalls from that session.

Only continue once Android boots and ADB actually works:

```sh
adb devices -l
adb -d shell id
adb -d shell getprop ro.product.model
adb -d shell getprop ro.product.cpu.abi
adb -d shell getprop ro.build.version.sdk
adb -d shell getprop ro.build.fingerprint
adb -d shell getprop sys.boot_completed
adb -d shell getenforce
```

This unit returned `uid=0(root)` directly, SDK `23`, `armeabi-v7a`, the fingerprint
in section 1, `sys.boot_completed=1`, and SELinux `Disabled`. It did not need
`su -c` or `adb root`. If shell is not root, or the firmware/board differs, stop:
the system paths and package names below need independent verification.

After a reboot, our host ADB server sometimes failed to rediscover the frame.
`adb kill-server` followed by `adb start-server` fixed discovery. This restarts
the host server and affects other ADB sessions; it does not root the device.

## 4. Back up before modifying Android

Keep all captures in ignored `backups/` or `diagnostics/`. Do not publish the
serial, eMMC CID, Wi-Fi details, full property dumps, vendor APKs or flash images.

Identify partitions on **your** device first:

```sh
adb -d shell 'ls -l /dev/block/by-name; cat /proc/partitions'
adb -d shell 'cat /sys/class/block/mmcblk0p7/size; mount'
```

On the tested unit, `system` resolved to `mmcblk0p7`, 2,097,152 sectors of 512
bytes (1,073,741,824 bytes), mounted read-only. Check both before using this example:

```sh
mkdir -p backups
adb -d exec-out 'dd if=/dev/block/by-name/system bs=1048576 2>/dev/null' > backups/a33-system.img.partial
wc -c < backups/a33-system.img.partial
# Expected ONLY for the matching tested layout: 1073741824
```

Reject an unexpected length or repeated `0xCC` filler. Independently capture the
read-only partition again, compare with `cmp`, record SHA-256, then compress and
verify gzip decompression against that hash. Rename `.partial` only after those
checks pass. Also preserve boot/recovery and the exact original WebView tree:

```sh
adb -d exec-out 'toybox tar -C /system/app -cf - webview 2>/dev/null' > backups/a33-stock-webview.tar
```

Independently reread that tar, compare byte-for-byte, and inspect its members
before any replacement. A `dd`/`tar` error may otherwise leave a misleading file.
Old `adbd` can merge remote stderr into binary `exec-out` output; the `2>/dev/null`
in these commands prevents a `dd` status footer from contaminating the image.

To read the whole eMMC in chunks (`/dev/block/mmcblk0` with `skip=`), use
`/sbin/busybox dd`. The stock `dd` returned **0 bytes, with no error**, for every chunk
that starts at 2 GiB or later (firmware 20260529, observed; also `20260416`, #190). `busybox dd` read those
chunks, and gave the same bytes as the stock `dd` below 2 GiB. Check each chunk's size,
not only its hash: an empty chunk has the same MD5 on the frame and on the host.

The tested session independently verified the whole system partition and boot
image. Recovery had partial spot checks rather than a complete second reread.
This was **not a full-device backup**: userdata, hardware boot areas and every
partition tail were not captured. Before root, the owner explicitly accepted
the limited boot backup covering every proposed modified sector. Do not silently
claim that as compliance with the repository's full backup rule.

## 5. Install a launcher and optional Firefox fallback

Download on the host, verify the hashes, then install. These are the same pinned
sources as the existing guide; importing its download references does not make
its Rockchip `apply` script suitable for this board.

| APK | Source | SHA-256 |
| --- | --- | --- |
| Rootless Launcher 3.9.1 | [F-Droid](https://f-droid.org/repo/amirz.rootless.nexuslauncher_30911.apk) | `7fa44d560dc4577374d45176220de2c0b00a71e09d6d148cdea4e0a52d38404a` |
| Firefox 143.0.4 ARMv7 | [Mozilla archive](https://archive.mozilla.org/pub/fenix/releases/143.0.4/android/fenix-143.0.4-android-armeabi-v7a/fenix-143.0.4.multi.android-armeabi-v7a.apk) | `af560738627d4efc9ace75e708fc48aad6a24c78ef43a89daca27e16ff3829f8` |
| WebView 106.0.5249.126 ARM | [LineageOS at `4b0ae494a7dd`](https://raw.githubusercontent.com/LineageOS/android_external_chromium-webview_prebuilt_arm/4b0ae494a7dd/webview.apk) | `e2edc1f89ec1608b169da9e7ffc037190b70c7825f0be29694f4cae719980580` |

Use private local filenames `diagnostics/rootless.apk`, `diagnostics/firefox.apk`
and `diagnostics/webview.apk` below. Inspect APK signatures, package/version and
minimum SDK with Android build-tools as well as verifying SHA-256.

With the owner approving these installations:

```sh
adb -d install diagnostics/rootless.apk
# Optional fallback; the kiosk does not require Firefox:
adb -d install diagnostics/firefox.apk
adb -d shell am start -a android.intent.action.MAIN -c android.intent.category.HOME -p amirz.rootless.nexuslauncher
```

Confirm the new launcher is visible before disabling the vendor launcher. Also check by hand on the
panel that you can reach Android Settings → Apps from it. On a unit without working USB ADB,
AiMOR is the only route back in that doesn't need the SD card; see
[the lockout notes](pf1007l-20260410-network-adb.md#6-lockout-after-disabling-aimor-and-offline-recovery).

```sh
adb -d shell pm disable com.efercro.os.aimor
adb -d shell input keyevent KEYCODE_HOME
```

Select Rootless Launcher as the Home default if prompted.
Disabling AiMOR also closes its remote root shell connection.
See [aimor-remote-root-shell.md](aimor-remote-root-shell.md).

Confirm the physical screen as well as Android's foreground activity. A
[May 2026 macOS setup](pf1007l-macos-20260529-report.md#android-home-screen-and-evidence-after-reboot)
produced black `adb exec-out screencap -p` images after reboot while the owner saw
Rootless's date, arrow, and search bar on the panel. A black capture alone did not
establish a boot or launcher failure, and changing the animation scale did not fix
the capture. Ask what the panel shows before changing the setup.

Also disable `com.DeviceTest`. It runs as the system user and has an unprotected receiver
that enables or disables components of any package.

The observed vendor
updater was `com.yhk.qeota`, with an active download service. Check that package
on your device before disabling it:

```sh
adb -d shell dumpsys package com.yhk.qeota
adb -d shell pm disable com.yhk.qeota
adb -d shell am force-stop com.yhk.qeota
adb -d shell am force-stop org.mozilla.firefox
adb -d shell settings put global animator_duration_scale 0
```

Record existing animation settings first. Window and transition scales were
already zero on our unit. Do not blanket-disable Android core services.

**Wait for package settings to reach disk before rebooting.** Our first immediate
reboot lost the updater-disable and Firefox-stopped states. `sync` alone does
not force Package Manager's asynchronous XML update. Check the private
`/data/system/users/0/package-restrictions.xml` until the relevant package entries
show `enabled="2"` for disabled packages and `stopped="true"` for Firefox.
Then reboot, check `dumpsys package` again, and check `ps` for restarted processes.
Do not publish that XML. `enabled=2` is the expected `dumpsys` disabled state.

## 6. Upgrade WebView before using the kiosk

Stock WebView was **44.0.2403.119**. The dashboard targets Chrome 106, so a kiosk
using the stock engine was not sufficient. Firefox worked without changing
WebView, but used substantially more RAM in our snapshots.

WebView 106 is an old 2022 engine; these instructions document compatibility
with Android 6, not a current or secure general-purpose browser. Root ADB and
the old OS are also unsuitable for exposing to an untrusted network.

After verifying the system and WebView backups and obtaining approval for this
specific `/system` replacement:

1. Extract **all** `lib/armeabi-v7a/*.so` from the verified WebView APK on the host.
   The tested APK contains `libchromium_android_linker.so`,
   `libcrashpad_handler_trampoline.so` and `libwebviewchromium.so`.
2. Stage the APK/libraries under `/data/local/tmp`, outside the live WebView tree.
3. Check free space with `adb -d shell toybox df -k /system`. Keep enough space
   for both old and new trees; our conservative staging check required 300,000 KiB.
4. Remount `/system` read-write and create `/system/homehq-new-webview` with
   `webview.apk` and `lib/arm/*.so`. Directories must be 0755, files 0644, owner
   root:root. Refuse existing staging or rollback paths rather than overwriting them.
5. Read back every staged file with `adb exec-out` and compare with the host
   bytes **before** touching `/system/app/webview`.
6. Move the original whole tree to `/system/homehq-stock-webview` (outside the
   scanned `app`/`priv-app` directories), then move the new tree to
   `/system/app/webview`. This preserves the original APK **and its odex** and
   avoids leaving an old oat directory in the new tree.
7. Read back every live file again, verify ownership/modes, run `sync`, and remount
   `/system` read-only. Check package-state persistence from section 5, then reboot.
8. Confirm `adb -d shell dumpsys package com.android.webview` reports
   `versionName=106.0.5249.126`, and confirm the kiosk actually renders. Check
   `adb -d logcat -d` privately for `Failed to load library`/`dlopen failed`.

Replacing just the APK can report version 106 while failing at runtime: Android
6 does not extract the compressed native libraries for this system app. Verify
the library files and a real page, not just Package Manager's version number.

Undo before proceeding if a check fails: stop the kiosk, remount `/system`
read-write, move the new live tree aside, restore the preserved original whole
tree to `/system/app/webview`, verify it against the backup, remount read-only,
and reboot. Keep the working launcher/Firefox fallback while testing.

## 7. Build the fullscreen kiosk and serve the demo over USB

The existing [`dashboard/kiosk/`](../dashboard/kiosk) is already a minimal
WebView Activity with immersive mode: it does not have a browser URL bar. Build
using JDK 17, Android build-tools 34.0.0 and platform android-34 as described in
[`build.sh`](../dashboard/kiosk/build.sh); set `ANDROID_HOME` to your SDK directory.
Its default URL is Wes's hosted demo. Change it locally to your own URL, or use
the explicit VIEW intent below to override it.

```sh
cd dashboard
npm ci
npm run build
# Keep this terminal running:
npm run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

In another terminal, from the repository root:

```sh
dashboard/kiosk/build.sh
adb -d install dashboard/kiosk/build/homehq.apk
adb -d reverse tcp:4173 tcp:4173
adb -d shell 'am start -a android.intent.action.VIEW -d "http://127.0.0.1:4173/#home" -n com.wesbos.homehq/.MainActivity'
```

This URL is **localhost on the frame**, forwarded to the host by ADB. It does not
require opening a host firewall port or using the frame's changing Wi-Fi address.
Keep the host server and USB connected. Recreate the reverse mapping after a
device/ADB restart. Hold two fingers still for **1.5 seconds** to exit to the
launcher. Boot auto-start is not implemented by this procedure.

Don't make a two-finger hold your only way out. On one April unit, a different kiosk's two-finger
hold never triggered for the owner. The `gslX680` driver reports multitouch (tracking IDs 0–11),
but [PR #40](https://github.com/wesbos/photo-frame-dashboard/pull/40) observed that it reads two
fingers held close together as one touch. A control revealed by a single tap did work on that unit.

The dashboard contains **sample data**, not your real calendar. Older Android
trust stores can reject external HTTPS images even though the local HTML loads.
That happened with Picsum on this unit. Our local setup used a host image proxy
with normal upstream TLS verification; that proxy and our lighter dashboard
profile are local changes, **not included in this documentation-only PR**.
Use trusted locally served images, or investigate the specific certificate chain
before changing the system CA store. Do not bypass certificate validation.

Quote the entire remote command when URLs contain `&`, for example:

```sh
adb -d shell 'am start -a android.intent.action.VIEW -d "http://127.0.0.1:4173/?diag=0#home" -n com.wesbos.homehq/.MainActivity'
```

`adb shell` joins its arguments for the remote shell; unquoted query-string `&`
can split the command. Ordinary `am start` worked; Firefox's `am start -W`
sometimes timed out even when the page had loaded.

## 8. Measure memory before adding swap

```sh
adb -d shell cat /proc/meminfo
adb -d shell cat /proc/swaps
adb -d shell cat /sys/block/zram0/disksize
adb -d shell cat /sys/block/zram0/mem_used_total
adb -d shell dumpsys meminfo
adb -d shell dumpsys meminfo com.wesbos.homehq
adb -d shell ps
```

This unit already had **256 MiB zRAM**, unlike the Rockchip unit's original
128 MiB. We did not add swap or copy its SuperSU startup hooks. With the custom
kiosk and local lighter dashboard, a final snapshot showed:

| Measurement | Observed |
| --- | --- |
| Firefox processes in earlier snapshot, combined PSS | 387,039 KiB (about 378 MiB) |
| Kiosk PSS in final snapshot | 81,513 KiB (about 80 MiB) |
| System free/reclaimable RAM in final snapshot | 706,327 KiB |
| Swap capacity / usage | 262,140 KiB / 260 KiB |
| zRAM physical memory used | 40 KiB |

These are snapshots with different configurations, not a controlled benchmark
or a guarantee for other pages. No valid before/after touch-latency comparison
was obtained. Extra swap was not indicated by this workload. First reduce
background apps, image dimensions, animated effects and hidden-view work, then
measure again; do not assume the Rockchip swap prescription applies.

### Matched-page comparison on another January unit

On 2026-10-11, a Humblestead PF1007L with the same January firmware, Android 6.0.1,
1 GiB RAM and 1280 × 800 display was measured from a Windows host. WebView
106.0.5249.126 and Firefox 143.0.4 rendered the same lightweight mock dashboard.
This used a separate small kiosk, not Home HQ. No real home controls were used.

| Foreground page and app | Median aggregate PSS | Range | Processes counted |
| --- | --- | --- | --- |
| Mock dashboard, WebView 106 kiosk | 86.78 MiB | 86.78–87.09 MiB | 3 |
| Same mock dashboard, Firefox 143 | 264.63 MiB | 264.39–264.81 MiB | 5 |
| Existing Home Assistant dashboard, Firefox 143 | 357.24 MiB | 356.40–358.06 MiB | 5 |

Each window had 60 s to settle, then six PSS readings at 10 s intervals, on the
same boot. Start each browser afresh on its comparison page, keep the existing
profile and saved login, and perform no actions during the capture. The mock
page was served from the PC over USB reverse. The Home Assistant page used its
existing network path, so it is context, not the same-page engine comparison.

Count all of the app's processes. The kiosk total includes its main process and
`com.android.webview:webview_service` / `webview_apk`. Those two helpers remained
after the kiosk stopped, using about 31–33 MiB during the Firefox captures; their
cost is excluded from the Firefox app totals rather than inflating Firefox's
result. An earlier Firefox run that loaded Home Assistant before the mock had
six processes and 360.69 MiB median PSS; it was excluded from the fresh-page table.

The matched mock page used 177.85 MiB less PSS in the kiosk, about **67.2%**. The
owner felt similar responsiveness in the two browsers on that page. There was
no instrumented touch-latency measurement. Sequential cache/history and thermal
state differed (44–46 °C), and the collector itself affects CPU. This does not
establish a CPU speedup, energy saving or a RAM ratio for other dashboards.

For a repeatable comparison, retain each process's PSS and report the sum for
each reading, then the median/range of those sums. Record app versions, page,
boot, settling time and retained provider processes. Do not compare one app's
Java heap with another app's total PSS. `/proc/meminfo` on this kernel has no
`MemAvailable`; a free-plus-cache estimate is not that kernel metric. Keep raw
process/network reports private.

## 9. January unit: remote management and background services

These are observations from one Humblestead PF1007L, tested on 2026-10-10 through
2026-10-12 with Windows and PowerShell 7. The About-screen firmware was
`YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113`, AiMOR 6.0.78,
Allwinner A33, Android 6.0.1 / SDK 23 / ARMv7. The Android fingerprint matches
section 1. Stock USB was mass storage only; root ADB was enabled with a guarded
boot-ramdisk patch and a custom bounded MMC helper. This is not another rooting
procedure: the helper is not included. The owner accepted two matching boot
captures and limited system backups, **not a full-device backup**. That does not
meet the repository's complete-backup rule, and physical restoration was not
tested. The reports below start after root was established.

### Native Tailscale and root SSH

The official Linux static **ARM** build of Tailscale 1.104.1 ran on this Android
unit; a current Android Tailscale APK was not needed. Download provenance:

| Item | Official source / SHA-256 |
| --- | --- |
| Archive | [tailscale_1.104.1_arm.tgz](https://pkgs.tailscale.com/stable/tailscale_1.104.1_arm.tgz) |
| Official checksum | [archive checksum](https://pkgs.tailscale.com/stable/tailscale_1.104.1_arm.tgz.sha256) |
| Archive SHA-256 | `aea7ae225989d302444b10b44aa42e89fdfa2a691b4d124ed710b4753518a875` |

The version/hash records what was tested, not a recommendation to stay on that
version indefinitely. Before installing any version, check its official checksum
and compatibility. Do not copy authenticated state or publish the sign-in URL.

The tested daemon used `--tun=userspace-networking`, a private Unix socket and
private state/log directories, `--port=0` and `--no-logs-no-support`. Browser
tailnet access used `--outbound-http-proxy-listen=127.0.0.1:1056`; it did not
listen for proxy clients on the LAN. `TS_LOGS_DIR` supplied a writable private
log directory. Root SSH needed two additional Android compatibility adapters:

- Android had no normal `/etc/passwd` database. A daemon-local `getent` adapter
  returned only the existing UID 0 / GID 0 account, with `/system/bin/sh` and a
  private home directory, for a `passwd` query for `root` or `0`. It rejected
  other lookups. It did not create or change a system account.
- Android's `id` rejected the `-Gz` query used for the root account. A local
  adapter returned group 0 with a NUL terminator for that query only and
  delegated other arguments to `/system/bin/id`.

Only the owned daemon's `PATH` included those adapters. SSH sessions used
`/system/bin:/system/xbin`, with `SHELL=/system/bin/sh` and
`TAILSCALE_SSH_DEFAULT_PATH` set to that path. Tailnet authentication and SSH
policy still applied. The first SSH trial failed at policy, before account
lookup; authenticated root SSH worked after the owner approved a frame-specific
rule. Root SSH grants broad device control. Prefer a narrowly scoped rule and
normal interactive tailnet sign-in; an account adapter is not authorization.
Both network access to port 22 and an SSH rule are needed; see the official
[Tailscale SSH guide](https://tailscale.com/docs/features/tailscale-ssh). Its
supported server platforms are Linux and the open-source macOS client. This
Android result with adapters is a one-unit compatibility report, not an official
Android SSH-server support claim. Normal Tailscale coordination and encrypted
tailnet traffic still occur even with support logging disabled.

Userspace networking did **not** give every Android app a VPN interface or
system MagicDNS. The daemon/proxy could reach tailnet IPs and MagicDNS names, and
Firefox could reach them through the loopback proxy. Changing Android DNS to
Quad100 alone does not supply tailnet routes or the userspace DNS interception.
For the production dashboard, the browser used a direct LAN URL with its global
proxy off; Tailscale remained available for management. General kernel/TUN VPN
operation, SSH PTY and SFTP were not tested.
See the official [userspace-networking explanation](https://tailscale.com/docs/concepts/userspace-networking)
and [Quad100 reference](https://tailscale.com/docs/reference/quad100).

### Startup and cleanup

A separate, owner-approved Home/network helper started a fixed root-owned
supervisor after Android boot. It was not a `/system` boot hook. On this firmware,
an ordinary boot receiver alone did not provide reliable startup. The Home task
had to remain available; finishing it prevented later navigation rebinding.
This is additional behavior to check on a unit, not a reason to replace Home HQ's
existing [Home startup](../dashboard/kiosk/README.md#start-at-boot).

The startup implementation checked root, the expected private device identity,
firmware, current boot and payload ownership/modes before running anything.
Authenticated state stayed mode 0600; only trusted root-owned code was executed.
Record and reject symlink or ownership mismatches rather than trusting a path
under shell-writable `/data/local/tmp`. The private helpers are not supplied here,
so this is a record of the required pieces, **not a persistent-install recipe**.

The supervisor waited for its exact daemon child. A PID file or a stale `ready`
marker was insufficient: checks matched command/socket, boot and process identity
before signalling a process. Explicit HUP/INT/TERM handlers performed cleanup;
an EXIT trap alone did not cover the observed signal exits. On this Android 6
build, deleting `http_proxy` alone left the framework proxy active. Cleanup first
set it to `:0`, then deleted it, and only changed it if it still matched the
helper's loopback proxy. Save a prior proxy before testing and do not overwrite a
different proxy installed by someone else.

Planned undo (not exercised): verify independent USB access; keep a working
launcher and on-panel Settings. Prevent helper autostart, disable Tailscale SSH while its
daemon is running, then stop only the matching supervisor/daemon. Restore the
saved proxy and Home destination before removing the newly installed helpers.
Do not copy our private startup paths, policies or authenticated state.

### Vendor background cleanup: the list is an exception list on this build

The first persistent setup later went offline while Wi-Fi still had IPv4.
`BackgroundManagerService` logged force-stops of the network and navigation
helper packages, followed by SIGKILL of their root supervisor/daemon process
group. It also cleared the selected navigation service. A `ready` marker
survived, so checking it alone falsely suggested the network helper was healthy.

Read-only checks on an already rooted, selected unit:

```sh
adb -d shell settings get system kill_background_services
adb -d shell settings get system kill_background_services_list
adb -d shell settings get secure enabled_accessibility_services
adb -d shell settings get secure accessibility_enabled
```

Keep this output private: it can contain personal package/service choices.
Decompiled firmware showed `allowBackgroundTask` treating the comma-separated
`kill_background_services_list` as **exceptions** when all-app cleanup was on,
despite an internal variable named `Blacklist`. A `SettingsObserver` reloaded
the setting live. `executeKillBackgroundTask` and `skipService` consulted it.
This is the `system` namespace; the boot-broadcast list is a different setting.
Do not infer the same semantics on other firmware from the key name alone.

The owner-approved repair appended only the installed network/navigation helper,
launcher and Firefox packages, retaining existing entries and leaving cleanup
enabled for other apps. It saved the exact original value (including absence),
compared it before writing, verified readback and the live Binder allow results,
and checked that an unlisted probe was still disallowed. The writer attempts
restoration only on the live-allow timeout, while the setting still matches its
candidate. Readback/probe and transport failures have no automatic rollback.
Planned undo (not exercised): restore the saved value, or delete the key if it
was originally absent, only while it still matches the candidate. No vendor
firmware was edited and no blanket cleanup-disable was needed.

The Binder transaction number and allowlist writer are intentionally not offered
as generic paste-in commands. Confirm the implementation and transaction on the
exact firmware, keep the original setting, and obtain approval for the specific
packages before changing it. This behavior differs from the May service-selection
reset in [PR71](https://github.com/wesbos/photo-frame-dashboard/pull/71).

### What passed, and what remains untested

After the cleanup repair, 20 read-only observations over 603.2 s retained the same
daemon and bound navigation while Firefox stayed foreground, without bringing a
helper activity to the front as keepalive. Software and owner-performed cold
boots later recovered Wi-Fi, authenticated Tailscale root SSH and navigation
without a host starting the daemon. Earlier failed cold boots remain relevant:
changing the Wi-Fi MAC before IPv4 existed disrupted association on this unit;
deferring that change until IPv4 appeared passed later tests. The underlying
driver cause was not proven. This is not evidence against the different strategy
tested on newer firmware in [pf1007l-boot-fixes.md](pf1007l-boot-fixes.md).

A separate three-hour capture after five minutes settling recorded 180 one-minute
samples with Wi-Fi IPv4, Tailscale Online and the same daemon at every sample,
with no sample gaps. It cannot exclude brief outages between readings or establish
indefinite uptime. The collectors and private logs are not shipped in this repo.

The January frame also retained its selected accessibility component across a
reboot while `accessibility_enabled` became `0`. A selected-services check alone
misses that state. Our separately approved navigation app restored only the
master switch when its own component remained selected. The Home HQ repair for
this case is host-tested, not installed or physically reboot-tested on this unit.

## Undo and hand-off

- Re-enable vendor apps with `pm enable com.efercro.os.aimor` and
  `pm enable com.yhk.qeota`, then start Home. Android 6's `pm` here lacked
  `default-state`: this restores functionality with explicitly enabled state
  rather than the original default-enabled state.
- Restore the original animator setting; if originally unset, use
  `settings delete global animator_duration_scale`.
- Restore the whole original WebView tree using section 6, not just its APK.
- Uninstall newly added apps only after a working Home launcher is restored.
- `adb -d reverse --remove tcp:4173` removes the USB dashboard mapping.
- Keep verified boot/system backups and the FEL card private and available.
  Restoring a boot patch requires the same board-specific, bounded storage writer;
  `sunxi-fel` alone does not provide an eMMC restore command.

This setup does not update Android, remove the root exposure, configure automatic
startup, or integrate real calendar data. Those are separate tasks.

## Sensor and native UI observations

Tested on one PF1007L over USB from Linux: AiMOR 6.0.78, reported firmware
suffix `V10-1680.0.20260529`, Android 6.0.1 / SDK 23, A33, about 1 GiB RAM,
1280 × 800 display and nominal 16 GB eMMC. Inventory used read-only
`dumpsys`, `/proc` and `/sys`; no board teardown or bus writes.

An [existing PF1007L report](pf1007l-macos-20260529-no-mmc-hs-report.md) lists
the same sensor names. Additional checks distinguish working behavior from
advertised interfaces:

| Interface | Observed | Unverified |
| --- | --- | --- |
| SC7A20 accelerometer | Live XYZ samples; `sc7a20` at I2C `1-0019`. Physical portrait/landscape rotation worked with `SCREEN_ORIENTATION_FULL_SENSOR`. | Calibration and accuracy. |
| LTR-C216R-14 light | SensorService sends values 63–64 to AutomaticBrightnessController. | Response to changing light; physical part identity. |
| AW. ambient temperature | Type 13 advertised; no samples or active client. | A working ambient sensor. |
| SoC thermal | `sunxi-therm` reports raw 43 in thermal and hwmon nodes. | Scaling and calibration; distinct from ambient temperature. |
| Silead touch | `gslX680new` at I2C `0-0040`; multitouch advertised. Taps and swipes worked. | Reliable close two-finger gestures. |
| Audio | `SUNXI-CODEC` exposes playback/capture; speaker playback works. | Fitted microphone or working capture. |
| Camera | Camera HAL present; camera service reports zero devices. | Physical inspection. |
| Bluetooth | Feature flags present; no sysfs/rfkill controller, Bluetooth app or connected framework service. | Working Android stack or fitted radio; Linux BLE support is reported below on a different unit (the Omarchy SD build). |
| Power | USB online. Battery node reports present/charging with zero voltage/capacity. Reconnecting USB power caused a cold boot. | A usable battery. |

No gyroscope, magnetometer or proximity sensor was listed. SensorService's
"9-axis fusion disabled" message and Android feature flags do not establish
fitted hardware. USB data and power worked; host peripherals were not tested.

VirtualSoftKeys intercepted roughly the bottom 64 pixels even when invisible.
Moving controls above the overlay restored taps. Keep an accessible exit to
the launcher and Settings.

Firefox reported software WebRender and `FEATURE_FAILURE_NO_GLES_3` on the
Mali-400. Dashboard app PSS was about 265 MiB in Firefox, 46 MiB in stock
WebView and 10–12 MiB in a native framebuffer app. A native RGB565 photo viewer used
23–25 MiB with one decoded next photo, bounded thumbnail workers and a 4 MiB
thumbnail cache. These are short-run snapshots of different implementations,
not a controlled benchmark. PSS excludes GPU allocations and memory attributed
to shared compositor/media services.

scrcpy 5.0.1 AOA HID worked without video/audio mirroring. Over 30 key presses,
the native app's event-to-draw interval was median 13 ms, p95 22 ms. This
excludes USB transit, scanout and pixel response; it is not end-to-end latency.

## Native Linux / Omarchy SD build

Paolo Rosson ([`@redp314`](https://x.com/redp314)) built a separate, experimental
Arch Linux ARM and Omarchy path for the Humblestead HM-PF1007-BK / EFERCRO
PF1007L variant. It boots from microSD and deliberately leaves the original
eMMC untouched; it is independent of this guide's Android recovery and boot
patch routes.

The tested unit has an Allwinner A33, 1 GB RAM, Mali-400 graphics, an 800×1280
DSI panel, Silead touch, and AIC8800 Wi-Fi/Bluetooth. Its working features are
Hyprland/Omarchy, display and touch rotation, an on-screen keyboard, Wi-Fi,
and Bluetooth LE mouse/keyboard support. Audio, accelerometer-based rotation,
and automatic ambient-light dimming are still being brought up. The internal
radio is 2.4 GHz only.

The SD-image builder and frame-specific installer are at
[`pangoleen/ormarch-picture-frame`](https://github.com/pangoleen/ormarch-picture-frame/tree/a3d83874aabcae655f245973e6408937a591e39f)
(linked at the commit we looked at). **It is third-party and has not been reviewed here.** The image
enables passwordless `sudo` and an auto-login console on USB serial, so anyone with the frame in
hand has root.
They are for this exact PF1007L hardware family: start with the device checks
and keep the original card and Android firmware backup before attempting the
Linux route.
