# Akimart ZN-DP013 15.6" Digital Photo Frame (32GB Variant)

The Akimart ZN-DP013 is a 15.6-inch white-label display running Frameo on a Rockchip RK3326 chip. Unlike the heavily locked-down ZN-DP1501 variants often found in community hardware troubleshooting threads, the ZN-DP013 features fully functional internal data traces on its physical USB port interface, allowing for a clean, native developer pathway out of the box.

Follow this configuration path to safely isolate your network, unlock wireless ADB layers, verify your underlying architecture properties, fix the internal system WebView, and preserve system settings against automated manufacturer updates.

## Prerequisites

1. **A Reliable Phone Data Cable:** A standard USB-A to USB-C sync cable sourced from a modern smartphone (Samsung, Pixel, OnePlus, etc.). Do not use a straight USB-C to USB-C cord due to unstable Power Delivery negotiation layers on this chip.
2. **Android SDK Platform Tools:** Ensure the basic adb software packages are installed on your host computer.
3. **Python 3.x (Optional Fallback):** Only required if you run into a rare hardware timing loop and need to deploy the polling script.

---

## Step 1: Network Isolation & Unlocking the Developer Interface

To guarantee the frame does not pull down a silent background manufacturer update before you can disable the update services, you must isolate the device from the internet during initialization.

1. **Air-Gap the Setup:** Turn on the digital frame. When prompted during the initial setup wizard, **skip the Wi-Fi connection step entirely**. 
2. **Secondary Safeguard:** If your specific firmware build insists on a Wi-Fi link to proceed, connect the frame to a temporary Wi-Fi Access Point configured with a deliberately **invalid default gateway**. This tricks the frame into establishing a local connection without giving it internet access.
3. Open the main **Settings** menu.
4. Scroll down and tap on **Join Beta Program**. 
5. Enabling this mode exposes the hidden native development controls, showing a radio button to enable **ADB Access**. Toggle this setting to **ON**.

---

## Step 2: Running the Connection Check
1. Connect your phone data cable directly from a standard USB-A port on your PC to the USB-C slot on the side of the frame.
2. Open a terminal prompt on your computer and evaluate the hardware connection list:
    * `adb devices`
3. Look at your frame's display screen and accept the standard RSA Security permission window to permanently authenticate the connection loop.

### Optional Fallback: Intercepting Volatile Connection Timings (Untested Workaround)
*Note: The author connected instantly without this issue on the ZN-DP013. This fallback is strictly provided as a suggested, untested workaround if your specific host computer drops data streams before catching the frame interface.*

Create a script named **usb_watcher.py** with the following code if needed:

    import subprocess, time
    print("Polling system USB lanes... Rapidly cycle the ADB toggle on your frame screen!")
    subprocess.run(["adb", "kill-server"])
    subprocess.run(["adb", "start-server"])
    while True:
        try:
            stream = subprocess.check_output(["adb", "devices"]).decode("utf-8").strip().split("\n")
            if len(stream) > 1 and stream.strip() != "":
                print(f"\n?? Hardware link captured! Fixing bridge connections...")
                if "unauthorized" in stream:
                    subprocess.run(["adb", "kill-server"])
                    subprocess.run(["adb", "devices"])
                else: break
        except Exception: pass
        time.sleep(0.02)

Run **python usb_watcher.py** in your terminal and quickly flip the frame's ADB Access toggle switch OFF and ON continuously until the security confirmation window locks onto the screen.

---

## Step 3: Migrating Permanently to Wireless ADB
To avoid hanging long data wires from a wall-mounted dashboard console, immediately hand off the communication pathways to your local network infrastructure.

1. While the device is actively verified via the initial USB bridge connection, set the network listener port flags:
    * `adb tcpip 5555`
2. Safely unplug the physical data cable from your computer.
3. If you skipped Wi-Fi earlier, you can now safely connect the frame to your home network. Look up its active local address inside Settings -> Wi-Fi (e.g., 192.168.1.45).
4. Establish your clean wireless terminal link:
    * `adb connect YOUR_FRAME_IP:5555`
*Note: This internal networking state successfully survives hard power drops and system reboots. You do not need to reproduce the physical cable initialization sequence unless your network architecture drops out or reassigns the frame's network IP address.*

---

## Step 4: Extracting and Backing Up the Stock Frameo APK (Safety Net)

Before breaking out of the manufacturer's jail or running package restrictions, pull a complete compiled copy of the factory photo framework application directly onto your computer. This creates a bulletproof local restore package in case a future system wipe or recovery reset leaves the device without its core interface assets.

1. **Locate the Application Path:** Find the physical path where the active Frameo application file is stored on the device's internal storage layer:
    * `adb shell pm path net.frameo.frame`
    * *Expected Output:* `package:/data/app/net.frameo.frame-xxxxxx/base.apk` (where `xxxxxx` is a unique system-generated alphanumeric string).

2. **Download the Backup Package:** Download the base application file directly to your host computer's active directory, renaming it cleanly to identify it later:
    * `adb pull /data/app/net.frameo.frame-xxxxxx/base.apk net.frameo.frame.apk`
    * *Verification Target:* Once the download stream wraps up, check the file properties on your computer. The completed backup file should register on your hard drive at exactly **64,040,990 bytes**. Your safety net is now fully established.


## Step 5: System Architecture & WebView Verification

Before making modifications to application spaces, open an elevated shell to evaluate system properties. 

1. Drop into the active network command shell:
    * `adb shell`
2. Request administrator context permissions:
    * `su`
    * *The prompt signature will immediately switch to a standard # marker, confirming root access.*
