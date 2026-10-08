# USB Wi-Fi dongle replacement

The onboard AP6256 radio appears dead (see [native Wi-Fi root tests](native-wifi-root-tests.md#firmware-radio-counters-2026-09-19)). This records the plan and pre-hardware results for a USB Wi-Fi dongle instead.

Owner clarified on 2026-09-21: get the dongle working with the existing Android 12 installation first; Android 14 support is a separate future phase. Preserve the driver sources, build artifacts and integration notes for that work. Android 14 compatibility is not yet tested.

**Current result: persistent Android 12 USB Wi-Fi is installed and reboot-tested.** The device automatically loaded the module, selected the USB radio, connected using saved credentials, and validated internet with Ethernet physically disconnected. Full details and recovery instructions are below.

## Why an RTL8188EU dongle

- Kernel: `CONFIG_MODULE_SIG` is not set, `CONFIG_MODVERSIONS=y`, cfg80211 and mac80211 are built in. Only SDIO Wi-Fi drivers ship; `# CONFIG_RTL8188EU is not set`, so Rockchip's source for it is in this tree family.
- Rockchip's Wi-Fi HAL (`/vendor/lib64/librkwifi-ctrl.so`, `libwifi-hal.so`) scans `/sys/bus/usb/devices` for known IDs and loads the matching `/vendor/lib/modules/<name>.ko`. RTL8188EU matches only `0bda:8179` and `0bda:0179` → `8188eu.ko`. Other recognized USB chips: 8723BU `0bda:b720`, 8188FU `0bda:f179`, 8822BU `0bda:b82c`, 8192DU `0bda:8194`, 8812AU `0bda:8812`. Matching is by exact ID, so vendor-specific IDs (TL-WN722N v2/v3 `2357:010c`, Archer T2UB Nano) are not auto-detected.
- Owner ordered a TP-Link TL-WN725N (RTL8188EUS, expected `0bda:8179`). Verify the ID on the Mac before connecting it to the calendar.
- Host mode: the micro-USB port is dwc3 `dr_mode=otg` with extcon ID detection and a `vcc5v0-otg` VBUS regulator. A micro-B **OTG** adapter (ID grounded) is required. A micro-OTG to USB-C adapter allows the existing hub with Ethernet, keeping network ADB available during bring-up.

## Kernel symbol versions

`scripts/extract-symvers.py` rebuilds `Module.symvers` from the stock boot image's raw arm64 Image using live kallsyms section bounds (PREL32 ksymtab plus absolute kcrctab). 6,102 + 5,545 exports. All 955 `__versions` entries of stock 8723cs, 8821cs, bcmdhd and ssv6x5x match, so the extraction is correct.

## Build

`scripts/usb-wifi.Dockerfile` (Ubuntu 22.04, clang/lld 12.0.1) and `scripts/build-usb-wifi.sh` build rockchip-linux/kernel develop-4.19 (tarball SHA-256 `42c9eefbda703ed85937edc95284d5c7596cb90e56e30b88731a0f7d191f013c`, 4.19.232) inside a case-sensitive Docker volume with the device's own config plus `CONFIG_RTL8188EU=m`. Only 11 config lines differ from stock: Skylight-only board/SSV/audio options and a few newer Rockchip options. The public rknpu Makefile's `-Werror` is removed in the build copy.

Output `diagnostics/tools/usb-wifi-build/8188eu.ko`, SHA-256 `3ce4da05877158e76dc825719c6381873db7beb3e86fb5b722e1368d14e29d16` (unstripped), vermagic `4.19.232 SMP preempt mod_unload modversions aarch64`, identical to stock modules.

CRC comparison of the full build against stock: 11,646 common exports, 212 differ, all in DRM/GEM, fbdev, dma-buf, videobuf2 and Mali kbase (Skylight display-stack changes). None in USB, networking, cfg80211/mac80211, SDIO or MMC. All 207 symbols 8188eu imports match stock CRCs. `get_sky_light_sensor_value` exists only in stock.

## Live load test without hardware (2026-09-19)

As root: `insmod` returned 0; the driver logged `rtl8188eu v5.7.6.1_36803.20200508`, registered the `rtl8188eu` USB interface driver and `module init ret=0`. No warnings or oops. `rmmod` returned 0 with `module exit success`. Nothing was installed persistently. Android Wi-Fi had been switched off earlier from Settings (18:42), unrelated to this test.

## Hardware and Android 12 results

### Hardware test, 2026-09-21

The owner's micro-USB → USB-C → USB-A/hub chain did not automatically enable host mode. A temporary write of `host` to `/sys/devices/platform/fe8a0000.usb2-phy/otg_mode` after disconnecting the Mac enabled USB host and VBUS. Restoring `otg` recovered USB ADB. No persistent change was made.

The hub, mouse, Ethernet and RTL8188EU enumerated. The Wi-Fi driver created `wlan2` and `p2p0`; onboard Broadcom already owns `wlan0` and `wlan1`. The initial diagnostic selected `p2p0`: first scan reported `scan aborted!` despite exit status 0, but the next two returned nearby access points, including the owner's network. Subsequent diagnostics select the USB `wlan*` interface. Ethernet acquired a LAN IPv4 address. Association, Android Wi-Fi integration and persistence remain untested. Private captures are in `diagnostics/usb-wifi-2026-09-21/`.

`scripts/test-usb-host-on-device.sh` waits for USB disconnect, forces host temporarily, runs `scripts/test-usb-wifi-on-device.sh`, then restores automatic OTG mode. Its optional duration is 180 or 900 seconds; an independent fallback restores OTG 30 seconds later if the main diagnostic stalls. Do not reconnect the Mac during forced host mode.

### Android framework connection succeeded

USB ID `0bda:8179` and the prepared module's SHA-256 were verified. Network ADB over the hub's Ethernet allowed live integration. With Android Wi-Fi disabled and `vendor.wifi_hal_legacy` stopped, the inactive Broadcom interfaces were renamed `onboard0`/`onboard1`, and the USB primary interface `wlan2` was renamed `wlan0`. Starting the HAL and enabling Wi-Fi connected automatically using the owner's saved credentials. Android reported WPA handshake completed, a DHCP address, and WIFI `VALIDATED`. A ping explicitly bound to `wlan0` reached an external IP with 3/3 replies and no loss. ADB also connected to the Wi-Fi address.

The HAL still logs chip type AP6255 and unsupported optional vendor operations (debug statistics/APF/RSSI monitoring), but standard association, DHCP and internet validation work with RTL8188EU. Broadcom was not unloaded or reloaded. No vendor module path or firmware file was changed.

The temporary host-test parent and fallback timer were stopped and killed after live network access was established, leaving host mode active for this session. A reboot restores automatic OTG and removes the temporary module/interface configuration. Do not connect the Mac to the forced-host port; first restore `otg` over network ADB, or reboot before reconnecting the Mac. `adb tcpip 5555` was enabled for this session with existing authentication preserved.

## Remaining steps

Ethernet was physically disconnected by the owner. Its carrier reads 0 and `eth0` is down with no address; Wi-Fi remains connected and validated, and network ADB continues over the USB Wi-Fi dongle.

1. Completed: verify the connection with the Ethernet cable physically disconnected.
2. Completed: host mode, driver loading and interface selection survive reboot through the startup mechanism below.
3. Check Wi-Fi toggle and dongle reconnect behavior, then assess whether the HAL's optional vendor-operation errors need further changes.
4. Android 14 support is future work.

## Persistent installation and successful reboot

`scripts/build-wifi-boot.py` uses the exact verified debug boot image and adds one property to its existing `adb_debug.prop`:

```properties
ro.boot.init_rc=/metadata/skylight-wifi/init.rc
```

The installed first-stage fstab mounts `/metadata` before second-stage init. The inspected Android 12 init implementation reads `ro.boot.init_rc` when selecting its boot scripts. The root-owned metadata wrapper imports all six stock entry points in their original order, then defines a root oneshot Wi-Fi service triggered by `sys.boot_completed=1`. It keeps stock Android boot services, ADB authentication, kernel, resource/DTBs and the partition tail unchanged. The startup script is restricted to Android 12 / kernel 4.19.232.

Installed files:

- `/metadata/skylight-wifi/init.rc`: from `scripts/skylight-wifi-init.rc`, mode 0600, directory 0700.
- `/metadata/skylight-wifi/start.sh`: from `scripts/skylight-wifi-start.sh`, mode 0600, invoked through `/system/bin/sh`.
- `/data/local/skylight-wifi/8188eu.ko`: the original hardware-tested module, mode 0600, SHA-256 `3ce4da05877158e76dc825719c6381873db7beb3e86fb5b722e1368d14e29d16`.
- `/data/local/skylight-wifi/boot-before-wifi.img`: verified debug-boot rollback copy, SHA-256 `f6e2c27c89a3db7835089fa8037909dc5e7eb62745eb90471fabab58b49821b3`.

The new full boot partition image is 67,108,864 bytes, SHA-256 `a97c648870c3fd377fe23680367857e3478d81825665e899d56349450f9cfd8e`. Independent parsing verified both Android SHA-1 image IDs, all component offsets, every unchanged CPIO entry, and the single property-file modification. The candidate was staged on the device, checksummed, written to `/dev/block/by-name/boot` from root Android, flushed and fully SHA-256 read back. The previously installed partition was backed up and verified before writing. The system and vendor partitions were not rewritten.

After `adb reboot`, Android reported boot completion and the new init-script path. The service log recorded finding USB `wlan2` and completing startup; it is expected to show `stopped` afterward because it is a oneshot service. It renamed the inactive onboard interfaces, selected USB `wlan0`, connected automatically, and enabled authenticated TCP ADB. Ethernet carrier was 0 and `eth0` had no address. Wi-Fi was Android's validated default network; an external ping bound to `wlan0` received 3/3 replies. Root ADB remained available on explicit request. Captures are `diagnostics/usb-wifi-2026-09-21/persistent-reboot-*`; the build/install manifest is `diagnostics/usb-wifi-boot-candidate/manifest.json`.

### Recovery and removal

Keep the hub and dongle attached for ordinary boots. Hot-unplug/replug recovery has not been established; reboot with the dongle attached to rerun setup.

For USB ADB recovery, power off, remove the hub, connect the normal Mac data cable, then power on. If a computer is detected at startup, the script leaves USB in peripheral mode. If no dongle appears within 60 seconds after forcing host mode, it also restores automatic OTG. These fallback branches are implemented but have not been physically tested. While host mode is active, do not reconnect a computer cable until `echo otg > /sys/devices/platform/fe8a0000.usb2-phy/otg_mode` has been issued over network ADB or the device is powered off.

To temporarily disable Wi-Fi startup, use root ADB to create `/metadata/skylight-wifi/disabled` and reboot. Removing the flag re-enables it on the next boot.

To fully undo the startup change, verify the rollback image's exact SHA-256 above, restore it to `/dev/block/by-name/boot`, flush, verify the entire partition matches, then reboot. The same rollback image is preserved on the Mac at `diagnostics/debug-boot-candidate/boot.img`; the original stock boot is separately preserved at `backups/extracted/boot.img`. Only after restoring boot may the metadata wrapper and data files be removed. **Do not wipe `/metadata` or factory-reset while this custom boot-script path is installed; restore the prior boot first.** The boot process now relies on its wrapper in `/metadata`.
