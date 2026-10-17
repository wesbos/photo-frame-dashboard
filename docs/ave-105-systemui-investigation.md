# AVE-105: Rockchip platform signing and donor SystemUI

Findings from one [AVE-105, Android 9 Go unit](ave-105.md), tested on 2026-10-17
from macOS on Apple Silicon. This documents an experimental userdata-only
restoration. No system/vendor/boot partition was remounted or changed.

**Current result:** adapted SystemUI v3 renders status/navigation bars,
notifications, quick settings, and classic Recents. Back/Home/Recents passed
ADB tap checks. Notification pull-down and swipe-up passed injected touchscreen
checks after a startup fix; physical confirmation after that fix remains
pending. Background-service persistence, recovery after process death, and
reboot startup are not solved. Firmware dumps, donor/rebuilt APKs, downloaded
keys, screenshots, and private logs are not included in this contribution.

## Exact target and initial state

Match all of these before considering the same adaptation:

- `AVE-105`, `rk3326_go`, Android 9 / API 28, 32-bit `armeabi-v7a`.
- Build `AVE-105.user.2026-04-28+19:38:34`.
- Product version `K2001-V1.2-frameo-LM-202604281938`.
- Fingerprint `rockchip/rk3326_go/rk3326_go:9/PI/zhiheg204281937:user/release-keys`.
- Target `framework-res.apk` SHA-256:
  `3f6a094b94f16d3e3530c3341271be502b12a3a00c8636192261a58bbb004646`.

Initially `com.android.systemui` was absent, including from `pm list packages -u`.
No SystemUI APK was found under `/system`, `/vendor`, or `/oem`. The dark-theme
package is only an overlay. `statusbar`, `notification`, and `window` Binder
services existed. The platform privileged-permission XML retained a SystemUI
entry; copied `services.vdex` retained `startSystemUi` and SystemUIService
symbols. Symbols alone do not prove reachable vendor startup code.

## Public Rockchip platform key matches this firmware

The signature on the frame's `framework-res.apk` verifies with Android SDK
`apksigner`. Its signing-certificate SHA-256 is:

```text
2d370c21f5dfd553d2a796314b70925fb38adeef90864c920bbbbb12887d3522
```

