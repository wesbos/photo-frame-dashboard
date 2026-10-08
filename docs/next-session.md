## Latest: persistent USB Wi-Fi works on Android 12 (2026-09-21)

Persistence is now installed and reboot-verified. Current boot SHA-256 is `a97c648870c3fd377fe23680367857e3478d81825665e899d56349450f9cfd8e`. It changes the debug ramdisk property `ro.boot.init_rc` to `/metadata/skylight-wifi/init.rc`; this wrapper preserves stock init imports and starts `/metadata/skylight-wifi/start.sh` after Android boot completion. The script loads `/data/local/skylight-wifi/8188eu.ko`, forces host mode, renames inactive Broadcom interfaces, selects USB `wlan0` and enables saved-network Wi-Fi plus authenticated network ADB. A normal reboot reconnected automatically, Ethernet remained unplugged, Android validated Wi-Fi as default, and an external bound ping passed 3/3. Explicit `adb root` still works.

Rollback is the verified previous debug boot (`f6e2c27c89a3db7835089fa8037909dc5e7eb62745eb90471fabab58b49821b3`), saved on device at `/data/local/skylight-wifi/boot-before-wifi.img` and on the Mac at `diagnostics/debug-boot-candidate/boot.img`. Restore it before deleting the metadata startup files, wiping metadata or factory-resetting. For USB ADB recovery, boot with the normal Mac USB cable connected instead of the hub; the script detects a computer and leaves peripheral mode. This fallback is implemented but not yet physically tested. Do not connect the Mac while forced host mode is active. A root-owned `/metadata/skylight-wifi/disabled` flag disables startup on subsequent boots.

Owner's objective remains Android 12 now, Android 14 in a future phase. See `docs/usb-wifi-dongle.md` for full installation, readback, reboot evidence and recovery details.

### Earlier runtime bring-up (superseded by persistence above)

RTL8188EU `0bda:8179` enumerates and connects through Android's normal Wi-Fi stack. The adapter chain required forcing `/sys/devices/platform/fe8a0000.usb2-phy/otg_mode` to `host`. The prepared `/data/local/tmp/skylight-8188eu.ko` loaded, Broadcom interfaces were temporarily renamed `onboard0`/`onboard1`, USB `wlan2` became `wlan0`, and restarting the Wi-Fi HAL with Wi-Fi enabled connected using saved credentials. Android WIFI validation and an external ping bound to `wlan0` passed. Network ADB is available on port 5555; local addresses are in ignored diagnostics. No persistent Wi-Fi setup exists yet. Host-test timers were canceled to keep this working session alive.

Keep the hub/dongle and wall power connected. Before reconnecting a Mac USB cable, restore automatic `otg` via network ADB or reboot; reboot also loses the temporary module/interface changes. Owner wants Android 12 working first and Android 14 in a future phase. See `docs/usb-wifi-dongle.md` for details and outstanding reboot persistence work.

## Previous state: Android with persistent ADB-root capability; stock radio firmware

The debug boot image is now successfully installed through Rockusb, fully read back, and independently SHA-verified. Android boots normally, including a subsequent ordinary reboot. ro.debuggable=1 persists; ADB starts as normal shell UID2000 after reboot and adb root explicitly enables UID0. Current boot SHA256 f6e2c27c89a3db7835089fa8037909dc5e7eb62745eb90471fabab58b49821b3. Stock restore image remains verified in backups/extracted/boot.img. No unlock, erase or userdata change was performed.

Newer Wi-Fi firmware .203 was actually tested via temporary bind mount, but broad scans still aborted and found no networks. It was removed. After normal reboot, stock .125 firmware and console logging0 are confirmed, sys.boot_completed=1, Lawnchairhome restored, and USB internet passed HTTP204. Framework scanning had been reenabled before reboot. No runtime firmware mount persists. A runtime bcmdhd unload/reload failed SDIO initialization; reboot recovered it. Do not repeat that reload method without new evidence. Full results docs/native-wifi-root-tests.md; owner asked to enable a nearby2.4GHz phone hotspot for a controlled detection test, answer pending. Main objective remains a general Android display, Skylight optional.

## Diagnostic boot test completed; stock Android restored

Owner explicitly approved the diagnostic boot test. `fastboot flash boot` reported a successful write (host label boot_a), but the candidate reboot returned to fastboot and never exposed Android ADB. The exact backed-up original boot image was then flashed successfully. Android now reports sys.boot_completed=1 and ro.debuggable=0, Lawnchair is the default home, Skylight USB Test remains installed, and restored gnirehtet internet passed a real HTTP204 probe. No Wi-Fi radio firmware, vbmeta, userdata, or unlock state was intentionally changed. The candidate did not establish root access.

