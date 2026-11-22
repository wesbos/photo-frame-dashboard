# CYPID C1 / AiMOR 4.0.0 (Allwinner A333, Android 15)

One C1 tested on Linux on 21–22 November 2026. Android Settings and authenticated USB ADB were
reached without a firmware flash; KISS Launcher was selected as Home and the built-in calendar was
left enabled. This is a one-unit record, not a confirmed route for other C1 firmware.

**There is no verified full flash or userdata backup and no proven restoration procedure for this
unit.** The owner explicitly approved the settings, app installs and temporary RAM tests below
before a full backup existed. The copied stock APKs are not a firmware backup. Follow the
[backup and approval rules](../README.md#rules-we-learned-the-hard-way) before changing another
unit; do not flash a PF1508, A33, A133 or other device's images to it.

## Identify it

| Field | Observation |
| --- | --- |
| Model / AiMOR | `C1` / 4.0.0, package `com.efercro.calendar` |
| Firmware | `YHK.C-calendar-A333-1506-D2048-K692-V10-216-C1.0.20260801` |
| Android build | `C1_216_SY15_20260801`; fingerprint `Allwinner/a537_pro_arm64/a537-pro:15/AP3A.241105.008/26080114:user/release-keys` |
| SoC / board | Allwinner A333 marking; `ro.hardware=sun65iw1p1`, `ro.board.platform=earth`; board marked `K692_MB_V1.0` |
| Android | 15, SDK 35, `arm64-v8a`, `user`, `ro.debuggable=0`, SELinux enforcing |
| Verified boot | `green`; bootloader reported locked. This does not establish the BootROM's security configuration. |
| Display / WebView | 1280×800 at 160 dpi; `com.android.webview` 124.0.6367.219 |
| Storage | Toshiba `THGBMAG7A2JBAIR` marking; its product listing identifies 16 GB eMMC. Actual sector count and hardware boot-area sizes were not measured. |
| USB | Before debugging, `1f3a:4ee1` presented MTP; with USB debugging enabled, `1f3a:4ee7` presented ADB. |

## Reach Android Settings and USB ADB

The [PF1508 test-app route](allwinner-a333-pf1508.md#get-adb) was not successful on this
calendar. On the tested unit, About → MAC address repeatedly opened **Open Aging**, and Device ID
repeatedly opened **Open Factory**; the PF1508 test-app password was rejected. Calendar ID opened
**Change Server**. Do not select factory reset or clear test data.

Instead, the computer used an Android Open Accessory (AOA) HID keyboard while the device was in
MTP mode. Android Settings opened when the host sent **Meta+I**. This changes the input-device
state and can recreate activities; it did not install an app or require ADB. The
[AOA HID sequence and keyboard descriptor](uhale-hsb-f10.md#1-open-the-browser-through-usb-hid)
are documented for another frame. For this C1, after registering that descriptor and allowing the
keyboard to appear, the observed eight-byte press report was `08 00 0c 00 00 00 00 00`, followed
by eight zero bytes to release the keys; the host then unregistered the HID. The host selected the
single `1f3a:4ee1` device. This is protocol evidence, not a bundled general-purpose keyboard tool.
A physical or OTG keyboard route was not tested.

On the panel, the owner then:

1. Opened **About tablet** and tapped **Build number** seven times to enable Developer options.
2. Opened **System → Developer options** and enabled **USB debugging**. The computer's RSA
   fingerprint was checked and authorized on the panel.
3. Also enabled **Stay awake**; its original value was not recorded.

The resulting `adb shell` was `uid=2000(shell)`, not root; raw block-device reads were denied.
USB ADB and its authorization returned after reboots on this unit. An unknown host key and network
ADB authorization were not tested. Leaving USB debugging enabled permits the authorized computer
access when connected; revoke authorization or disable debugging only after confirming a usable
on-panel route back into Settings.

## Replace Home without removing AiMOR

With the owner's approval before a full backup, the host installed KISS Launcher 3.26.0 (package
`fr.neamar.kiss`, version code 224), first opened it without changing Home, and verified on the panel
that KISS could open **Settings → Apps**. The tested [F-Droid APK](https://f-droid.org/repo/fr.neamar.kiss_224.apk)
had SHA-256 `da6ab0b1219ad3b5ee573698523fb15d60a918083e0843f94a03c1b12e1098c9`.
The host then selected `fr.neamar.kiss/.MainActivity` as Home. KISS and USB ADB returned after a
reboot; AiMOR and its updater were left enabled. Rotation worked when the owner changed the panel's
orientation. KISS is a launcher, not a hosted-dashboard kiosk; a dashboard was not tested here.

The original Home component was `com.efercro.calendar/.pages.WidgetActivity`. This rollback was
recorded, **not tested**, and requires working authorized ADB:

```sh
adb -d shell cmd package set-home-activity com.efercro.calendar/.pages.WidgetActivity
```

Uninstalling KISS with `adb -d uninstall fr.neamar.kiss` was also not tested and deletes its app
data. Do not disable AiMOR or its updater based on this report; their boot and update dependencies
were not established.

## Navigation bar and reboot behavior

This firmware's `Settings.Global` key `navigationbars_state` was originally `2`. With owner
approval, ADB changed it to `1`, producing the standard Back, Home and Recents bar. The owner
confirmed Home and Back on the panel. After a later power cycle, the setting had returned to `2`
and the bar was absent; the reason for the reset is not established.

The local [C1 navigation restore helper](../scripts/cypid-c1-nav/) is a narrow alternative for
this exact Android model, display ID and fingerprint. It has no Internet permission and does not
activate on its own. Its build script creates an APK and a private signing key under
`diagnostics/cypid-c1/nav-helper/`; building does not install it. With separate owner approval,
the tested unit installed version 1.2, granted `android.permission.WRITE_SECURE_SETTINGS` via ADB,
and the owner tapped **Enable navigation restore at boot**. After one software reboot, the helper
received `BOOT_COMPLETED`, requested value `1`, and ADB subsequently observed the bar; Home and
Back worked on the panel. The setting is hidden from the helper's readback, so its success message
means the write was accepted, not that the app independently verified the bar. Cold-power-cycle
persistence with the helper enabled was not established by that test.

For a new build, set `ANDROID_HOME` to an Android SDK containing build-tools 36.0.0 and
`platforms/android-37.0/android.jar`, and `JAVA_HOME` to a JDK 17 installation. Then run
`scripts/cypid-c1-nav/build.sh` on the host. It reuses `signing.p12` if present but overwrites its
output `c1nav.apk`; preserve an existing APK and signing key first. With separate approval, install
the resulting APK with `adb -d install diagnostics/cypid-c1/nav-helper/c1nav.apk`, grant the
permission below, and enable the helper on the panel. A different signing key cannot update the
installed helper; do not uninstall it just to work around that without accounting for its data and
permission grant.

For this unit, the following commands were used for the live setting and permission grant; each is
a device change requiring the owner's approval. They are not a general Android setting recipe.

```sh
adb -d shell settings put global navigationbars_state 1
adb -d shell pm grant com.photoframe.c1nav android.permission.WRITE_SECURE_SETTINGS
```

To disable the helper's boot behavior, open it and tap **Disable navigation restore at boot**; this
was not tested and does not change the current bar setting. The original taskbar value can be
requested with `adb -d shell settings put global navigationbars_state 2` (rollback untested).
Uninstalling the helper removes its app data and grant but does not restore the setting. Preserve
the private `signing.p12` separately: updating the installed APK requires the same signing key.
The grant is broad; keep the APK and key private and grant it only to the intended helper.

## Backup and recovery research: incomplete

- Android listed user-area A/B boot-chain partitions and virtual A/B COW mappings, but shell could
  not read raw block devices. Snapshot merge state was not established. Android's device tree
  associates the eMMC with controller `0x0400a000`; it contains `mmc-bootpart-noacc`, and Linux
  exposed no `mmcblk0boot` nodes. This does not prove that the hardware boot areas are absent.
- FEL enumerated as `1f3a:efe8`, protocol 1, SoC ID `0x1919`. A bounded SRAM read and two tiny
  owner-approved RAM-only programs worked. They did **not** read eMMC, initialize DRAM, or verify a
  restore path. The unit returned caller address `0x000182d0`; its memory mapping is unknown.
- **Tool pitfall:** `sunxi-fel` 1.4.2 truncated the 32-bit version-response scratchpad field to
  16 bits. It displayed `0x9000`; decoding the raw version response gave `0x00069000`. An attempted
  upload at the mistaken address failed and was not executed; whether it changed memory is unknown.
  A subsequent read at `0x9000` timed out after a short response. Do not infer the correct address
  on another device from this unit or treat a USB overflow as proof of a security restriction.
- The available A333-family DRAM initializer targets other power hardware and is not C1-validated.
  SyterKit's MMC high-speed tuning code can **write a pattern to eMMC**; it must not be used
  unmodified as a backup reader. The C1's eMMC pinmux, rail settings and a read-only reader remain
  unverified. A logical user-area image alone would not include separate boot areas, RPMB or
  device-bound secrets.
- Receive-only serial capture at 1.5 Mbaud, 8N1 produced readable KeyMint/TEE messages, not a
  Boot0 or U-Boot console. Captures at 115200 and 57600 did not decode usefully; other stages'
  rates and an interactive console were not established.
- Owner-approved vendor update metadata checks for the installed version and an earlier reported
  version returned `hasUpdate=false` and no URL. No package was downloaded or installed; this does
  not prove that a factory image does not exist.

Keep private records, stock APKs, the helper signing key, serial captures and SRAM dumps out of
commits and public reports. The ignored `frames/` and `diagnostics/` directories are not a backup
by themselves; copy the needed private material to secure storage outside the checkout.