3. Run these environment diagnostic calls to map your firmware profile:
    * `getprop ro.board.platform`
    * `getprop ro.build.version.release`
    * `dumpsys package com.google.android.webview | grep versionName`

### Expected Verified Log Targets
* **Platform:** rk3326
* **Android Version:** 8.1.0
* **WebView Engine Version:** Blank / Returns Error Status

### Resolving the Hidden WebView Situation
If checking the com.google.android.webview package returns an empty or error state, it is because Android Oreo on this firmware build has suppressed the standalone Google WebView engine package in favor of the stock system core. If you notice your custom dashboard layouts or web applications failing to compile or display right, you must explicitly enable the web rendering framework manually via your root shell:
* `pm enable com.google.android.webview`

---

## Step 6: Breaking the Manufacturer Jail & Disabling Stock Shells

**CRITICAL WARNING:** Before running the following disable commands to shut down the stock photo shell, ensure you have already installed a custom application runner or alternate kiosk launcher package (such as Nova Launcher, Fully Kiosk, or WallPanel) onto the device using *adb install path/to/app.apk*. If you drop the stock user interface layer without another environment ready to receive system intents, your screen will go entirely blank.

1. **Locating Hidden Update Packages:** White-label hardware brands frequently distribute hidden background update engines under varying package signatures. Run a targeted grep query inside your root shell to identify the exact update daemons on your device:
    * `pm list packages | grep -E "update|ota|fota|card"`
    * *Expected Output on ZN-DP013:*
        * `package:com.adups.fota`
        * `package:android.rockchip.update.service`
        * `package:com.android.dreams.phototable`

2. **Neutralizing Over-The-Air (OTA) Tasks:** Freeze the discovered automatic updating services to safeguard your permanent development access and prevent the manufacturer from pushing silent background firmware patches:
    * `pm disable-user --user 0 com.adups.fota`
    * `pm disable-user --user 0 android.rockchip.update.service`

3. **Terminating the Primary UI:** To drop the frame out of its standard commercial environment loop, apply the same user-scoped landscape configuration flag against the underlying net.frameo.frame target:
    * `pm disable-user --user 0 net.frameo.frame`
    * *The stock Frameo interface will immediately vanish from your photo frame's physical display panel, turning the machine over to your custom dashboard environment.*

---

## Step 7: Deep Storage Optimization & Secure Session Teardown

Since the stock applications have been frozen and the environment layers migrated over to your wireless console loop, execute this specific root optimization routine to flush application memory and clean up file indexing configurations without altering the device's system hooks.

1. **Evaluating Cache Structure Stability:** Running a deep verification pass via `ls -lR` on this specific ZN-DP013 build reveals that the `/cache` partition does not hold hidden manufacturer update debris or bloating installation setups. Instead, it is cleanly populated with essential system links and native recovery structures. Do **NOT** run destructive recursive directory deletion commands like `rm -rf /cache/*`, as wiping these core layout nodes can destabilize recovery pathways.

2. **Executing Safe, Targeted Storage Maintenance:** To safely optimize file spaces without touching any of the filesystem anchors or core system components, run only these two targeted commands inside your root shell to clear out active database profiles and organize the internal flash disk sectors:
    * `pm clear net.frameo.frame`
    * `vdc fstrim dotrim`
    * *Success Check:* The system will clear out residual frame databases and runtime application configurations, while the `vdc fstrim` call forces the low-level flash chip controller to index dead block space, keeping navigation and rendering processing speeds high over time.

3. **Secure Disconnection Routine:** Once the optimization parameters match target baselines, exit the internal administrator context loops sequentially and sever your local computer bridge:
    * `exit`
    * `exit`
    * `adb disconnect`
    * *Note:* The terminal session will cleanly shut down over your local Wi-Fi interface. Your PC is now completely detached from the frame, and your custom launcher dashboard has exclusive control of the 15.6" physical screen matrix.

---

## Step 8: Clean Restoration & Safe Factory Reset

If you ever want to reconfigure your unit back into a standard digital frame for decorative use, or if a dashboard script misbehaves and locks user interface components, you can reverse your system footprints safely.

1. **Re-establish the Physical Link:** Because the wireless terminal bridges were severed in the previous step, you cannot connect over Wi-Fi out of nowhere. Connect your phone data cable directly from a standard USB-A port on your PC to the USB-C slot on the side of the frame.
2. Verify the hardware connection list is tracking cleanly:
    * `adb devices`
3. **Reinstalling the Stock Application Framework (If Wiped):** If a recovery wipe or system reset has removed the factory user interface entirely, push your locally stored backup file from Step 4 back onto the frame from your computer terminal:
    * `adb install net.frameo.frame.apk`
4. Open the internal system console line and elevate your session to root status:
    * `adb shell`
    * `su`
    * *The prompt signature will switch to a standard # marker, confirming active administrator clearance.*
5. Run these package restoration lines sequentially inside your active root shell to restore the factory default settings:
    * `pm enable com.adups.fota`
    * `pm enable android.rockchip.update.service`
    * `pm enable-user --user 0 net.frameo.frame`
6. **Hardware Recovery Loop Fallback:** Alternatively, if a custom background layout script misbehaves so severely that it breaks user interface rendering entirely and freezes your command layer access, you can force an independent hardware wipe right from your computer's terminal box:
    * `adb reboot recovery`
    * *Note:* The motherboard will immediately shut down and start up inside the native Android system recovery menu console. You can plug a standard wired USB keyboard into the frame's USB port to navigate the options, choose the "Wipe data/factory reset" instruction, and return the entire frame back to clean out-of-the-box condition.