The stock restoration reboot returned a USB status-read error while the device disconnected; subsequent successful Android boot is the stronger outcome. Pstore contains the old Android session ending with the requested reboot-to-bootloader, not a diagnostic-image crash. The failure stage remains unknown. Raw flash/restore logs and pstore stay in diagnostics/debug-boot-test. Do not repeat speculative boot-image changes without new evidence. Earlier statements that no firmware was ever flashed are historical: this test wrote boot and then restored stock.

## Owner priority: general Android display

Owner clarified that making the Android device itself usable is the primary objective; Skylight app use is optional. Android 12 boots, touch/display work, Lawnchair is the default HOME activity, and USB reverse tethering works. Native Wi-Fi is the unresolved blocker to standalone wireless use. Prefer diagnostics of the existing driver/radio over replacing Android wholesale. A GSI retaining vendor/kernel may preserve the same failure. See wifi-firmware-candidate.md for the newly identified AP6256 .203 firmware comparison; not installed.

## Latest result: Wi-Fi onboarding bypassed

Skylight USB Test (`com.skylight.usbtest`) is installed alongside the factory app and currently displays activation-code entry over USB internet. The owner confirmed successful activation and adding it in the mobile app. Full calendar behavior remains under observation. A subsequent official update-metadata check returned HTTP 403; no new version was downloaded. See [the patch and removal instructions](onboarding-network-gate.md#successful-separate-app-bypass-2026-09-14). No firmware was flashed.

# Resume from the current state

The owner fully disconnected wall power and USB after the raw legacy RAM test hung. **Normal Android is running again, ADB works, and sys.boot_completed is 1.** No transfer remains active. The full backup is validated; no firmware was flashed.

The post-reset pstore directory is empty, so no crash log identifies the temporary boot failure. Further boot debugging needs a serial boot log rather than another speculative image. Existing native Wi-Fi evidence is preserved, but the underlying radio failure remains unresolved.

## Working network workaround

Gnirehtet USB reverse tethering is running on the Mac and the calendar has verified external HTTP access. See [restart/stop instructions](usb-internet-sharing.md). Do not start a second relay on the same port. Wi-Fi radio and Skylight onboarding acceptance are separate questions.

## Current findings

- The hidden manufacturer menu successfully enabled ADB and opened native settings. See [app analysis](app-analysis.md); local owner instructions are in diagnostics/app-analysis/owner-menu-notes.md.
- Running hardware uses bcmdhd and AP6256 firmware, superseding the generic ssv6x5x device-tree label. Firmware/NVRAM initialization succeeds.
- Native scans abort about 1.1 seconds after starting, including requests outside Skylight. Wi-Fi cycling did not resolve it. See [live diagnostics](live-diagnostics.md).
- ADB is shell uid 2000. adb root is refused. SELinux permissive does not remove Unix permission checks. The static iw utility at /data/local/tmp/skylight-iw can read radio information/events, but cannot issue privileged scan commands.

## Temporary recovery work

`adb reboot bootloader` reaches approved fastboot. A bounded `fastboot getvar max-download-size` reports 0x04000000. Avoid getvar all: its snapshot-status query stalled this bootloader once.

The AP6256 Android-format candidate backups/diagnostic-recovery-ap6256/recovery.img is 57,397,248 bytes, SHA-256 e88e7e4a7a37a84cb898ae2b4cb4f4ed9d515ccb4a5a46aad1302347a0db731e. fastboot boot acknowledged the upload and boot command, but recovery did not start and fastboot remained responsive. fastboot reboot returned normal Android. Do not mistake OKAY for a running recovery.

The earlier compact SSV candidate is unsuitable for diagnosing this actual Broadcom radio. The original full recovery candidate exceeds the download limit. A legacy multi-image alternative was built and checked. Standard fastboot boot auto-wraps it in an Android header, so that attempt did not test the intended format. The reviewed raw uploader then sent the exact candidate and received download/boot acknowledgements, but subsequent fastboot and raw libusb queries timed out. Recovery never exposed ADB. The failure stage is unknown; do not repeat or build another candidate without more evidence. Inspect the latest RAM boot notes. No flash/unlock/erase commands are required for the intended RAM tests.

## Preserved results

- backups/full-flash.img.gz: 15,636,365,312 raw bytes compressed to 1,283,729,666 bytes, gzip readback and SHA-256 verified.
- backups/extracted/: validated boot, recovery, super and cache; GPT and independent sample comparisons passed.
- Original first 32 MiB and low partitions are also preserved. INCOMPLETE-CC files are invalid reads, never restoration sources.
- Private captures and firmware stay under ignored diagnostics/ and backups/. Public notes omit unique identifiers.

Loader/MaskROM recovery methods remain documented in [loader research](loader-research.md). Normal ADB now provides the simpler route to fastboot.
