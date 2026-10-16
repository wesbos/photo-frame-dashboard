# PF1007L May 2026: TF-card FEL to a standalone Home Assistant panel

Successful setup on 2026-10-12/13: a PF1007 with AiMOR and no working stock ADB
became a Home Assistant dashboard that starts automatically and retains its login
after a cold boot on the supplied wall adapter, without the Mac attached.

**The TF/microSD card entered FEL; it did not install a replacement Android ROM.**
This used [Route U](allwinner-a33-mainline-uboot.md): the Mac loaded U-Boot into
RAM, backed up eMMC through read-only USB mass storage, then applied a bounded
boot-ramdisk patch to enable the existing root USB ADB daemon.
This was **not** the SD-only Route S or a one-sector `build.prop` edit.

This is a separate unit from the
[earlier May macOS report](pf1007l-macos-20260529-report.md). The stock boot image
matched, but storage size, USB arrangement, and the successful RAM build differed.
These are observations, not permission to reuse this unit's offsets or payloads.
Start with the [current identification and safety checks](pf1007l-start-here.md).
No frame writes were performed to prepare this report.

## Tested identity and outcome

| Item | Observed |
| --- | --- |
| About model / Android model property | `PF1007` / `AEEZO` |
| Vendor firmware | `YHK.F-null-A33-1001-D1024-PF1007L-V10-1680.0.20260529` |
| AiMOR | `6.0.78` |
| SoC / OS / ABI | Allwinner A33, Android 6.0.1 / API 23, `armeabi-v7a` |
| Screen | 1280 x 800 landscape |
| Purchase reference | [Amazon ASIN B0GGB7LWX8](https://www.amazon.es/dp/B0GGB7LWX8); listing is not a board identity check |
| Stock USB | `1f3a:1000`, Android mass storage; no ADB device |
| Stock network ADB | TCP 5555 refused the tested connection |
| FEL | `1f3a:efe8`, `soc=00001667(A33)` |
| eMMC user area | 30,777,344 sectors of 512 bytes; 15,758,000,128 bytes |
| Original boot image | 15,886,336 bytes; SHA-256 `6c118dc1aa583797884c33cd3ac3796c72b2bd3a3f1fcafd1bf0982ae5f29e2c` |
| Result after boot patch | Persistent root USB ADB; `adb -d shell id` returned `uid=0(root)` |
| Final use | Fully Kiosk displaying the owner's Home Assistant dashboard after standalone cold boot |

The original firmware and its kernel remain installed. This is not an Android
upgrade or a supported, modern security baseline.

## TF-card approach

1. **Establish a working USB data path first.** A known-good USB-A-to-C data cable
   through a USB-C-to-A adapter directly into the Mac exposed the stock Android
   device. Dock/power arrangements had previously produced no enumeration or a
   stalled boot. Working power alone did not establish working data.
2. **Inspect and back up the card before changing it.** A 256 GB microSD card
   already had an MBR and a FAT32 partition starting at sector 16384. Its boot gap
   could hold the FEL stub, so formatting was not needed for the initial write.
   The first 4 MiB were backed up twice and the compressed backup read back.
3. **Write only the verified FEL stub into the boot gap.** With owner approval,
   the guarded card tool wrote the official 8192-byte `fel-sdboot.sunxi` at
   **byte offset 8192**, then verified the bytes and ejected the card.
   Sector 8192 and byte 8192 are not interchangeable.
4. **Insert the card into the unpowered frame and reconnect USB.** A dark display
   was expected. USB enumeration and `sunxi-fel` identified FEL and A33; a black
   screen was not treated as evidence of failure.
5. **Load the reviewed read-only U-Boot build into RAM from the Mac.** The card
   caused entry into FEL; it was not providing a running Android installation.
   U-Boot exposed storage through read-only USB mass storage (UMS).
6. **Back up, patch, and independently verify before normal boot.** After those
   stages succeeded, remove the FEL card and cold-boot Android to test root ADB.
   Leaving the card inserted sends the frame back into FEL instead.

The owner later reformatted/renamed the same card. The FEL stub remained present,
but surrounding bytes changed. The old prefix backup was therefore no longer a
safe blind restoration of the reformatted card. No second stub write was needed.

This 256 GB card worked for **FEL entry** on this unit. It does not establish that
large cards work with Route S's filesystem-based scripts or justify weakening
the card tool's layout checks.

## USB reliability and the RAM build that completed the backup

The macOS START STOP correction and null console were retained from the
[earlier report](pf1007l-macos-20260529-report.md#ums-disappeared-after-about-30-seconds).
They were not sufficient by themselves: the initial 1008 MHz build remained
visible while idle but disappeared during reads. A 408 MHz/no-PMIC build still
reset during reads. Adding the 4-bit, 26 MHz eMMC overlay to that lower-power
build allowed the complete backup.

| Setting | Successful local build |
| --- | --- |
| U-Boot | v2025.10, commit `e50b1e8715011def8aff1588081a2649a2c6cd47` |
| DRAM clock / ZQ | 456 MHz / 15291 |
| CPU | `CONFIG_SYS_CLK_FREQ=408000000` |
| PMIC | `CONFIG_SUNXI_NO_PMIC=y`; `CONFIG_AXP221_POWER` disabled |
| Console | `CONFIG_SYS_DEVICE_NULLDEV=y`; guarded null input |
| eMMC overlay | 4-bit bus, maximum 26,000,000 Hz; board overlay includes `sunxi-u-boot.dtsi` |
| Host UMS writes | Refused by write callback; LUN initially read-only |

These were local diagnostic build changes, not proof that all PF1007L units need
these settings or that the repository's default build produces this variant.
Inspect the actual generated configuration: enabling no-PMIC without disabling
AXP221 first was insufficient because Kconfig selected AXP221 again.

Post-patch full verification also disconnected twice, without reporting a byte
mismatch. **The flash operation was not repeated.** Moving the adapter to a
different direct Mac USB-C port, then reloading read-only U-Boot, allowed full
verification to finish. The electrical cause was not measured; the evidence does
not isolate CPU clock, MMC speed, power, or port as a universal fix.

## Backup and boot-patch verification

The Mac lacked space for the raw backup, so ignored backup storage was linked to
an external SSD. All 15 resumable segments of the eMMC user area were independently
reread and compared, with exact-length, SHA-256, filler, and gzip readback checks.
Environment, boot, and recovery were also independently compared before flashing.
This captures the **eMMC user area**, not separate hardware boot areas or RPMB.

The boot patch changed the stock `mass_storage` action in `init.sun8i.usb.rc` to
activate `mass_storage,adb` and start `adbd`. It used payloads derived from this
unit's verified backup. The local apply/restore scripts gated preflight reads,
CRCs, comparisons, writes, and readbacks, with the boot header written last.
The header spanned two sectors because the Android image ID extends beyond byte
511. Host failure-injection checks supplemented, but did not replace, readback.

After writing, **the entire eMMC user area matched the original backup plus
exactly the approved boot patch**. The owner then removed the card and cold-booted
Android offline; root USB ADB worked. Recovery payloads and the working RAM build
were kept privately on the SSD. Do not publish userdata dumps or whole-device
hashes, and do not copy a patch from a matching-looking frame.

## Working standalone dashboard

After root, the owner approved these separate changes:

- Installed Rootless Launcher 3.9.1 as a maintenance fallback and Fully Kiosk
  Browser 1.61.4. APK identity, API compatibility, and Android signatures were
  checked before installation.
- Disabled `com.efercro.os.aimor`, `com.yhk.qeota`, and `com.DeviceTest`.
  Their disabled state was checked in Package Manager's on-disk XML before
  reboot, then checked again afterward. Wi-Fi stayed off during this stage.
- Replaced WebView 44 with the pinned ARM WebView 106.0.5249.126, including
  **all three native libraries**, while preserving the whole stock tree for
  rollback. See the [WebView procedure](allwinner-a33-pf1007l.md#6-upgrade-webview-before-using-the-kiosk).
- Corrected an initial 1970 clock and added verified official ISRG Root X1/X2
  certificates after observing a missing trust-anchor error.
- Configured Fully for fullscreen, keep-screen-on, network-reconnect reload,
  page-error retry, and retained cookies/web storage. The owner entered the
  dedicated dashboard account credentials directly on the frame.

Fully's launch-on-boot setting did not start the app on this firmware; the
observed boot-completed broadcast did not list Fully among its recipients.
A small, locally built, no-permissions **Panel Home** app was selected as Android's
default Home. It launches Fully for Home intents and exposes dashboard, Rootless,
and Android Settings buttons when opened as a normal launcher app. Its source,
signed APK, and recovery records were saved privately; **that helper is not
included in this report**, so installing Fully alone does not reproduce this
unit's automatic startup.

The owner confirmed that the dashboard opened automatically and stayed signed in
after removing USB power and restarting on the wall adapter without the Mac.
Remote administration, camera/microphone features, the device JavaScript bridge,
and paid kiosk lockdown were not enabled as part of this setup.

**Security exception:** the owner chose to retain Fully's "Ignore SSL Errors"
setting even after installing the trust roots. Successful rendering does not
establish valid certificate verification in that configuration. Do not copy that
exception as a solution to HTTPS errors. WebView 106 and Android 6 are old, and
root USB ADB on this unit does not require an authorization prompt.

## Boot appearance and limitations

The owner subsequently supplied a 1280 x 800 image. It was converted to the two
native portrait logo formats described in the
[boot-screen guide](allwinner-a33-boot-screens.md): a 3,072,054-byte 24-bit BMP and
4,096,000-byte raw BGRA `initlogo.rle`. The bootloader filesystem claimed 128 MiB
despite the physical partition being 32 MiB. Its existing BMP was overwritten
**in place at unchanged size**, after independent partition backups and FAT-chain
checks. Full readback found only the intended logo bytes and file timestamps
changed; allocation and FAT tables were unchanged.

`debug.sf.nobootanimation=1` in `/system/build.prop` suppressed the animation
without deleting the stock ZIP. The property was checked after reboot; the owner
confirmed upright artwork, no animation, and automatic dashboard startup.
Original files were retained and `/system` was remounted read-only.

Android reported no camera devices or proximity sensor. The accelerometer
reported readings, but that detects movement of the frame, not people walking
past it. Light and temperature sensors were listed but not functionally validated.
No installed `com.android.systemui` package was found; normal phone-style
navigation bars and modern gesture navigation should not be assumed available.

Keep individual configuration, credentials, signing material, and backups private.
These observations establish success on this unit, not compatibility for every
frame sold under the same listing.

## Recovery references

The owner retained device-specific guarded apply/restore payloads and the verified
original backup. Restoring the boot patch requires those original payloads and
the same target-identity, current-state, and readback checks; this report does not
provide a generic flash command. Remove the FEL card to return to normal Android
boot without changing flash.

For post-root changes, restore the original whole WebView tree using the
[WebView rollback procedure](allwinner-a33-pf1007l.md#6-upgrade-webview-before-using-the-kiosk)
and restore the original logo files following the
[boot-screen undo procedure](allwinner-a33-boot-screens.md#8-undo).
Restore the saved original `build.prop` to remove this setup's animation override,
verifying the restored bytes and remounting `/system` read-only before reboot.
Select Rootless as Home to stop using the local launcher bridge without removing
the working fallback. Re-enabling AiMOR would also restore its vendor connection;
it is not required to regain Android Settings or a usable home screen.
