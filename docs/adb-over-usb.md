# ADB over USB: a checklist for Frameo frames

Most of these frames can speak ADB over USB, but getting there is fiddly: the cable
matters, the toggle is buried in the vendor app, and on frames with no on-screen UI the
authorization prompt never appears. This is a starting checklist, not a guarantee —
firmware varies, so note what your unit does and add it to the [device index](devices.md).

## 1. Use the right cable

- Use a **USB-A (computer) to USB-C (frame) data cable**, not a charge-only cable.
- On some frames a **USB-C to USB-C** cable enumerates nothing on the host — no power, no
  data (the README notes this for the PF1007L). If `adb devices` is empty, change the cable
  before trying anything else. Wireless ADB and the reset button are dead ends on many units.

## 2. Turn on ADB in the vendor app, before connecting USB

- Frameo: **Settings → Beta program → ADB access**, and enable it.
- Do this with the frame **not** plugged into the computer, then connect the cable.
- The path differs by vendor app. Some use a hidden tap counter and a code instead — for
  example the Arzopa app is Settings → About, tap the version five times, then an ADB toggle
  with a code. Decompiling the vendor app (jadx) reveals these; see
  [app-analysis.md](app-analysis.md).

## 3. Check from the computer

Run `adb devices`:

- **`device`** — authorized. You're in. Some frames don't enforce the key check and show
  `device` immediately even though `ro.adb.secure=1`.
- **`unauthorized`** — the frame enforces the key check and is waiting for you to approve
  this computer on its screen.

## 4. If it stays `unauthorized`

Normally you tap **Allow USB debugging** (and "always allow from this computer") on the
frame. The catch on many of these frames:

- **No SystemUI.** Several frames ship with `com.android.systemui` disabled — no status bar,
  no navigation bar — so the approval dialog has nowhere to appear and `unauthorized` cannot
  be cleared from the screen.
- Before assuming that, try a **different cable, USB port, or computer**: a flaky link can
  also read as `unauthorized`.

If the frame truly enforces keys and cannot show the prompt, the only way in is to place
your host's public key (`~/.android/adbkey.pub`) into the frame's key file **offline**:

- On a secured frame (`ro.secure=1`, SELinux enforcing), that file is
  `/data/misc/adb/adb_keys`, owned `system:shell`, mode `0640`, SELinux context
  `adb_keys_file`. A root-level `/adb_keys` is read only where SELinux is permissive or off.
- Reaching the filesystem offline means root, a writable bootloader, or loader mode (FEL on
  Allwinner A33). This is **frame-specific and not always achievable.** One trap: if userdata
  was not cleanly unmounted, the ext4 journal replays on the next boot and can undo an
  offline write — so read and edit userdata only after the frame has booted once, when the
  journal is clean. A33 background:
  [allwinner-a33-boot-access.md](allwinner-a33-boot-access.md),
  [allwinner-a33-mainline-uboot.md](allwinner-a33-mainline-uboot.md). PF1007L:
  [pf1007l-start-here.md](pf1007l-start-here.md).

## Before you put the frame online

Getting ADB is only step one. Before the frame touches the internet, check for hidden root
agents (for example `iotv`) and disable the vendor updaters — see the
[rules](../README.md#rules-we-learned-the-hard-way) and [app-updates.md](app-updates.md).
