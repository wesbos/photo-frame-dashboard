# AiMOR: remote root shell over an unencrypted vendor connection

Applies to the PF1007L / Allwinner A33 frame with the AiMOR firmware.
See the [setup guide](allwinner-a33-pf1007l.md) for the device data.

## 1. Summary

The frame app `com.efercro.os.aimor` keeps a TCP connection to a vendor server.
The connection has no encryption.
The server can send command type 12009 on this connection.
The app sends the text of command 12009 to `su`.
`su` runs the text as a root shell command.

Thus, the vendor server can run any command as root on the frame.
A person who can change the traffic between the frame and the server can do the same.
The frame is then a root-controlled device on your network.

## 2. Affected software

| Item | Value |
| --- | --- |
| Firmware | `YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113` |
| App | `com.efercro.os.aimor`, version 6.0.78 (code 78) |
| App location | `/system/priv-app/launcher_aimor/` |
| App user | `android.uid.system` (uid 1000) |
| APK SHA-256 | `abc4e274940e21729de7b9dbaf1f7969efdf427955d0c4881a319611942fb65d` |
| `su` | `/system/xbin/su`, owner root, setuid (`rwsr-sr-x`) |

The app is the home screen. Android starts it at each boot.
The app has no boot receiver. It does not need one.

A later test on firmware
`YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260410`, also running AiMOR
6.0.78, used command 12009 to start temporary Wi-Fi root ADB. See the
[April firmware report and bounded helpers](pf1007l-20260410-network-adb.md).
The captured April launcher's APK was independently rehashed and matches the
January APK hash above. The executable code is stored separately in
`oat/arm/launcher_aimor.odex`; a matching APK alone does not establish identical
optimized code, boot image, or whole firmware. The April command path was also
inspected and verified through a live root-ADB session.

## 3. Server

| Item | Value |
| --- | --- |
| Host | `imsconnect.efercro.com` |
| Port | 7806/TCP |
| DNS on 2026-10-10 | CNAME to an AWS load balancer in `us-east-1` |

The app also uses these vendor HTTPS ports: 10546, 10548, 10549 and 10550.
It uses port 3478 for peer-to-peer file transfer.

## 4. Code path

All paths are in the JADX output of the app, under `com/yhk/rabbit/baselibrary/`.
The code of the app is in `oat/arm/launcher_aimor.odex`, not in the APK.
Extract the dex files from the odex before you decompile.

1. `service/CommunicationPresenter.java:572` opens the connection to port 7806.
2. `netty/NettyClient.java:88-93` sets the channel pipeline.
   The pipeline has protobuf decoders and command handlers.
   The pipeline has no TLS handler.
3. `service/CommunicationPresenter.java:725-731` handles command 12009
   (`NettyReceiveMessage.RECEIVE_SHELL_COMMAND`):

   ```java
   case NettyReceiveMessage.RECEIVE_SHELL_COMMAND /* 12009 */:
       String stringUtf11 = ProtoDemo.EduPipelineMessage.parseFrom(bArr).getMsg().toStringUtf8();
       if (!TextUtils.isEmpty(stringUtf11)) {
           FileUtils.runCommand(stringUtf11);
   ```

   The handler does not check a signature or a sender.
4. `utils/FileUtils.java:1442-1460` (`runCommand`) starts `su` and writes the text to it:

   ```java
   processExec = Runtime.getRuntime().exec("su");
   ...
   dataOutputStream.writeBytes(str + "\n");
   dataOutputStream.writeBytes("exit\n");
   ```

## 5. Other server commands on the same connection

| Code | Name in code | Function |
| --- | --- | --- |
| 12001 | `RECEIVE_UPDATE` | Start an app update. If the server sets `isSilent`, the app installs the APK with `pm install -r` through `su`. It shows no prompt. |
| 12002 | `RECEIVE_LOGCAT` | Upload logs. |
| 12003 | `RECEIVE_MODIFY_SN` | Change the serial number file and `android_id`. |
| 12004 | `RECEIVE_SWITCH_LOGCAT` | Start or stop log capture. Copy the app databases to `/sdcard/crash/` for upload. |
| 12005 | `RECEIVE_CLEAN_LOGCAT` | Delete logs. |
| 12006 | `RECEIVE_SWITCH_ADB` | Turn ADB on or off. |
| 12007 | `AEEZO_LOG_SWITCH` | Set debug properties. |
| 12008 | `RECEIVE_SWITCH_DEBUG_EXCEPTION` | Set debug properties. |
| 12009 | `RECEIVE_SHELL_COMMAND` | Run any command as root. |

