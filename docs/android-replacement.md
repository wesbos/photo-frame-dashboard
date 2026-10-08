# Android replacement and rollback assessment

Read-only assessment, 2026-09-14. No replacement Android was installed.

Live properties report Treble enabled, ARM64 ABI, VNDK32 and dynamic partitions enabled. The DynamicSystemInstallationService APK, gsid and gsi_tool are present. These are promising prerequisites for evaluating a Generic System Image, not proof that one boots or that DSU installation works.

Android reports ro.boot.flash.locked=0 and verifiedbootstate=orange, whereas earlier fastboot getvars reported unlocked=no and secure=yes. The sources disagree; do not assume unlock requirements or trigger an unlock based on either alone.

[AOSP GSI guidance](https://developer.android.com/topic/generic-system-image) requires compatible vendor interfaces and an appropriate boot/unlock configuration. [DSU](https://developer.android.com/topic/dsu) can install a guest system separately and switch back to the original system on supported implementations. DSU is the next reversible route worth investigating; only its installed components have been confirmed here.

The validated full main-flash backup includes the original GPT, boot components, Android partitions and userdata. Loader/MaskROM RAM-helper access and unrestricted reads were verified. A flash-write-and-restore cycle has not been tested, so rollback is plausible but not guaranteed. The main-flash capture is not a backup of hardware fuses, RPMB or every possible eMMC hardware region; preserving the existing boot chain and avoiding security-state changes matters.

An experimental GSI should retain the device's existing kernel and board-specific vendor components where compatible. Consequently replacing the Android system alone may leave the present Wi-Fi driver/firmware failure unchanged. No known-working replacement image for this exact unit has yet been established.
