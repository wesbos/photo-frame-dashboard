# Skylight 150-CAL hardware and diagnostic research

Research date: 2026-09-14. This document distinguishes public reference hardware from the particular calendar being investigated. It contains no device-specific serial numbers, addresses, or account details.

## Hardware identification

The original 2022 certification is **FCC ID 2AABK-150**, filed by Shenzhen Chuangwei Electronic Appliance Tech Co., Ltd. (Skyworth). Its calendar manual is titled `D156-IM-A1` and describes the Skylight Calendar. The 2024 Glimpse filing `2BF8S-150` is a change of identification from that device. There is also a separate `2BF8S-150-1` family; model name alone is insufficient to establish board revision.

Sources: [original certification](https://fccid.io/2AABK-150), [D156 calendar manual](https://fccid.io/2AABK-150/User-Manual/User-Manual-CAL-6074303.pdf), [Glimpse certification](https://fccid.io/2BF8S-150).

The manufacturer's [2022 internal photographs](https://fccid.io/2AABK-150/Internal-Photos/Internal-Photos-6074299.pdf) show:

| Observation | Confidence and limitation |
| --- | --- |
| Mainboard silkscreen `D156-MB-D6-V02` | High, legible in photo; not proof of the investigated unit's revision. |
| AMPAK `AP6256` Wi-Fi module | High, module shield marking visible in first-page board photo. |
| Three exposed gold pads along a board edge | High that pads exist; their functions and ordering remain unverified. |
| Three physical keys marked volume down, power, volume up | High, separate key flex shown on PDF page 3. |
| External antenna connection near radio module | Visible physical lead; exact connector series and continuity require physical inspection. |

Downloaded originals and extracted photographs are stored locally under ignored `diagnostics/hardware-research/fcc-2022/`. `front-001.png` shows the populated board with shield fitted; `original-001.png` shows the shield removed. Do not infer UART wiring from an unreadable photograph.

## UART: evidence from the installed bootloader

The calendar's backed-up U-Boot contains the compiled default `baudrate=1500000`. Its U-Boot DTB selects UART2 at `0xfe660000` as `stdout-path`; see [offline boot analysis](boot-analysis.md). Both Android boot DTBs also enable `fiq-debugger` with `rockchip,serial-id = 2` and `rockchip,baudrate = 0x16e360` (1,500,000). A historical recovery kernel log records `ttyFIQ0` console registration. These establish software configuration and historical console initialization, not a live UART measurement. Electrical levels, pad order, and a live UART capture remain unverified.

Rockchip's own [Android RK3568 device-tree source](https://raw.githubusercontent.com/rockchip-linux/kernel/develop-4.19/arch/arm64/boot/dts/rockchip/rk3568-android.dtsi) also configures `console=ttyFIQ0`, UART2 mode 0, and **1,500,000 baud**. The calendar's own Android DTBs provide stronger evidence for its serial index and baud than this reference source; physical pad routing still needs verification.

[Firefly's RK3568 serial documentation](https://wiki.t-firefly.com/zh_CN/ROC-RK3568-PC/debug.html) specifies 1,500,000 baud, 8 data bits, 1 stop bit, no parity, and no flow control. It reports that some CH340 adapters cannot reliably achieve this rate and some PL2303 variants cannot reach it; verify the exact adapter rather than trusting a broad chip-family label. This is a plausible explanation for a previous unsuccessful UART attempt, not a diagnosis.

For a physical retry, first identify board ground and measure the idle TX voltage, then attach only adapter ground and adapter RX for a passive boot capture. Use a TTL adapter with matching logic levels; do not connect its power output or assume RS-232 voltage levels are suitable. Add adapter TX only after the pins and voltage are established. A boot log does not by itself guarantee an interactive shell: FIQ console output and Android shell services are distinct.

## Wi-Fi implementation and failure discrimination

### What the verified backup establishes

The extracted U-Boot DTB uses the generic `Rockchip RK3568 Evaluation Board` model string. It includes enabled MMC controllers at `0xfe2b0000` and `0xfe2c0000`, but contains no Wi-Fi, Bluetooth, radio-module or AP6256 identification. A configured host controller does not prove that a radio is connected or working. U-Boot may omit Android-only devices, so these omissions do not establish a missing or disabled radio either.

The complete backup supersedes the earlier first-32-MiB investigation. Both Android boot DTBs identify `Rockchip RK3566 g10 Board`, compatible with `rockchip,g10` and `rockchip,rk3566`, and configure `wifi_chip_type = "ssv6x5x"`. These are the calendar's own software configuration, unlike the generic U-Boot board name. The DTB string is not reliable radio identification: subsequent live ADB evidence identifies Broadcom hardware and AP6256 firmware selection, as described below.

The backed-up cache partition also contains `recovery/last_kmsg`. It records `Machine model: Rockchip RK3566 g10 Board`, the WLAN platform driver parsing `wifi_chip_type = ssv6x5x`, and `mmc1: new ultra high speed SDR104 SDIO card at address 0001`. During this boot the RTC sets the device clock to 2026-02-27. Thus the board configuration and SDIO enumeration are supported by a historical runtime log, not only static device trees. Enumeration does not prove successful radio firmware initialization, scans, or RF reception, and this historical boot does not establish the present fault.

The `super` and `cache` source partitions used for the earlier provisional extractions have been byte-compared against the validated full backup and match exactly. Local evidence remains in ignored `diagnostics/provisional-images/boot-dtb.txt`, `boot-dtb-1.txt`, and `cache-files/recovery/last_kmsg`; the directory's historical name does not imply that these compared sources are still unverified. Live ADB diagnostics have since supplied current-session radio and scan evidence.

### Live radio identification and scan failures

Live ADB captures identify SDIO `02D0:A9BF`, bound driver `bcmsdh_sdmmc`, module `bcmdhd`, and chip `0x4345` revision 9. The driver selects `fw_bcm43456c5_ag.bin` and `nvram_ap6256.txt`; its log reports successful NVRAM download/upload comparison and firmware startup. This is stronger evidence than the misleading `ssv6x5x` platform-DTB string. The software selection and chip identity fit the AP6256 reference module; its physical shield marking has not been inspected on this unit.

Android wificond repeatedly receives scan-aborted events, including while native settings is open. The captured failure is below Skylight's list rendering. Repeated events roughly 3.14 seconds apart include framework-delayed retries; that interval is not evidence of a three-second driver timeout. Initial scans fail roughly 1.2 seconds after initiation. No captured SDIO timeout or firmware crash establishes a cause. Firmware startup success does not prove scan-engine or RF health. Raw captures remain under ignored `diagnostics/live-adb/`.

The [Rockchip driver source](https://github.com/rockchip-linux/kernel/blob/develop-4.19/drivers/net/wireless/rockchip_wlan/rkwifi/bcmdhd/wl_cfg80211.c) maps multiple firmware status values to an aborted scan. Its optional debugfs control accepts `SCAN:1 DBG:1`, potentially exposing the hidden abort reason. Exact installed-source equivalence and debugfs availability remain unverified. Capture and restore the prior logging flags around one controlled scan. A reversible Wi-Fi off/on cycle and, if a privileged tool is available, single-channel passive scans can distinguish a stuck state or channel-specific failure. Existing logs do not justify replacing firmware or diagnosing an antenna fault.

### Regulatory reporting and the shell permission boundary

A locally built static `iw` 6.9 successfully reads the live interface and radio capabilities. It reports a global world domain (`00`) alongside a **self-managed** PHY domain (`US`). This coexistence is not itself evidence of misconfiguration: Linux documents that self-managed PHYs use their driver/firmware regulatory information independently of global hints. [Linux 4.19 regulatory definitions](https://github.com/torvalds/linux/blob/v4.19/include/net/regulatory.h).

The PHY advertises unusually broad ranges and lists channels 1–14 plus numerous 5-GHz channels without disabled/DFS flags. The referenced Rockchip driver also contains broad custom regulatory ranges similar to those advertised. This is evidence about the driver's reported table, not proof that firmware accepts every listed channel or that a country setting causes the scan aborts. The driver separately reports successful `US/988` selection. A missing core `regulatory.db` message does not establish failure of this self-managed radio.

A passive single-channel `iw` scan attempt returns `EPERM`. The ADB shell has UID 2000 and no effective Linux capabilities; this is an access failure, not a completed radio test. Raw netlink scan initiation requires privileges, whereas Android's Wi-Fi service can accept authorized shell commands and perform the operation through its own privileged components. Read-only `iw` getters do not imply permission to trigger scans. Keep channel-specific testing pending until an appropriate privileged path is available; do not interpret `EPERM` as a regulatory rejection.

Non-root follow-up can record `iw event -t` while requesting one scan through `cmd wifi start-scan`, if multicast event subscription is allowed, and correlate native events with logcat/kernel timestamps. This may expose overlapping connection or channel events, but need not reveal the firmware's private abort reason. Temporary verbose logging and an ordinary Wi-Fi toggle through Android are reversible service-mediated tests. No confirmed additional non-root route to driver debug controls was identified.

### Reference-module context and diagnostic plan

AMPAK documents the reference photograph's AP6256 as a dual-band Wi-Fi module using **SDIO for WLAN and UART for Bluetooth**. The live driver now independently selects AP6256 firmware, despite the platform DTB's `ssv6x5x` string. Its current page lists newer Bluetooth capabilities, so do not apply those retroactively to the 2022 module. Sources: [AMPAK AP6256](https://www.ampak.com.tw/cn/product/WiFi-Bluetooth/stamp-type-1T1R/AP6256), [AMPAK chipset mapping](https://www.ampak.com.tw/about/StrategicPartnershipWithSynaptics).

A [Firefly AP6256 hardware-debugging thread](https://forum.t-firefly.com/t/topic/11207) records working SDIO functions with vendor/device `02D0:A9BF` and driver `bcmsdh_sdmmc`. A board with no SDIO functions required circuit investigation. This is useful comparison evidence, not proof of the same fault in a Skylight.

Once a shell exists, collect these read-only observations before changing Wi-Fi configuration:

```sh
getprop ro.build.fingerprint
getprop wifi.interface
getprop wlan.driver.status
ls -l /sys/bus/sdio/devices
cat /sys/bus/sdio/devices/*/uevent
ip link
dumpsys wifi
logcat -b all -d
dmesg
cmd wifi help
```

Some commands require privileges or may not exist in this firmware. Logs and `dumpsys wifi` can contain saved network names and other private information; keep raw captures in ignored diagnostics. After checking the available `cmd wifi` subcommands, a controlled scan can distinguish Android/app presentation from radio failure. Capture logs during that scan rather than repeatedly resetting the entire unit.

| Result | Working hypothesis / next check |
| --- | --- |
| No SDIO radio device | Power/reset/clock, SDIO path, device-tree setup, or module failure; not merely an antenna issue. |
| SDIO present, firmware download or calibration errors | Identify the bound driver and inspect its selected firmware paths and calibration configuration. Preserve existing calibration files. |
| WLAN interface exists, driver repeatedly times out during scan | Driver/firmware or radio/power fault; correlate kernel errors with scan timestamps. |
| Android sees access points, Skylight onboarding list stays empty | App permissions, location/scan state, filtering, or UI issue. |
| Scans only work beside the access point | Inspect antenna/coax/connector and RF path; compare both bands. |

Prioritize the runtime-selected Broadcom driver, `fw_bcm43456c5_ag.bin`, and `nvram_ap6256.txt` in this calendar's extracted vendor files; the DTB's `ssv6x5x` label does not select the live radio driver. Determine actual selected paths from its own init scripts, configuration and runtime logs. Do not replace firmware or calibration based on the public AP6256 photograph or another board's files.

## Software access findings

The [Calendar Max ADB walkthrough](https://github.com/dinewby88/SkylightMaxCalendarADB) depends on repeatedly opening the power menu and swiping until System UI crashes, then using App Info to reach settings. It is not a documented 150-CAL service mode. The attempted gesture did not expose settings on this unit. No verified alternative 150-CAL onboarding bypass or public full firmware recovery image was located in this bounded search.

Subsequent offline analysis of the factory APK, whose source partition now matches the validated full backup, identified an actual onboarding manufacturer-menu route with ADB and native-settings controls. That route has now enabled live ADB access as UID 2000 and native-settings access. See [application analysis](app-analysis.md) for the five-tap touch target and implementation evidence. It enables debugging access, not a root shell.

Skylight's [15-inch technical specification](https://skylight.zendesk.com/hc/en-us/articles/36052993626651-Technical-Specifications-for-15-Calendar) describes USB as a manufacturing port. That is consistent with pursuing Rockchip's maintenance interface, but does not specify a supported consumer recovery procedure.

The complete backup and live ADB captures establish the installed software, functioning SDIO communication, firmware startup, and native scan aborts. The next useful evidence is the precise abort status or a privileged controlled scan. Hardware repair remains a possibility; neither the empty onboarding list nor the current abort logs establish whether a radio hardware fault or driver/firmware behavior is responsible.
