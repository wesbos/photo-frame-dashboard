package com.homehq.boot;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/**
 * Starts the dashboard after a reboot.
 *
 * This deliberately does NOT start an Android Service. The vendor firmware runs a
 * BackgroundManagerService that silently refuses services from packages outside its
 * whitelist ("not whitelist service Intent { cmp=com.homehq.boot/.StartService }"), so the
 * work is handed to a detached root shell script instead, which it does not police.
 */
public class BootReceiver extends BroadcastReceiver {

    static final String TAG = "HomeHQBoot";
    static final String SCRIPT = "/data/local/tmp/homehq-start.sh";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;
        start("");
    }

    /** Backgrounded with & so su returns at once and the receiver does not block. */
    static void start(String args) {
        String command = "sh " + SCRIPT + " " + args + " >/dev/null 2>&1 &";
        try {
            Runtime.getRuntime().exec(new String[] {"su", "-c", command});
            Log.i(TAG, "launched: " + command);
        } catch (Exception e) {
            Log.e(TAG, "could not launch " + SCRIPT, e);
        }
    }
}
