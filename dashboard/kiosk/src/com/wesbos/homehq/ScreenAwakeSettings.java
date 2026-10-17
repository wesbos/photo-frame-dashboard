package com.wesbos.homehq;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.view.WindowManager;

/** Keeps the kiosk's screen policy independent of its browser engine. */
final class ScreenAwakeSettings {
  private static final String KEY = "keep_awake";

  private static SharedPreferences preferences(Activity activity) {
    return activity.getSharedPreferences("kiosk", Activity.MODE_PRIVATE);
  }

  static void onNewIntent(Activity activity, Intent intent) {
    if (intent.hasExtra(KEY)) {
      preferences(activity).edit().putBoolean(KEY, intent.getBooleanExtra(KEY, true)).apply();
    }
    apply(activity);
  }

  static void apply(Activity activity) {
    boolean keepAwake = preferences(activity).getBoolean(KEY, true);
    if (keepAwake) {
      activity.getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    } else {
      activity.getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }
  }

  static void show(Activity activity) {
    boolean keepAwake = preferences(activity).getBoolean(KEY, true);
    new AlertDialog.Builder(activity)
        .setTitle("Screen and screensaver")
        .setSingleChoiceItems(new String[] {
            "Keep dashboard screen awake",
            "Allow Android sleep and screensaver"
        }, keepAwake ? 0 : 1, (dialog, which) -> {
          preferences(activity).edit().putBoolean(KEY, which == 0).apply();
          apply(activity);
          dialog.dismiss();
        })
        .setNegativeButton("Cancel", null)
        .show();
  }
}
