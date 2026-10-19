package com.example.pf1506kiosk;

import android.app.admin.DevicePolicyManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/**
 * Admin commands, over adb only. The manifest protects this receiver with
 * android.permission.DUMP, which the adb shell holds and ordinary apps can't get, so other
 * apps on the frame can't change the page or release device owner. (MainActivity has to
 * be exported to be the home app, so it ignores intent extras.)
 *
 *   adb shell am broadcast -n com.example.pf1506kiosk/.AdminCommandReceiver --es url http://host:port/
 *   adb shell am broadcast -n com.example.pf1506kiosk/.AdminCommandReceiver --ez standalone true
 *   adb shell am broadcast -n com.example.pf1506kiosk/.AdminCommandReceiver --ez release_owner true
 */
public class AdminCommandReceiver extends BroadcastReceiver {
    static final String ACTION_APPLY = "com.example.pf1506kiosk.APPLY_SETTINGS";
    static final String PREF_RELEASE = "release_owner_pending";

    @Override public void onReceive(Context c, Intent i) {
        android.content.SharedPreferences.Editor e = c.getSharedPreferences("kiosk", Context.MODE_PRIVATE).edit();
        String url = i.getStringExtra("url");
        if (i.getBooleanExtra("standalone", false)) {
            e.putString("url", "");
        } else if (url != null && (url.startsWith("http://") || url.startsWith("https://"))) {
            e.putString("url", url);
        }
        boolean release = i.getBooleanExtra("release_owner", false);
        if (release) e.putBoolean(PREF_RELEASE, true);
        e.commit();
        // A running MainActivity applies it (it must stop lock-task mode itself)...
        c.sendBroadcast(new Intent(ACTION_APPLY).setPackage(c.getPackageName()));
        // ...and if it isn't running, release device owner here.
        if (release) {
            DevicePolicyManager dpm = c.getSystemService(DevicePolicyManager.class);
            if (dpm.isDeviceOwnerApp(c.getPackageName()) && !MainActivity.running) {
                dpm.clearDeviceOwnerApp(c.getPackageName());
                c.getSharedPreferences("kiosk", Context.MODE_PRIVATE).edit().remove(PREF_RELEASE).apply();
                Log.i("FrameKiosk", "device owner released");
            }
        }
        Log.i("FrameKiosk", "admin command applied");
    }
}
