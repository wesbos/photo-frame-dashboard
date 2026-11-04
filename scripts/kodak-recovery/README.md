# Kodak Recovery

Recovery app for Kodak RCF-1018W, Android model `RCF-1018`, firmware `QY10V1.0.1`. See the [device guide](../../docs/kodak-rcf1018w.md).

## Use

1. Install `diagnostics/kodak-recovery.apk` through ApkInstaller from a FAT32 microSD card.
2. Open **Kodak Recovery → Check root**.
3. If System UI is disabled, select **Enable System UI → Enable**.
4. Open **USB debugging**, enable it, connect the Mac using a USB-A to USB-C data cable, and approve the computer.

The root commands are `/system/xbin/su -c id` and `su -c 'pm enable com.android.systemui'`. Each has a 10-second timeout. Enabling requires a successful root check, the exact tested model/fingerprint, disabled override 2, and confirmation. The original override is saved in private preferences. Keep System UI enabled afterward.

## Build

Requires JDK 17, Android SDK platform 34/build-tools 34.0.0, Bash, and zip. On macOS:

```sh
brew install openjdk@17
brew install --cask android-commandlinetools
```

Fish environment:

```fish
set -gx JAVA_HOME (brew --prefix openjdk@17)/libexec/openjdk.jdk/Contents/Home
fish_add_path "$JAVA_HOME/bin"
set -gx ANDROID_HOME (brew --prefix)/share/android-commandlinetools
```

From the repository root:

```sh
sdkmanager --sdk_root="$ANDROID_HOME" "platforms;android-34" "build-tools;34.0.0"
bash scripts/kodak-recovery/build.sh
adb install -r diagnostics/kodak-recovery.apk
```

Review the SDK license prompts. The build retains one APK and removes temporary compiler output. It signs with the local Android debug key. Paths can be overridden with `ANDROID_HOME`, `BUILD_TOOLS`, `KODAK_APK_OUT`, and `KODAK_KEYSTORE` (debug-style password `android`).

Version 2.0/code 5, label **Kodak Recovery**, package `local.kodak.adbcheck` for in-place updates. No requested Android permissions. Ordinary apps can obtain root on this firmware; install trusted software only.
