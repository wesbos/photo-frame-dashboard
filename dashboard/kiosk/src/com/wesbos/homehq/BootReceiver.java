package com.wesbos.homehq;

import android.content.ActivityNotFoundException;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/**
 * Opt-in BOOT_COMPLETED launch for frames that must retain their vendor Home app. The kiosk
 * already retries its saved URL if Wi-Fi is late, so the receiver does not wait for a network,
 * start a service, or hold an asynchronous broadcast. Disabled by default in the manifest.
 */
public class BootReceiver extends BroadcastReceiver {
  @Override
  public void onReceive(Context context, Intent intent) {
    if (intent == null || !Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;
    try {
      context.startActivity(new Intent(context, MainActivity.class)
          .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
      Log.i(MainActivity.TAG, "Boot completed: opening the kiosk");
    } catch (ActivityNotFoundException | SecurityException e) {
      // Leave the vendor Home visible if the kiosk cannot start. Never change the default Home.
      Log.w(MainActivity.TAG, "Boot completed: kiosk launch unavailable");
    }
  }
}
