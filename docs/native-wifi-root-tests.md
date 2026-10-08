# Native Wi-Fi root tests

## Root access established

Direct Rockusb write/readback of the verified debug boot image succeeded; Android reported ro.debuggable=1 and adb root returned UID0. Live /dev/block/by-name/boot SHA256 exactly matched the candidate. See debug-ramdisk-research.md. Both fastboot-written debug and recompression-only control images had returned to fastboot, while stock restorations booted; the reason for that path difference remains unresolved.

## Radio firmware comparison

Stock .125 and newer Orange Pi .203 both initialized with the original NVRAM/config/country settings. The .203 test used a temporary bind mount over /vendor/etc/firmware/fw_bcm43456c5_ag.bin, visible in init's mount namespace; the vendor partition itself was not overwritten. info_string confirmed .203 was actually loaded. A broad manual scan with Android framework scanning disabled still aborted in about 1.11 seconds and found no networks. This rules out interpreting every observed abort as overlap with framework scanning. The candidate did not repair discovery and was unmounted; .125 was verified reloaded.

Single-channel and limited passive scans can finish with zero BSS results. With .203 and framework scanning disabled, channels1–11 completed in about0.91s; channel36 completed in about2.40s. Earlier limited stock5GHz tests overlapped with framework activity and are not a clean before/after comparison. An iw scan command can exit0 even when its event says aborted, so use the captured event status rather than exit code alone. Raw network output remains private under diagnostics/wifi-root.

Root command cmd wifi enable-scanning disabled was used temporarily to prevent overlapping Android scans. It was restored to enabled before reboot. No saved networks were deleted or joined. A nearby phone hotspot in2.4GHz compatibility mode was requested from the owner for a controlled detection test; no credentials are needed.

## Driver logging attempt and cleanup

Changing dhd_console_ms to200 did not expose a useful abort cause; its previous value0 was restored. A subsequent normal rmmod/insmod of the exact stock bcmdhd.ko with wl_dbg_level=15 and explicit stock firmware paths failed SDIO reinitialization (power-up retries, exit err=-19). Module-list presence and shell command exit were insufficient to establish usable Wi-Fi. Do not repeat a runtime module reload as if it were proven supported. Normal reboot was requested to restore the usual initialization sequence. No persistent driver or radio firmware replacement was made.

Normal reboot completed successfully: boot_completed1, ro.debuggable1 persists, ADB defaults to UID2000, stock .125 radio firmware initialized, dhd_console_ms0, Lawnchairhome and real USB HTTP204 verified. The runtime mount and debug module parameters are gone. Root remains available on explicit adb root.

## Nearby phone hotspot attempt

Owner enabled a phone hotspot and supplied its name/password. Password was used only to submit a normal Android connection request, not copied into public notes or command-result logs. With framework scanning paused, stock firmware passive and active scans over channels1–11 both finished in about0.91s but returned zeroBSS. Common5GHz channels also returned noBSS. Framework scanning was reenabled. A directed hidden-network WPA2 connection request was accepted by Android but did not connect; sampled logs showed further scan aborts and no authentication/association rejection. This does not establish that the password was rejected. Owner confirmation of Maximize Compatibility and keeping PersonalHotspot settings visible was requested before finalizing the strong-signal result.

Owner confirmed hotspot compatibility mode enabled. Repeated passive and directedSSID scans across channels1–11 both completed normally in about0.90s with zeroBSS results. A previously pending broad Android scan aborted, but the two controlled scans each emitted scan-finished events. Normal framework scanning was restored; Wi-Fi remains enabled and disconnected. This strengthens suspicion of a radio receive/antenna/board fault or low-level radio configuration issue, but the hotspot was not independently observed with a second receiver and physical hardware failure is not proven. No password-authentication failure was observed.

## Firmware radio counters (2026-09-19)

`scripts/wlprobe.c` is a small static, read-only probe that issues Broadcom WLC get-ioctls through bcmdhd's SIOCDEVPRIVATE entry, like the `wl` utility. Built with the same Zig toolchain as static iw; device copy at /data/local/tmp/skylight-wlprobe; requires adb root. The firmware answered `WLC_GET_MAGIC` with 0x14e46c77 and returned counters version 10; offsets were checked against `wl_cnt_ver_11_t` and `wl_cnt_ver_6_t` in Rockchip's bcmdhd wlioctl.h, which share the relevant prefix.

About 15 minutes after boot, with framework scanning paused, counters were captured before and after one active and one passive full scan (both zero BSS):

| Counter | Since boot | Active scan Δ | Passive scan Δ | Meaning |
| --- | --- | --- | --- | --- |
| rxstrt | 0 | 0 | 0 | PHY receive starts (any detected preamble) |
| rxframe, rxbadplcp, rxbeaconobss | 0 | 0 | 0 | Received frames, bad PLCP, other-BSS beacons |
| rxcrsglitch | 59 | 0 | 0 | Energy without valid preamble |
| txphyerr | 6053 | +391 | 0 | Transmit PHY errors in tx status |
| txallfrm | 39 | +2 | +1 | Frames actually sent by MAC |
| reset | 84 | +3 | +3 | Firmware wlc core resets |

A working radio in an inhabited area accumulates rxstrt continuously. Zero receive starts since boot, near-zero CRS glitches, thousands of transmit PHY errors and core resets during every scan indicate the radio PHY neither receives nor transmits. The resets during each scan plausibly explain the ~1.1 s "scan aborted" events. A merely disconnected antenna would usually still show some receive activity and would not typically produce transmit PHY errors.

Board configuration checks in the same session: the RK809 32.768 kHz output feeding sdio-pwrseq is enabled (register 0xF2 = 0xA0, CLK32KOUT2_EN set); sdio-pwrseq reset GPIO and PMIC clock phandles resolve to the expected nodes; related regulators report enabled at nominal setpoints (software-reported, not measured). The DTB's `wireless-bluetooth` node is disabled and `android.hardware.bluetooth` is not declared, so the module's Bluetooth half cannot be used as a comparison receiver without further work.

Conclusion: strong evidence for a hardware fault in the AP6256 RF section (chip RF/PA/LNA, front-end switch, reference crystal, or its local supply), not Android, Skylight software, firmware version or regulatory setup. Not yet physically confirmed. Framework scanning was re-enabled afterward.
