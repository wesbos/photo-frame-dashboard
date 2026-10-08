# Live Android access and Wi-Fi diagnostics

The owner successfully used the hidden manufacturer menu and enabled ADB. The device enumerated as Rockchip D156, USB 2207:0006, and ADB connected without an additional Android key prompt. This confirms the factory-app entry route on the running system. The installed package path is /system_ext/priv-app/Skylight/Skylight.apk.

ADB provides uid 2000 (shell). Android is a production user build; adb root explicitly refuses. SELinux reports permissive, but ordinary Unix permissions still prevent root-only module parameter writes. The build fingerprint is rockchip/D156/D156:12/AndroidS/skylightOS-D156-user-release-keys-20250311.212629:user/release-keys.

## Actual Wi-Fi hardware and startup

Live SDIO functions report 02D0:A9BF and bind to bcmsdh_sdmmc. The loaded module is bcmdhd. Driver logs read chip signature 4345, revision 9, and select AP6256-specific assets:

- fw_bcm43456c5_ag.bin
- nvram_ap6256.txt
- config.txt

Firmware and NVRAM load successfully, including NVRAM readback comparison. Firmware version is 7.45.96.125, dated 2022-01-20; driver version is 101.10.361.22, compiled 2025-03-11. The driver ignores the external CLM path and reports embedded CLM 9.2.9. The country mapping applies US/988 successfully.

These live observations supersede treating the generic device-tree ssv6x5x string as a hardware identification. The public FCC AP6256 photo is consistent with this runtime evidence, although the physical module label has not been inspected on this unit.

## Failure reproduced below the app

Wi-Fi is enabled and wlan0 exists. Android's native wificond repeatedly receives Scan aborted events; WifiNl80211Manager, WifiNative and WificondScannerImpl propagate scan failures. Kernel logs show LEGACY_SCAN requests. The roughly three-second repetition includes Android retry scheduling and is not proof of a three-second firmware timeout.

Opened Android's own Wi-Fi settings, enabled verbose Wi-Fi logging temporarily, and requested scans directly with cmd wifi start-scan. Results stayed empty. A Wi-Fi disable/enable cycle followed by another direct scan also returned no results. Verbose logging was restored to its previous disabled state afterward. No saved networks were removed or credentials changed.

This is stronger evidence than an empty app list: the scan operation is failing in the native/driver path. It does not yet identify an antenna fault, bad module, firmware incompatibility, regulatory issue, or a specific abort reason. Firmware loading success and lack of obvious SDIO timeouts do not establish that the radio is functioning correctly.

A locally built static iw utility captured a service-requested scan starting and aborting 1.107 seconds later. No intervening connection or channel event appeared in that capture. Direct frequency-limited scan requests from the shell fail with EPERM because the shell lacks network-administration capabilities; that permission failure is not radio evidence.

After moving the device upstairs and reconnecting, a further service-requested scan still returned no results. This observation alone does not distinguish the abort cause.

## Deeper tracing constraints

The installed kernel has CONFIG_DEBUG_FS disabled. Its bcmdhd dhd_console_ms module parameter exists but is writable only by root. Ordinary ADB cannot enable that trace. A temporary root recovery with the actual Broadcom assets was uploaded through fastboot boot. Fastboot acknowledged it but remained responsive in the bootloader; recovery did not start. A fastboot reboot returned normal Android with ADB still enabled. The normal boot and recovery kernel files are byte-identical (SHA-256 61f8ae942299bdfeed281bed05be6cd1062fadfc84053d380512bde713563266), so the diagnostic recovery retains the running kernel version. No replacement firmware has been installed.

Raw dmesg, logcat, dumpsys Wi-Fi and interface captures stay under ignored diagnostics/live-adb because they include unique identifiers and potentially nearby network details.

## Raw legacy recovery test outcome

The subsequently built legacy multi-image was sent unchanged with a guarded raw fastboot client. Download and boot were acknowledged, but recovery did not expose ADB. USB descriptors remained visible while both a bounded fastboot query and a raw libusb query timed out. This differs from the earlier Android-format attempts, which left a responding bootloader. The raw test may have progressed farther, but the exact failure stage is unknown. After disconnecting both USB and wall power, normal Android and ADB returned. The pstore directory was empty, so no crash log identified the failure. No firmware was flashed.
