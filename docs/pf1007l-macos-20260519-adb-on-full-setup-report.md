# PF1007L / AiMOR `20260519` on macOS: ADB already on, then the full kiosk setup

One PF1007L with the May `20260519` firmware shipped with root ADB already on over USB, so the
entire setup ran over a plain `adb` connection — no FEL, no boot patch, no SD card. This is the
same class as #148, #204 and #240. From stock to the Home HQ kiosk in one session from an
Apple-silicon Mac, following the existing guides unchanged.

## Report

```text
About model / firmware:   PF1007L; YHK.F-null-A33-1001-D1024-PF1007L-FL-AIMOR-OS.0.20260519
                          fingerprint AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260519:eng/test-keys
AiMOR version:            6.0.78
Ports (DC jack, or USB-C only): USB-C only, TF slot
Cable and port that gave USB data: a USB-A to USB-C data cable into the Mac
T3 USB IDs seen / adb devices output: 1f3a:1002, adb devices listed the unit as "device" at first plug-in
T3b network ADB result (port 5555): skipped (frame kept off Wi-Fi until lockdown was done)
T4 sunxi-fel version output (or skipped): skipped (ADB already on)
T5 check-dump stage / chunks (or skipped): skipped
eMMC size in sectors:     30,777,344
Boot partition start sector: 172032 (env 139264, system 237568, recovery 2400256)
Boot image SHA-256 (sector 172032, 31,028 sectors):
                          9a6e2456952f3dc2b99e64ea021321397bdc824364b5c8b42f503f847261630a
Route used and result:    none — root ADB out of the box (1f3a:1002); adb -d shell id = uid=0(root),
                          SELinux disabled, ro.secure=0, persist.sys.usb.config=mass_storage,adb
                          already in /data/property and surviving reboots
Host OS:                  macOS (Apple silicon)
First failed step and its exact output: none
```

## What was different

- **Root ADB out of the box.** The unit came up as `1f3a:1002` with a root shell and
  `ro.secure=0` before anything was done to it. `persist.sys.usb.config=mass_storage,adb` was
  already present and survives a power cycle, so no boot patch was needed and none was applied
  (boot hash above is stock).
- **No Wi-Fi until after lockdown.** The frame had never joined a network (the vendor app had
  never phoned home; `com.efercro.os.aimor`'s server connection was the first thing killed).
  Wi-Fi was configured only after the vendor apps were disabled, using the home network.

## After root

The router blocked the frame while it booted. Then, in this order:

- **Launcher then disable, in that order.** Rootless Launcher 3.9.1 was installed and confirmed
  on the panel before any vendor app was disabled, so the home screen never broke. Then
  `com.efercro.os.aimor`, `com.yhk.qeota` and `com.DeviceTest` were disabled. All three showed
  `enabled="2"` in `package-restrictions.xml` and stayed disabled across the reboot, with no
  vendor processes and no `:7806` connection.
- **WebView 106.** Swapped as in section 6 of the PF1007L guide, with every staged and live file
  compared byte for byte with the host copy; the stock tree was kept on-device as the undo path.
  `/system` had roughly 400 MB free beforehand. The first boot after the swap was clean.
- **CA roots.** GTS Root R1, GTS Root R4 and ISRG Root X1 were absent and added as in the Uhale
  guide, each DER SHA-256 matched. With Wi-Fi up, a `*.workers.dev` dashboard loaded with no
  certificate errors.
- **Kiosk as Home app.** Android 6 has no `cmd package set-home-activity`, so the kiosk's Home
  alias was enabled with its `home` extra and selected as the preferred Home activity through the
  system chooser with **Always**.
- **Boot fixes.** `install.sh check`, `apply` and `verify` passed with `WIFI_DEFER=1`,
  `POWER_FIX=0` (the AXP22x control file is absent on this unit, so POWER_FIX is a no-op) and
  `NTP_SERVER=time.google.com`. After a cold boot the clock is correct, Wi-Fi comes up deferred
  with the configured MAC, and the kiosk is in focus.