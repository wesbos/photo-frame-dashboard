# Sammix AW105 Uhale: reported SystemUI malware loader

**Keep a suspected frame off the internet and separate from trusted devices. Disabling the
downloaded apps alone does not remove a loader inside SystemUI.** Do not disable SystemUI or
delete its native library as a generic fix: that can break the interface and recovery access.

This records [jlj-dev's investigation, issue #279](https://github.com/wesbos/photo-frame-dashboard/issues/279)
and its [three-unit follow-up](https://github.com/wesbos/photo-frame-dashboard/issues/279#issuecomment-6550107051).
The maintainer has not independently examined the firmware or tested the mitigation. No vendor
binaries or dumps are hosted here. See [frame security](security.md) for containment and evidence handling.

## Reported units

| Field | Reported value |
| --- | --- |
| Product | Three Sammix AW105 Uhale frames, purchased from Amazon |
| Product / board | `si006asb` / `sp7731g_1h10`, Spreadtrum |
| Android | 6.0 |
| Fingerprint | `S0645/si006asb/sp7731g_1h10:6.0/MRA58K/W26.17.6-11:user/release-keys` |
| Build description | `eng.zfc.20260425.111341` |
| About-screen build | `S0645_K105_V01_202604251115` |
| Host / connection | macOS, USB-A to USB-C, root ADB available during investigation |
| Library | `/system/priv-app/SystemUI/lib/arm/libunionnn.so`, 363,532 bytes |
| Library SHA-256 | `1ea86e2a09d34114df45a801850425b535166f6d42d57a62370e1ffb1b98c522` |

The library was byte-identical in all three system backups, taken before system modifications
and before connection to the reporter's Wi-Fi. This does **not** establish that the units had
never been online: the follow-up corrects the original report on that point. Earlier dated
artifacts suggest prior network use, but where it happened and who was responsible are unknown.

## Evidence and limits

The reporter traced `SystemUIApplication.onCreate` through `org.b.c.lib.MainLib` to loading
`libunionnn.so` and calling `nativeInit()`. SystemUI held package installation and deletion
permissions. On the first unit, three apps labeled **Sys** appeared with
`installer=com.android.systemui`:

- `com.mobile.applock.xk1`
- `com.mobile.applock.xk3`
- `com.rainbow.xk4`

SystemUI's private data held `files/plg` plugin files and `app_e_kw_lib` artifacts. The reporter
observed many connections attributed to the apps and SystemUI, including port 25 attempts.
Relayed proxy traffic is a hypothesis; packet contents were not captured. Native crash records
may explain the **Unfortunately, Sys has stopped** dialog, but no dialog was matched to a record.

**The other two units had no installed Sys apps, yet both had `kwlib` artifacts.** Package absence
is therefore not a useful clean bill of health. An unsuccessful path lookup or a different library
hash also cannot clear another firmware: loader names, locations and host apps may differ.

The older [SI006 report](si006-uhale.md#dashboard-launcher-and-disabled-apps) lists the same three
packages on a different build (`W25.22.5-11`). That unit's loader has not been investigated here.
Neither shared package names nor a shared board establishes the same infection on SI006,
[VTimes VT01001](vtimes-vt01001.md) or [HSB / F10](uhale-hsb-f10.md).

## Read-only checks

Use an already authorized USB ADB connection to the selected frame. These checks do not require
internet access. Root is needed to inspect SystemUI's private data. Keep output private; package
lists and diagnostic files may contain information about the owner.

```sh
adb -d shell getprop ro.build.fingerprint
adb -d shell 'pm list packages -3 -i'
adb -d shell 'ls -l /system/priv-app/SystemUI/lib/arm/'
adb -d shell 'sha256sum /system/priv-app/SystemUI/lib/arm/libunionnn.so'
adb -d shell 'ls -ld /data/data/com.android.systemui/files/plg /data/data/com.android.systemui/app_e_kw_lib'
```

`Permission denied`, an unavailable hashing tool or a missing path is inconclusive. Do not
enable network ADB or take a new write route just to run this checklist. Match observations to
the specific build and preserve the original files privately before considering a change.

## Reported mitigation: a record, not an installation procedure

The reporter replaced the library with an empty ARM shared library that still loads, then
cleared SystemUI's downloaded state and removed the observed payload apps. On this build,
the later missing `nativeInit()` implementation was caught and SystemUI continued running.
Simply deleting the original library could instead raise an uncaught `UnsatisfiedLinkError`;
that failure mode was inferred from the code and was not tested.

The follow-up reports the same mitigation on all three matching units. Each was watched for
60 minutes with socket sampling every five seconds. The reported payload apps and plugin
artifacts were absent afterward. Sampling can miss short connections, and an hour without
observed traffic is not proof that all unwanted firmware behavior is gone.

The issue's write snippet is **not an upstream-approved procedure**. It does not implement the
repo's full verified-backup checks, automatic compare-before-write, on-device payload hash check,
readback comparison and guarded undo. It also stages a root-consumed file in shell-writable
`/data/local/tmp`. We have not added that writer or its generator to the setup tools. A future
implementation must address these checks, preserve file metadata and read-only remounts on
failure, and prove recovery access before touching SystemUI. Clearing its data also discards
state; it is not fully reversed by restoring the library alone.

Keep external containment in place while investigating. A factory reset or reflash of the same
affected firmware can leave or restore the loader. Returning or retiring a suspect frame is an
alternative to an unverified system modification.

## Related research

[Quokka's Uhale assessment](https://www.quokka.io/blog/major-security-issues-digital-picture-frames)
reports automatic malware delivery on some Uhale frames. The [FBI's BADBOX 2.0 notice](https://www.ic3.gov/PSA/2025/PSA250605)
includes digital picture frames among affected device categories. Neither establishes the
specific loader or attribution for these three units. Issue #279 also compares components with
Kaspersky and Bitdefender research; those similarities do not establish a common operator.
