# KPKUE DP-10B (Frameo, Android model DP105F)

One-unit report from [@agoole in PR #264](https://github.com/wesbos/photo-frame-dashboard/pull/264),
tested on 2026-10-28/29 from an Apple silicon Mac running macOS. Bought from
[Amazon.ca B0FFHNT5LK](https://www.amazon.ca/dp/B0FFHNT5LK).

USB ADB worked through a hub after a direct USB-C connection failed. Shipped `su` returned
root, and Home HQ started after a complete power cycle once selected as Home. No UART,
soldering, boot patch or offline partition edit was needed for that result.

This is a record of one unit. Its full Android fingerprint and firmware build were not supplied,
so it is not a firmware profile for the setup scripts. Do not reuse another DP105F's partition
offsets or write tools based on the model name alone.

## Identity

| Item | Reported value |
| --- | --- |
| Case brand / model | KPKUE / DP-10B |
| Android model / manufacturer property | `DP105F` / `rockchip` |
| Android | 8.1.0, API 27 |
| Frameo | v1.29.10 (59940) |
| Platform | RK3326 family inferred from the reported similarities to other DP105F frames; exact SoC not independently identified |
| Storage | `mmcblk2`, 16 partitions; 62,545,461,248-byte user area |
| Display | 1440×1080 reported; density 160 |
| Root | Shipped `su -c id` returned `uid=0(root)` with no prompt |

The [QCREA YYD-1156](qcrea-yyd-1156.md) and [Pastigio FRAME156/157](pastigio-frame156.md)
also use the Android model `DP105F`. That alone does not establish the same board, firmware or
partition layout.

## USB and ADB

With Frameo **Settings → About → Beta Program → ADB Access** enabled, a direct USB-C connection
to the Mac produced no USB enumeration or ADB device. Trying other cables, ports and reboots
did not resolve it. Adding a USB-C multiport hub between the Mac and frame made it enumerate,
and ADB showed `device`. The exact hub model and downstream connection were not recorded.
Whether an authorization prompt appeared, and whether an unfamiliar host key is rejected,
were not recorded.

The frame's USB-A port acted as a host for importing photos. Use its USB-C port for the computer
connection. On this unit, removing barrel-jack power shut the frame down even with the direct
USB-C cable attached. The cause of the enumeration difference was not established.

## Kiosk result and limits

The [kiosk build and install steps](../dashboard/kiosk/README.md#build-and-install) worked.
After enabling Home HQ's optional Home alias and selecting it as Home, the owner waited about
30 seconds for Android to save the setting. Disconnecting and reconnecting power then started
the dashboard automatically.

The initial report noted letterboxing on the 4:3 panel. A later customized dashboard changed
its layout, but that fork's features are not part of the repository demo.

No verified full-device backup or restore test was reported. Physical Settings → Apps recovery,
unknown-key rejection, network ADB, and long-term unattended operation were not documented.
Follow the [backup and recovery rules](../README.md#rules-we-learned-the-hard-way) before further
changes or disabling the existing launcher.
