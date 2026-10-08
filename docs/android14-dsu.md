# Android 14 GSI trial through DSU

Goal: a current browser and Google apps. The trial uses Dynamic System Updates, so the stock Android 12 system and its userdata are not modified; the guest lives in pinned files on /data and `gsi_tool enable -s` makes it one-shot.

## Prerequisites observed (2026-09-19)

gsid and com.android.dynsystem present; `ro.boot.flash.locked=0`, verified boot orange; /data f2fs with about 10 GB free; /metadata/gsi exists; vendor VINTF target-level 6. No /avb keys in the boot ramdisk, which did not block the unlocked DSU boot.

## Image

Google Android 14 QPR1 GSI ARM64+GMS `gsi_gms_arm64-exp-UQ1A.231205.015-11084887-2026a0e7.zip` from the [official GSI release page](https://developer.android.com/topic/generic-system-image/releases). Zip SHA-256 `2026a0e788abf09a91421a4f83b7d766bfe1ec82707e3b6a5ca74f6c65212fc8` matched the published value. system.img is raw ext4, 3,066,781,696 bytes, user build, security patch 2023-12-05, includes 32-bit support. Stored under ignored diagnostics/tools/gsi/.

## First boot: BoringSSL self-check reboot

Installed with `adb exec-in gsi_tool install --gsi-size 3066781696 --userdata-size 3145728000 --wipe < system.img` (6 min 40 s). The device then booted the guest once and rebooted with `reboot,boringssl-self-check-failed`; one-shot mode returned it to Android 12 (install_status `disabled`). Android 12 booted normally.

pstore console log of the guest boot: second stage started at 3.9 s; SELinux went **enforcing** (the user GSI ignores `androidboot.selinux=permissive`); apexd reported `ActivateFlattenedApex` and `This device does not support updatable APEX. Exiting`. Only the flattened fallbacks in /system_ext/apex (runtime, i18n, vndk, virt, cts shim) were bind-mounted. The Google mainline APEX files in /system/apex (Conscrypt, ART, `com.google.mainline.primary.libs` shared libraries) were never activated, so the Conscrypt `boringssl_self_test_apex*` could not load `/apex/sharedlibs/.../libcrypto.so` and init rebooted.

Cause: the Android 12 vendor never sets `ro.apex.updatable` (the stock system uses flattened APEX directories), and the GSI ships no value of its own, expecting the vendor to provide it.

## Patched trial image

`system-mod.img`: the original with /system/build.prop edited in place (inode 638, blocks 74763–74764, same inode, mode 0600 and SELinux label), size 4515 → 4647:

- `ro.adb.secure=1` → `0` (trial convenience; the guest has no stored ADB keys)
- appended `ro.apex.updatable=true` and `persist.sys.usb.config=adb`

The AVB footer was erased and regenerated with avbtool (external/avb main, SHA-256 `e5a664a38db623da00f080219bc0ee60a640a9dc4a872803616fae4938ac749b`): same partition size, sha256 hashtree, rollback index and descriptor props, no FEC, signed with a locally generated trial RSA-4096 key. `e2fsck -fn` clean; `avbtool verify_image` passes. SHA-256 `b9ef42d3adf45df674133b349dd75b928af96d2d92b074904771a373e365d9d3`. The Android 12 system is not affected because the property exists only inside the guest image.

## Install streaming note

A second `adb exec-in` install logged `gsid: read gsi chunk: I/O error` at the end and left an image with `invalid AVB footer`, while gsi_tool still exited 0. Check gsid logs, not just the exit code. Reinstalling with `adb shell -T 'gsi_tool install …' < system-mod.img` (6 min 22 s) reached `write system 100%`. Both complete installs were followed within seconds by a reboot into the guest; gsi_tool's default enable is one-shot (`one_shot_boot=1` was observed after the first).

## Second boot: Android 14 running

With the patched image, the guest reached `sys.boot_completed=1` about a minute after reboot: Android 14, patch 2023-12-05, `ro.apex.updatable=true`, SELinux enforcing, ADB working (`product:gsi_gms_arm64`), `ro.debuggable=1` from the debug ramdisk. Google setup wizard in the foreground. Play Store, GMS, Chrome and Google WebView 116.0.5845.195 are installed. Display 1920×1080 at 240 dpi. No crash-buffer entries at first check. Wi-Fi disabled (onboard radio still faulty); `wlan0` and `wlan1` exist.

Network for setup: gnirehtet 2.5.1 client installed in the guest, `appops set com.genymobile.gnirehtet ACTIVATE_VPN allow` to avoid the VPN dialog, relay started with `scripts/share-internet.sh run`. The VPN network reported VALIDATED and Google TLS connections opened through the relay.

## Soft reboots: per-app memcg denial

In the running guest, `system_server` restarted three times in five minutes (`sys.system_server.start_count=3`) with `java.lang.AssertionError: Unable to create process group for com.google.android.webview:sandboxed_process0…` from `ProcessList.startProcess`, preceded by `avc: denied { create } for comm="ActivityManager" name="uid_99000" scontext=u:r:system_server:s0 tcontext=u:object_r:cgroup:s0 tclass=dir permissive=0`. The vendor sets `ro.config.low_ram=true`, so Android 14 defaults to per-app memcg under the cgroup-v1 `/dev/memcg/apps` hierarchy (label `cgroup`), which its enforcing policy does not let system_server write. Any sandboxed/isolated process (Chrome and WebView renderers) triggered a system restart.

Fix: `ro.config.per_app_memcg=false` appended to the guest /system/build.prop (the vendor does not set it). `system-mod2.img` SHA-256 `b36d0e2e59cd620d845841ed2c11c6ac29e40ef22ca03accab858fdb95890a4e`, built as before but with the original Google hashtree salt.

### In-place patch, keeping guest userdata

The DSU image files on FBE /data cannot be compared through the filesystem: gsid writes the image unencrypted to the raw userdata partition through dm-linear. `lpdump /metadata/gsi/dsu/dsu/lp_metadata` gave system_gsi extents on `userdata` (sectors 7049216+4096, 7041024+4096, 7053312+5981616). Reading /dev/block/mmcblk2p14 at those sectors matched system-mod.img exactly (2 small extents by hash; third extent in 4 MiB chunks; tail by hash). For image blocks ≥ 1024, raw 4 KiB block = 880640 + image block.

Only 5,806 blocks (22.7 MiB, 3 runs: 65543, 74764, 736891–742694) differ between the two trial images. From Android 12 as root, each run was pre-checked against the old content, written with dd, and post-checked against the new content. All three passed. `gsi_tool enable -s` → reboot: Android 14 with `ro.config.per_app_memcg=false`, guest `user_setup_complete=1` preserved. A full-image `sha256sum` through toybox dd with `iflag=skip_bytes,count_bytes` gave a misleading mismatch; use block-aligned reads.

After unlocking (CE storage is locked until first unlock; `wm dismiss-keyguard` works with no PIN), Chrome 116 on wikipedia.org ran `sandboxed_process0` and `privileged_process0` with no system_server restart, cgroup error or denial. MemAvailable about 680 MB of 2 GB, about 280 MB zram swap in use. Chrome and WebView are 116.0.5845.195 until updated from Play.

## USB host mode and network ADB (trial v3)

The board ignores the OTG adapter's ID pin: with a genuine OTG adapter the port stayed in device mode, `vcc5v0_otg` stayed disabled, and no hub or mouse powered up. The otg-port DT node has only `vbus-supply`, no ID interrupt. Forcing it from Android 12 as root (`echo host > /sys/devices/platform/fe8a0000.usb2-phy/otg_mode`, timed script with automatic `otg` restore) powered the hub immediately: Genesys 05e3:0610 hub, HID mouse 1241:1166, Realtek RTL8153 `0bda:8153` on built-in r8152 (optional `rtl_nic/rtl8153b-2.fw` patch missing, works without it) as `eth0`, and Android DHCP leased a LAN address. Raw log: /data/local/tmp/host-test-20260920.log on the device.

In the Android 14 guest the shell can set only `debug.*` properties (`persist.debug.*`, `persist.sys.*` and `service.adb.tcp.port` are refused), and adb root is unavailable (the user GSI has no su domain). otg_mode is labelled `sysfs_usb`.

`system-mod3.img` (SHA-256 `a5357a72413dedec371d1a49298c6ab240f6d03dcad57b506d15fcd1be6d36e0`, same salt/key as v2):

- build.prop: `ro.adb.secure=1` again, plus `service.adb.tcp.port=5555` and `debug.skylight.usb_host=1`
- /system/etc/init/usbd.rc (inode 740, block 75667, 103 → 545 bytes): on `sys.boot_completed=1 && debug.skylight.usb_host=1` write `host` to otg_mode; on `=0` write `otg`

11 blocks differ from v2. Applied in place from Android 12 with pre/post hash checks, all passing. Guest left disabled (not enabled for the next boot) pending an on-site test: USB works until boot completes, then the port becomes host; approve the Mac's ADB key on screen at the first `adb connect <ip>:5555`. `adb shell setprop debug.skylight.usb_host 0` returns to device mode. While the guest is one-shot, a power cycle returns to Android 12, which has no host-mode rule.

## Trial v4: init policy for otg_mode, Ethernet working

In v3 the usbd.rc rule fired but init was denied: `avc: denied { write } for comm="init" name="otg_mode" scontext=u:r:init:s0 tcontext=u:object_r:sysfs_usb:s0 permissive=0`. The first-boot USB drop observed with v3 was probably an adbd restart, not host mode. `dumpsys usb` reports `usb_hal_version=-2` (no USB HAL), so `set-port-roles` is not an alternative.

`system-mod4.img` (SHA-256 `f2844e9ed9bc943e869f610f80212a3df553b808588bb4895a77954063e6585b`) appends to /system/etc/selinux/plat_sepolicy.cil (inode 1005, last block 77103; 2,131,715 → 2,131,854 bytes): `(allow init sysfs_usb (file (open write getattr)))`. The GSI policy is compiled at boot from CIL, because the vendor precompiled-policy hash does not match. 8 blocks differ from v3, applied in place from Android 12 with pre/post checks.

Result 2026-09-20: after `gsi_tool enable -s` and reboot, USB to the Mac disappeared at boot completion and stayed gone. With the OTG adapter and hub, the hub powered on; `otg_mode=host`, `eth0` has a LAN address and is the active default network (ETHERNET, validated), and `adb connect <frame-ip>:5555` connected with the existing authorized key.

A reboot from inside the guest returned to Android 12 (one-shot honoured). An earlier unexplained `reboot,shell` from inside the guest had come back to Android 14 once. Watch for it before relying on the one-shot fallback.

macOS note: after the Mac restarted, `adb connect` failed with `No route to host` while `nc` reached port 5555. Restarting the adb server (`adb kill-server; adb start-server`) fixed it (Local Network permission for the daemon).
