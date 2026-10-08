# Rockchip DeviceTest Wi-Fi screens

Read the live /system/app/DeviceTest/DeviceTest.apk and decompiled it locally. Package com.DeviceTest; APK SHA-256 0c83b43170b703176537898e5807aa88ce8299469a1efb0a4f92d5aa54952c60. Private APK, resources and logs remain under diagnostics/.

Both WifiTestActivity and WifiTest2Activity enable the same Android WifiManager and call startScan. Both return immediately on empty scan results without replacing the layout's default WifiResultText, which reads Please wait for init the equipment. That message is not a reliable indication of ongoing hardware initialization.

Wi-Fi lists scanned networks and separates strong/weak signals at -35dBm; it may attempt to join an open network. Wi-Fi2 displays scan results but looks for a specific open factory network named CMW-AP for its connection test. These are two test routines, not evidence of two separate populated Wi-Fi radios.

Live log capture shows WifiTest2Activity requesting a scan at23:17:31.810 and wificond reporting Scan aborted at23:17:32.964. The factory app therefore hits the same native failure already seen in Android Settings and the Skylight app. It does not provide a separate working scan path or identify the exact abort cause. No calibration or erase action was initiated by the investigation.
