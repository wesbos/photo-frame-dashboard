# External networking assessment

Read-only checks on2026-09-14 found built-in USB Ethernet drivers: RTL8152/8153, AX8817X, AX88179/178A, CDC Ethernet/NCM and others. Android advertises android.hardware.usb.host and its Ethernet service is running, with interface filter eth\d. No Ethernet interface is currently tracked. These support trying a compatible adapter; they do not prove the physical micro-USB port can supply host power or switch roles correctly.

A genuine micro-USB OTG host adapter is the first connection requirement to test. The previously attempted USB-C-to-micro adapter/hub combination is not identified, so its failure does not establish that USB Ethernet is unsupported. A normal shape-changing/data adapter may not request host mode. Retain wall power; the same port cannot simultaneously serve the Mac's ADB connection and a hosted USB peripheral in the ordinary arrangement.

The existing kernel does not show enabled support for the usual tested USB Wi-Fi families; several Realtek names in the firmware are SDIO variants. No plug-and-play USB Wi-Fi adapter has been established. The Android Wi-Fi integration would also need to support a replacement interface.

A USB Ethernet adapter using an exact supported chipset is a stronger candidate. Example manufacturer-documented RTL8153 device: [StarTech USB31000S2](https://www.startech.com/en-us/networking-io/usb31000s2). This is chipset evidence, not a claim of tested Skylight compatibility. Identify the owner's existing hub and host adapter before buying another.

If physical Ethernet cabling is inconvenient, a separate Wi-Fi-to-Ethernet bridge/travel router can connect wirelessly and supply a LAN cable to the USB Ethernet adapter. [GL.iNet documents this arrangement](https://docs.gl-inet.com/router/en/4/faq/produce_a_wired_connection/). First establish USB Ethernet and whether Skylight onboarding accepts that connection; neither is runtime-tested yet.

Follow-up app analysis found an explicit Wi-Fi-only NetworkRequest in onboarding. Therefore working Ethernet may still face the same app gate as the verified USB VPN. External networking and acceptance by Skylight onboarding must be evaluated separately; see onboarding-network-gate.md.