The certificate matches the pinned public
[ASUS Tinker Board Rockchip Android 9 platform certificate](https://github.com/TinkerBoard-Android/rockchip-android-build/blob/7f04fdfe9bd7adbf552d6aee63d436826c8f2dad/target/product/security/platform.x509.pem).
That same source tree also publicly publishes the matching
[development private key, `platform.pk8`](https://github.com/TinkerBoard-Android/rockchip-android-build/blob/7f04fdfe9bd7adbf552d6aee63d436826c8f2dad/target/product/security/platform.pk8).
The private key's derived public key was compared with the device certificate's
public key and matched. This establishes signing capability, not merely a match
between two public certificates. The key was already published upstream; it
was not extracted from this frame and is not committed here.

| Published input | SHA-256 of downloaded file |
| --- | --- |
| `platform.x509.pem` | `29873cf3837dd45d61cd0e7bcb37c75306f4f2e63d7e46956c8a5640e70019e6` |
| `platform.pk8` | `f24056fe406bc0b609e34b8ca2b23f9bef52401712f212ad438bba976791945b` |

The file hash of PEM text above is different from the certificate fingerprint
because they hash different encodings. The derived public-key DER SHA-256 is
`0c091d8aedbd6252e90dcfedb7816165a7806010d0c3df18fbceadd7a76ab896`.
The same certificate also appears in the pinned
[Rockchip Android 7.1 source](https://github.com/rockchip-android/build/blob/c8a3e0a0958efd0b96a6d26fe2a15921bc0fb97d/target/product/security/platform.x509.pem).
Do not identify a signing key by its generic Android certificate subject.

Useful read-only checks on independently obtained files:

```sh
apksigner verify --print-certs framework-res.apk
openssl x509 -in platform.x509.pem -pubkey -noout |
  openssl pkey -pubin -outform DER | openssl dgst -sha256
openssl pkey -inform DER -in platform.pk8 -pubout -outform DER |
  openssl dgst -sha256
```

Matching platform signing allowed the adapted APK, installed under `/data/app`,
to receive required signature permissions on this Android 9 firmware. Actual
grants were checked for status-bar/internal-window control, activity stacks,
Recents, cross-user operations, secure settings, USB/user management, and
framebuffer access. Signing does not establish resource/API compatibility,
system-app status, boot-time execution, or protection from low-memory kills.
This finding is scoped to this firmware; do not assume newer Android versions
or other frames grant the same permissions.

## Official donor provenance

The donor comes from [Radxa's official Rock Pi Android 9 release](https://github.com/radxa/manifests/releases/tag/RockPi-android9-20200826_1210),
also linked by the [Rock Pi download page](https://wiki.radxa.com/Rockpi4/downloads).
Use the tablet archive, not the separate `_box` image:

```text
rockpi-4b-rk3399-android9-20200827_1006_94736e8-gpt.zip
952,525,782 bytes
Locally computed archive SHA-256:
605fd94e3ed7b96520495c37557fa62105913c9e29f9f6779b1cac74f3106d0e
```

The local digest is a reproducibility record, not a publisher-supplied checksum.
ZIP CRC and the extracted image's GPT header/partition-table CRC checks passed.
The system ext4 filesystem was read on the host without mounting or executing
the image. **The RK3399 firmware is only an APK extraction source; do not flash
it to the AVE-105.**

Extracted `/system/priv-app/SystemUI/SystemUI.apk`:

| Check | Result |
| --- | --- |
| Package / version | `com.android.systemui`, version 9 / code 28 |
| Minimum / target SDK | 28 / 28 |
| Signing certificate | Exact target platform-certificate match above |
| APK bytes | 20,368,367 |
| APK SHA-256 | `394aa5739a076b3eac685090cc309328c23b7b85907f3f2fc59bacf473b95f94` |
| Application code | Full `classes.dex`, 6,740,808 bytes, DEX 039 |
| Native libraries | None bundled |
| Donor build | RK3399, Android 9, `PI/1.0.1`, security patch 2019-12-05 |

Although the donor OS is 64-bit, this APK contains Java code and no native
libraries. Do not copy its ARM64 precompiled files to the 32-bit frame.

## Required resource and code adaptation

The donor is **not a drop-in APK**. Comparing target and donor framework resource
IDs by type/name found 10,265 target entries, 10,266 donor entries, and 10,263
shared IDs. Of the shared IDs, **1,804 name different resources**: 1,595 drawables
and 209 strings. Only 8,459 shared IDs retain their original meaning.

For example, donor constant `0x01040648` means `string/system_ui_date_pattern`,
but means `string/tethered_notification_message` on the frame. An unchanged
donor would also select incorrect icons even with a matching certificate.

The successful local adaptation used these steps:

1. Decode the donor with its own framework using official
   [Apktool 2.12.1](https://github.com/iBotPeaches/Apktool/releases/tag/v2.12.1).
   The downloaded JAR matched release metadata SHA-256
   `66cf4524a4a45a7f56567d08b2c9b6ec237bcdd78cee69fd4a59c8a0243aeafa`.
2. Map framework references by resource type/name, not numerical offset.
   Retarget **38 code constants across 17 smali files**, including five Wi-Fi
   icon entries in static arrays. An initial instruction-only scan found only
   33 sites. Seven XML typed references and one resource-table reference also
   required the target framework.
3. Relink decoded resources against the actual AVE-105 `framework-res.apk`.
   This step alone does not fix framework constants embedded in application code.
4. Apply the absent-wallpaper guards and scrim initialization below, build,
   ZIP-align, and sign with the verified matching Rockchip platform key.
5. Verify the signature, re-decode the result, compare intended code/resources,
   then independently compare the installed APK hash with the local artifact.

A fresh decode of the first retargeted build matched all 5,322 intended smali
files, all 2,364 resource files, and its manifest. Later compatibility edits were
checked separately. A static target-framework audit resolved 5,696 of 5,723
method references through copied framework declarations and all 509 field
references. The other 27 method references were inherited Java/XML methods
outside that copied file. This is a partial audit: reflection, other boot
libraries, Binder behavior, and startup still require runtime testing.

### Missing wallpaper Binder

The first retargeted build installed but crashed in
`LockscreenWallpaper.<init>` when calling `setLockWallpaperCallback` on a null
wallpaper Binder. The service was absent before this work.

The second build guards that constructor, `getBitmap`/`loadBitmap`, and ambient
wallpaper calls in `StatusBar` and `DozeWallpaperState`. Missing-service paths
return no lockscreen bitmap or skip the Binder call; existing wallpaper behavior
is retained when the service exists. No wallpaper service was removed.

### Transparent startup scrim swallowed touch

Touch pull-down failed in both the launcher and Settings even though ADB could
expand the shade. Expansion-disable flags were zero and
`config_enableNotificationShadeDrag=true`. A held injected swipe reached the
StatusBar input channel and root view but never began panel tracking.

The live dump showed scrim state `UNINITIALIZED`, target front alpha `-1.0`,
and rendered alpha `0.0`. The donor marks nonzero target alpha clickable, so
this transparent front layer intercepted touches. Firmware policy reported
`deviceHasKeyguard=false`, while donor keyguard/screen lifecycle initialization
was incomplete. Missing normal startup callbacks are the likely trigger.

Version 3 calls the existing `StatusBar.updateScrimController()` once at the
end of `StatusBar.start()`, after its dependencies initialize. It selects a
state using existing fields, rather than disabling scrims. The resulting state
was `UNLOCKED` with front alpha `0.0`. The same injected touchscreen swipe then
opened the shade; swipe-up closed it, including after returning Home. A fresh
decode confirmed that only this initialization call changed from version 2;
all non-code/non-signature APK payloads matched exactly.

### Zero navigation dimensions

The base framework has `config_showNavigationBar=false`; a generated vendor
overlay sets it true. A navigation window was created in practice, but its
frame was `[0,800][1280,800]`: the frame's navigation dimensions were `0dp`.

A platform-signed, code-free dynamic overlay targeting `android`, package
`com.photoframe.systemui.navigation`, overrides these resources:

```xml
<resources>
    <dimen name="navigation_bar_height">48dp</dimen>
    <dimen name="navigation_bar_height_landscape">48dp</dimen>
    <dimen name="navigation_bar_width">48dp</dimen>
</resources>
```

The overlay uses `android:isStatic="false"`, priority 999, and SDK 28. Installed
in userdata and enabled for user 0, it produces frame `[0,752][1280,800]` and
visible Back, Home, Recents, and volume buttons. No framework APK was replaced.
Overlay persistence across reboot remains untested.

### Classic Recents works without installing Launcher3

The target's `config_recentsComponentName` names missing Launcher3 Quickstep.
However, this donor's `OverviewProxyService.updateEnabledState()` disables its
Quickstep connection and its classic Recents implementation explicitly launches
its own activity. The Recents button opened
`com.android.systemui/.recents.RecentsActivity` successfully. This behavior is
specific to the tested donor.

## Tested artifacts and rollback

These are local experiment identifiers, not downloadable releases:

| Artifact | SHA-256 |
| --- | --- |
| Guarded SystemUI v2 | `7319d280db861a0b528d736f947056916e7a4503ca271c44087d8d0aedd23e8d` |
| SystemUI v3, including touch fix | `c668c1a3319912ca59c555b18fae50dac1dd78fb6bde9ded9b1f05c8144ddd9a` |
| Navigation-dimension overlay | `5708920b79f5c4cb17951eb1b0d4de047d97fbc42fe2a09c401fdc305b4290ce` |

The v2 and v3 installed hashes matched independently. Back/Home/Recents passed
injected tap checks; shade and quick settings rendered; v3 pull-down and
swipe-up passed injected touchscreen checks. Physical confirmation after the
final touch fix is pending. Five pre-trial package/settings reference files
passed byte count, independent device hash, gzip readback, and filler checks.
Firmware backup limits are in the [device report](ave-105.md#backup-findings-and-limits).

The rollback plan recorded before installation is to remove the temporary
SystemUI exemption, stop/uninstall the userdata `com.android.systemui` package,
disable/uninstall `com.photoframe.systemui.navigation`, and return to the existing
launcher. To undo just v3, reinstall the independently verified saved v2 APK;
its original pull-down limitation returns. Never replace live package/settings
databases with reference snapshots. This uninstall rollback assumes SystemUI
was genuinely absent before the trial; check that on every unit.

## Memory pressure and persistence

Ordinary manual background starts were rejected, even when issued through root.
A temporary `deviceidle` exemption allowed startup:

```sh
# Only for the already installed, verified trial APK on the matching unit.
adb -s <frame-address>:5555 shell cmd deviceidle tempwhitelist -d 300000 com.android.systemui
adb -s <frame-address>:5555 shell am startservice --user 0 -n com.android.systemui/.SystemUIService
```

This exemption lasts five minutes. It neither establishes boot startup nor
protects the process from memory pressure. After an earlier exemption ended,
the bars remained, but `SystemUIService` was no longer listed.

Later, while Chrome was open, event logs showed many process deaths and repeated
low-memory events, including SystemUI. Chrome also had an input-dispatch ANR.
There was no new SystemUI Java exception in the crash buffer. The first manual
restart did not restore usable bars while pressure persisted. Closing Chrome
recovered available memory to about 675 MiB; the existing v3 process then rendered
both bars and reported the initialized scrim state. No APK or firmware changes
were needed for that restart. This supports memory pressure as the failure mode;
it does not establish the precise source of the memory consumption.

No persistent background exemption was applied, and no reboot test was done.
Background execution, process importance, automatic recovery, and a verified
recovery path need further work. Platform signing and battery exemptions alone
do not make a userdata app an Android persistent system process.

## Wallpaper restoration remains experimental

The frame retains declarations for `WallpaperManagerService`, its lifecycle,
and related classes, but base `bool/config_enableWallpaperService=false`.
`service check wallpaper` finds no Binder. WallpaperPicker, WallpaperCropper,
and WallpaperBackup are installed. The configured renderer is
`com.android.systemui/com.android.systemui.ImageWallpaper`, supplied by the donor
and protected by `BIND_WALLPAPER`.

The pinned Rockchip Android 9
[SystemServer](https://github.com/TinkerBoard-Android/rockchip-android-frameworks-base/blob/1c430aee6132d3c5c0e0260a4fa992ab2322dd24/services/java/com/android/server/SystemServer.java)
starts wallpaper only when that Boolean is true. Its
[WallpaperManagerService](https://github.com/TinkerBoard-Android/rockchip-android-frameworks-base/blob/1c430aee6132d3c5c0e0260a4fa992ab2322dd24/services/core/java/com/android/server/wallpaper/WallpaperManagerService.java)
publishes the Binder and binds the renderer. These sources support the
investigation; they are not the verified exact vendor source for this frame.

A separate code-free overlay, `com.photoframe.framework.wallpaper`, was built
and signature-verified with the single Boolean set true. It was **not installed
or enabled**. Its local SHA-256 is
`b17a0c4e8384028c50b6b29f2eb7feed3a03293727e10fc3893e01525c4b0758`.

Startup timing remains unresolved: the matching
[overlay manager](https://github.com/TinkerBoard-Android/rockchip-android-frameworks-base/blob/1c430aee6132d3c5c0e0260a4fa992ab2322dd24/services/core/java/com/android/server/om/OverlayManagerService.java)
initializes asynchronously, and SystemServer reads the wallpaper Boolean early.
An installed dynamic overlay may arrive too late. A static firmware overlay or
another early-boot change would need separate evaluation, authorization, and
verified backups before partition writes. Keep the absent-service guards until
actual startup and renderer binding have been verified.

## Building from source

A full source build was not attempted. The public
[Rockchip Android Pie manifest](https://github.com/TinkerBoard-Android/rockchip-android-manifest)
documents branch `p-rk3399pro`; its checked manifest had 705 projects. The pinned
[SystemUI build definition](https://github.com/TinkerBoard-Android/rockchip-android-frameworks-base/blob/1c430aee6132d3c5c0e0260a4fa992ab2322dd24/packages/SystemUI/Android.mk)
uses platform signing, privileged installation, and private framework APIs.
This is a platform module, not a normal standalone Android SDK app.

A Linux x86-64 host is the conventional source-build route. The build must use
the target's framework resource IDs for generated `com.android.internal.R`
constants and linker inputs. Building unchanged donor source against its own
framework would reproduce the ID mismatch. The vendor's exact AVE-105 source
tree and a public exact-model firmware download were not located in the searches
performed. No kernel, donor firmware, or replacement framework needs to be
flashed merely to test an adapted SystemUI APK.
