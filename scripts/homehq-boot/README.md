# Home HQ boot app

Starts the dashboard at boot on a frame whose firmware blocks the usual ways to do it, with
no `/system` write. Written for the [QOCEN J1008](../../docs/qocen-j1008.md) (Allwinner A33,
Android 6.0.1); it should suit any frame with the same obstacle.

## Why it exists

That firmware runs a vendor `BackgroundManagerService` which consults a whitelist compiled
into the framework. For a package outside it:

- a background `Service` never starts — `startService` returns without error and nothing runs;
- **`BOOT_COMPLETED` is never delivered**, so a boot receiver cannot work.

Android *starts* the HOME activity directly at boot instead of broadcasting to it, and that
path is not intercepted. So this app registers as HOME, and hands the work to a **detached
root shell script** that lives outside anything the vendor service polices.

Measured on the J1008: about 100 s from `adb reboot` to a fullscreen dashboard, unattended.

## What it does

`MainActivity` is the HOME activity. On a cold start it runs `homehq-start.sh` as root,
detached, and shows a small screen with an **Open dashboard** button so the dashboard can be
brought back without a reboot. The script then:

1. waits 20 s for the system to settle (skipped with `--now`);
2. starts `busybox httpd` on port 8080 serving `/data/local/tmp/homehq`, unless it is already
   running;
3. opens Firefox at `http://localhost:8080`;
4. waits for first paint and taps the dashboard's fullscreen gate.

`BootReceiver` is kept as a free fallback. It is blocked on this firmware and would simply
start working if the package were ever whitelisted.

Absolute paths are used throughout: `su`'s PATH starts with `/sbin`, where SuperSU ships a
stripped busybox with no `httpd` applet, and `/system/bin/busybox` on this build has no `date`
applet either.

## Prerequisites

- The dashboard built and pushed to `/data/local/tmp/homehq`, with the `httpd.conf` described
  in the device doc — without it `busybox httpd` serves `.js` as `application/octet-stream`
  and the page renders blank.
- A fullscreen gate in the page. Step 4 taps a fixed coordinate; the gate exists so that tap
  cannot land on a dashboard card and open a detail sheet. See the device doc.
- Firefox installed, and a frame with a working root `su`.

## Build

Build only. It never installs anything or touches a connected frame.

```sh
export JAVA_HOME=$(/usr/libexec/java_home)
scripts/homehq-boot/build.sh
```

Needs Android SDK `build-tools;34.0.0` and `platforms;android-34` under
`diagnostics/android-sdk` (override with `FRAME_BOOT_SDK`). The signing keystore is kept
outside the output directory on purpose, so a rebuild does not regenerate the key and trip
`INSTALL_FAILED_UPDATE_INCOMPATIBLE` on an already-installed frame.

## Install, with the owner's approval

```sh
adb push scripts/homehq-boot/homehq-start.sh /data/local/tmp/homehq-start.sh
adb shell chmod 755 /data/local/tmp/homehq-start.sh
adb install -r diagnostics/homehq-boot/homehq-boot.apk
```

Then press Home on the frame and choose **Home HQ** → **Always**. The first press may only
offer the current launcher; pick Home HQ under "Use a different app", press Home again, and
the Always option appears for it.

## Undo

`adb uninstall com.homehq.boot`, or Settings → Apps → Home HQ → Clear defaults. The HOME
chooser returns and any other launcher on the frame can be selected again.
