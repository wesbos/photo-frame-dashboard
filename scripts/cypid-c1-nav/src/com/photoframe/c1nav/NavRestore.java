package com.photoframe.c1nav;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import android.provider.Settings;

final class NavRestore {
    static final String PREFERENCES = "c1_navigation";
    static final String ENABLED = "restore_on_boot";
    private static final String FINGERPRINT =
            "Allwinner/a537_pro_arm64/a537-pro:15/AP3A.241105.008/26080114:user/release-keys";
    private static final String DISPLAY = "C1_216_SY15_20260801";
    private static final String STATE = "navigationbars_state";
    private static final int SHOW_NAVIGATION_BAR = 1;

    private NavRestore() {}

    static String restore(Context context) {
        if (!"C1".equals(Build.MODEL) || !DISPLAY.equals(Build.DISPLAY)
                || !FINGERPRINT.equals(Build.FINGERPRINT)) {
            return "Unsupported device or firmware; no setting changed.";
        }
        if (context.checkSelfPermission(Manifest.permission.WRITE_SECURE_SETTINGS)
                != PackageManager.PERMISSION_GRANTED) {
            return "WRITE_SECURE_SETTINGS is not granted; no setting changed.";
        }
        try {
            if (Settings.Global.getInt(context.getContentResolver(), STATE, 0)
                    != SHOW_NAVIGATION_BAR
                    && !Settings.Global.putInt(context.getContentResolver(), STATE,
                            SHOW_NAVIGATION_BAR)) {
                return "Android refused the navigation setting.";
            }
            if (Settings.Global.getInt(context.getContentResolver(), STATE, 0)
                    != SHOW_NAVIGATION_BAR) {
                return "Navigation setting did not remain enabled.";
            }
            return null;
        } catch (SecurityException denied) {
            return "Android denied the navigation setting.";
        }
    }
}
