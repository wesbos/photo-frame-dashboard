package com.photoframe.c1nav;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public final class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (intent == null || !Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;
        if (!context.getSharedPreferences(NavRestore.PREFERENCES, Context.MODE_PRIVATE)
                .getBoolean(NavRestore.ENABLED, false)) return;
        String error = NavRestore.restore(context);
        if (error == null) {
            Log.i("C1NavRestore", "Boot navigation setting verified");
        } else {
            Log.w("C1NavRestore", error);
        }
    }
}
