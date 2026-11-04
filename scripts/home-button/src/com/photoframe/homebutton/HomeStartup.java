package com.photoframe.homebutton;

import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.Log;
import java.io.FileInputStream;
import java.security.MessageDigest;
import java.util.concurrent.atomic.AtomicBoolean;

/** Reload an owner-selected Auto run list on one audited Allwinner firmware. */
final class HomeStartup {
    static final String RESTORE_AUTO_RUN = "restoreAllwinnerAutoRun";
    private static final String TAG = "FrameHomeBoot";
    private static final ComponentName VENDOR = new ComponentName(
            "com.softwinner.awmanager", "com.softwinner.awmanager.GCMBroadcastReceiver");
    private static final String FINGERPRINT =
            "Allwinner/ceres_aw/ceres-aw:10/QP1A.191105.004/eng.joy.20220905.163444:eng/test-keys";
    private static final String APK_SHA256 =
            "597068b508ff2dcc8f3a3f372354d74ce05b907cdbf6c3c2a786290476538869";

    static boolean supported(Context context) {
        if (!FINGERPRINT.equals(Build.FINGERPRINT)) return false;
        try {
            android.content.pm.ActivityInfo receiver = context.getPackageManager().getReceiverInfo(VENDOR, 0);
            ApplicationInfo app = receiver.applicationInfo;
            if (!receiver.enabled || !receiver.exported || !app.enabled
                    || (app.flags & ApplicationInfo.FLAG_SYSTEM) == 0) return false;
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (FileInputStream input = new FileInputStream(app.sourceDir)) {
                byte[] buffer = new byte[8192];
                int count, total = 0;
                while ((count = input.read(buffer)) != -1) {
                    total += count;
                    if (total > 128 * 1024) return false;
                    digest.update(buffer, 0, count);
                }
            }
            StringBuilder hex = new StringBuilder();
            for (byte b : digest.digest()) hex.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
            return APK_SHA256.equals(hex.toString());
        } catch (Exception unavailable) {
            return false;
        }
    }

    private static boolean enabled(Context context) {
        return context.getSharedPreferences("home", 0).getBoolean("enabled", true)
                && Settings.canDrawOverlays(context);
    }

    static void start(Context context, int incomingFlags, Runnable finished) {
        if (!enabled(context)) { finished.run(); return; }
        try {
            if (context.startForegroundService(new Intent(context, HomeService.class)) != null) {
                finished.run();
                return;
            }
        } catch (RuntimeException rejected) {
            Log.w(TAG, "Service start rejected", rejected);
            finished.run();
            return;
        }
        if (!context.getSharedPreferences("home", 0).getBoolean(RESTORE_AUTO_RUN, false)
                || !supported(context)) {
            Log.w(TAG, "Boot service refused; check this firmware's per-app Auto run settings");
            finished.run();
            return;
        }
        Handler handler = new Handler(Looper.getMainLooper());
        AtomicBoolean complete = new AtomicBoolean();
        Runnable done = () -> {
            if (complete.compareAndSet(false, true)) {
                handler.removeCallbacksAndMessages(null);
                finished.run();
            }
        };
        handler.postDelayed(() -> {
            Log.w(TAG, "Saved Auto run restore timed out");
            done.run();
        }, 5000);
        // The audited receiver ignores this action. Its Application reloads the saved
        // user list; no registration extra or new allow-list entry is supplied.
        Intent restore = new Intent("com.photoframe.homebutton.RESTORE_AUTO_RUN").setComponent(VENDOR);
        // Do not enqueue behind the boot broadcast whose PendingResult we hold.
        if ((incomingFlags & Intent.FLAG_RECEIVER_FOREGROUND) == 0)
            restore.addFlags(Intent.FLAG_RECEIVER_FOREGROUND);
        try {
            context.sendOrderedBroadcast(restore, null, new BroadcastReceiver() {
                private int attempts;
                private void retry() {
                    if (complete.get()) return;
                    if (!enabled(context)) { done.run(); return; }
                    attempts++;
                    try {
                        ComponentName started = context.startForegroundService(new Intent(context, HomeService.class));
                        if (started != null) {
                            Log.i(TAG, "Home service started after saved Auto run restore");
                            done.run();
                            return;
                        }
                    } catch (RuntimeException rejected) {
                        Log.w(TAG, "Service start rejected after restore", rejected);
                        done.run();
                        return;
                    }
                    if (attempts < 3) handler.postDelayed(this::retry, attempts * 600L);
                    else {
                        Log.w(TAG, "Service still refused; verify the saved Auto run choice");
                        done.run();
                    }
                }
                @Override public void onReceive(Context ignored, Intent result) {
                    handler.postDelayed(this::retry, 200);
                }
            }, handler, 0, null, null);
        } catch (RuntimeException unavailable) {
            Log.w(TAG, "Saved Auto run restore unavailable", unavailable);
            done.run();
        }
    }
}