## 6. Related behavior

- At each start, the app runs `setenforce 0` through `su`
  (`application/BaseApplication.java:88`). SELinux is then permissive.
- The main HTTPS client of the app accepts all server certificates
  (`com/zhy/http/okhttp/https/HttpsUtils.java`, `UnSafeTrustManager`).
- `com.DeviceTest` runs as the system user. Its receiver `EnableAppReceiver` has no permission.
  Any app can send it `android.rockchip.devicetest.action.APP_STATE_CHANGE`.
  The receiver then enables or disables the named component of any package.
- The `su` in the table above is world-executable and, unlike the AOSP `su`, does not restrict
  its callers to root and the shell, so an ordinary app uid becomes root with no prompt. Shown on
  `20260519` by dropping to an app uid first: `su 10035 /system/xbin/su 0 id` returns
  `uid=0(root)`. [pf1007l-start-here.md](pf1007l-start-here.md) warns about this (#24) and the
  [Route S report](pf1007l-macos-20260519-route-s-report.md) tightened the mode, but T8 never
  does: it closes the vendor's remote path, not the local one. Step 8 does. Other A33 frames ship
  a setuid `su` whose root is capability-stripped (#111, #122); this is about who may call the
  binary, not what it can do once called.

## 7. Check your frame

Run this command when the frame is on a network:

```sh
adb shell 'netstat -an | grep :7806'
```

A line with `ESTABLISHED` shows an open command connection.

## 8. Recommended actions

Do these steps in sequence.

1. Keep the frame off your home network until you complete step 4.
2. Block the vendor server on your router.
   Block `imsconnect.efercro.com` and outbound TCP port 7806 from the frame.
3. If you cannot change the router, add a firewall rule on the frame:

   ```sh
   adb shell 'for T in iptables ip6tables; do
     $T -N vendor_block
     $T -A vendor_block -p tcp --dport 7806 -j REJECT
     $T -A vendor_block -p tcp --dport 10546:10550 -j REJECT
     $T -A vendor_block -p tcp --dport 3478 -j REJECT
     $T -A vendor_block -p udp --dport 3478 -j REJECT
     $T -I OUTPUT 1 -j vendor_block
   done'
   adb shell am force-stop com.efercro.os.aimor
   ```

   This rule stays in memory only. A reboot removes it.
   The rule blocks ports, not hosts.
4. Install a replacement home app. Then disable AiMOR:

   ```sh
   adb shell pm disable com.efercro.os.aimor
   ```

   This step removes the command connection permanently.
   Use the procedure in section 5 of the [setup guide](allwinner-a33-pf1007l.md).
   Make sure that the new home app shows on the screen before you disable AiMOR.
5. Disable the firmware updater and the factory test app:

   ```sh
   adb shell pm disable com.yhk.qeota
   adb shell pm disable com.DeviceTest
   ```

6. Before a reboot, make sure that the change is on the disk.
   Read `/data/system/users/0/package-restrictions.xml`.
   Each disabled package must show `enabled="2"`.
7. After the reboot, do the check in section 7 again.
   The command must show no connection to port 7806.
8. Consider taking `su` away from apps, which steps 1 to 7 do not do:

   ```sh
   adb shell 'mount -o remount,rw /system && chmod 06750 /system/xbin/su \
     && sync && mount -o remount,ro /system'
   adb shell 'ls -l /system/xbin/su'                        # expect -rwsr-s---
   adb shell '/system/xbin/su 10035 /system/xbin/su 0 id'   # expect Permission denied
   ```

   Root and the `shell` group keep it, so root ADB and the scripts in this repository are
   unaffected; only apps lose it. Check the second command still returns `uid=10035` without the
   nested call, or the test proves nothing. The shipped mode is `06755`, read from a factory
   `/system` image, so `chmod 06755` is the exact undo. Do this only once you have persistent root
   ADB, and not if you rely on a root app on the frame.

## 9. Undo

- Remove the firewall rule:

  ```sh
  adb shell 'for T in iptables ip6tables; do
    $T -D OUTPUT -j vendor_block; $T -F vendor_block; $T -X vendor_block
  done'
  ```

- Enable the packages: `pm enable com.efercro.os.aimor`, `pm enable com.yhk.qeota`,
  `pm enable com.DeviceTest`.
