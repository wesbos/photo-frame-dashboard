# Proposed RAM-recovery Wi-Fi diagnostic sequence

Prepared offline; not yet validated in a running diagnostic recovery. This tests one passive scan without joining a network. The operator must first verify that recovery is temporary, ADB is root, `/tmp` is RAM-backed, and the expected stock module and firmware are present. Do not run the bundled PCBA scripts: they include `/data` writes and manufacturing-mode changes unrelated to this test.

## Evidence and prerequisites

The recovery module is `/pcba/lib/modules/rkwifi/bcmdhd/bcmdhd.ko`. Its metadata reports `4.19.232 SMP preempt mod_unload modversions aarch64`, no declared module dependencies, and these load parameters: `firmware_path`, `nvram_path`, `config_path`, `wl_dbg_level`, `dhd_console_ms`. Its strings include the scan-abort reason messages. The AP6256 diagnostic ramdisk contains the same runtime-selected firmware basename, `fw_bcm43456c5_ag.bin` (606,190 bytes), plus `nvram_ap6256.txt` and `config.txt`. The latter specifies `ccode=US` and `regrev=0`; normal Android's driver maps that to `US/988`. Preserve these existing settings for the baseline.

The [Rockchip driver source](https://github.com/rockchip-linux/kernel/blob/develop-4.19/drivers/net/wireless/rockchip_wlan/rkwifi/bcmdhd/dhd_linux.c) exposes console polling as `dhd_console_ms`; [its logging header](https://github.com/rockchip-linux/kernel/blob/develop-4.19/drivers/net/wireless/rockchip_wlan/rkwifi/bcmdhd/wl_cfg80211.h) assigns bits 0–3 to ERR, INFO, DBG and SCAN. Therefore `wl_dbg_level=15` enables those categories in that source. The local module confirms the parameter and relevant messages, but exact source equivalence remains unverified.

Run checks individually and inspect failures before proceeding:

```sh
id
uname -r
cat /proc/mounts
cat /proc/modules
ls -l /sys/bus/sdio/devices
ls -l /pcba/lib/modules/rkwifi/bcmdhd/bcmdhd.ko
ls -l /vendor/etc/firmware/fw_bcm43456c5_ag.bin
ls -l /vendor/etc/firmware/nvram_ap6256.txt
cat /vendor/etc/firmware/config.txt
ps -A
```

Check that no Android Wi-Fi service, supplicant or manufacturing test is already issuing scans. Do not launch one. Copy the locally built static `iw` to `/tmp/skylight-iw` only after confirming that location is RAM-backed, and verify its hash against the host build. Check `/sbin/busybox --list` includes `timeout`; use available `ip`, `insmod`, and `dmesg` applets or their `/sbin/busybox` equivalents.

## Load, capture, scan

Only if `bcmdhd` is absent from `/proc/modules`, load it once with explicit stock paths and diagnostic logging:

```sh
insmod /pcba/lib/modules/rkwifi/bcmdhd/bcmdhd.ko \
  firmware_path=/vendor/etc/firmware/fw_bcm43456c5_ag.bin \
  nvram_path=/vendor/etc/firmware/nvram_ap6256.txt \
  config_path=/vendor/etc/firmware/config.txt \
  wl_dbg_level=15 dhd_console_ms=200
```

If insertion fails, collect the error and kernel log; do not repeatedly reload or substitute another board's module. If already loaded, inspect its current parameters instead. `wl_dbg_level` may be load-only and absent from sysfs. Optional debugfs `debug_level` can support `SCAN:1 DBG:1 INFO:1`; save and restore its existing text if using that route. Save the existing `dhd_console_ms` value before modifying an already-loaded module.

```sh
ip link show wlan0
ip link set wlan0 up
/tmp/skylight-iw dev
/tmp/skylight-iw reg get
cat /sys/module/bcmdhd/parameters/firmware_path
cat /sys/module/bcmdhd/parameters/nvram_path
dmesg > /tmp/wifi-before.txt
```

Inspect initialization before scanning: SDIO chip identification, selected firmware/NVRAM paths, download comparison, firmware startup, and any country or transport errors. A firmware path parameter can be cleared by the driver after consumption, so the log is the stronger selection record.

```sh
/sbin/busybox timeout 20 /tmp/skylight-iw event -t > /tmp/wifi-events.txt 2>&1 &
/sbin/busybox timeout 15 /tmp/skylight-iw dev wlan0 scan freq 2412 passive > /tmp/wifi-scan.txt 2>&1
dmesg > /tmp/wifi-after.txt
```

The event listener is optional, and times out itself. If exact ordering matters, start it in a separate host session before the scan. `iw scan` exit status should be recorded immediately on the host. A command timeout does not guarantee the firmware scan was canceled; collect the log before deciding on cleanup or another test. Do not issue overlapping scans.

Keep all captures private: successful results can include nearby network names and addresses. Inspect firmware console and `ESCAN ABORT reason` messages, comparing request, abort and native event timestamps. A successful zero-result scan differs materially from an aborted scan. If it succeeds in recovery, normal Android's service/driver state becomes a stronger suspect, but one recovery result does not prove a particular cause. If it still aborts, record the specific reason before choosing any second test.

## Cleanup

Bring `wlan0` down after capture if this sequence brought it up. Restore changed logging values on an already-loaded module. For a module loaded only by this sequence, restarting to normal Android discards the temporary recovery/module state; do not force-unload it. This sequence neither connects to an access point nor edits firmware, calibration, partition contents or saved networks.
