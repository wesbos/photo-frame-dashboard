package com.wesbos.homehq;

import android.content.ActivityNotFoundException;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

/**
 * Opens the kiosk once Android has finished booting, for frames where the kiosk can't be the Home
 * app (on a PF1506, a new Home app left the boot animation over the screen, #118). The vendor
 * Home app stays and draws first, so the boot animation ends as usual; if this ever fails, the
 * frame shows the vendor app instead of getting stuck.
 *
 * Disabled in the manifest; MainActivity turns it on, since the shell can't enable a component of a
 * release app. Android 10+ also needs the overlay permission, or the start from the background is
 * blocked:
 *   adb shell am start -n com.wesbos.homehq/.MainActivity --ez boot true
 *   adb shell appops set com.wesbos.homehq SYSTEM_ALERT_WINDOW allow
 *
 * For a site that needs a newer engine than the frame's WebView, it can open a web app installed
 * in Firefox (Firefox menu → Add app to Home screen) instead; an empty value goes back to the kiosk:
 *   adb shell am start -n com.wesbos.homehq/.MainActivity --es boot_firefox_app https://example.com/
 * Firefox shows its offline page if it opens before Wi-Fi is up, so the web app waits for a
 * working connection (at most NETWORK_WAIT_MS).
 */
public class BootReceiver extends BroadcastReceiver {
  /** Under the 60 s Android gives a background broadcast. */
  static final long NETWORK_WAIT_MS = 45_000;

  @Override
  public void onReceive(Context context, Intent intent) {
    if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;
    String app = firefoxApp(context);
    if (app.isEmpty()) {
      openKiosk(context);
      return;
    }
    PendingResult result = goAsync();
    Context appContext = context.getApplicationContext();
    whenOnline(appContext, () -> {
      if (openFirefoxApp(appContext, app)) {
        Log.i(MainActivity.TAG, "Boot completed: opened the Firefox web app " + app);
      } else {
        openKiosk(appContext);
      }
      result.finish();
    });
  }

  static void openKiosk(Context context) {
    Log.i(MainActivity.TAG, "Boot completed: opening the kiosk");
    context.startActivity(new Intent(context, MainActivity.class)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
  }

  /** Runs once the default network is validated, or after NETWORK_WAIT_MS, on the main thread. */
  static void whenOnline(Context context, Runnable run) {
    ConnectivityManager connectivity = context.getSystemService(ConnectivityManager.class);
    Handler main = new Handler(Looper.getMainLooper());
    OnlineCallback callback = new OnlineCallback(connectivity, run);
    connectivity.registerDefaultNetworkCallback(callback);
    main.postDelayed(() -> callback.finish("no connection yet, opening anyway"), NETWORK_WAIT_MS);
  }

  private static class OnlineCallback extends ConnectivityManager.NetworkCallback {
    private final ConnectivityManager connectivity;
    private final Runnable run;
    private final Handler main = new Handler(Looper.getMainLooper());
    private boolean done;

    OnlineCallback(ConnectivityManager connectivity, Runnable run) {
      this.connectivity = connectivity;
      this.run = run;
    }

    @Override
    public void onCapabilitiesChanged(Network network, NetworkCapabilities capabilities) {
      if (capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) {
        main.post(() -> finish("online"));
      }
    }

    /** Called on the main thread; only the first call runs. */
    void finish(String why) {
      if (done) return;
      done = true;
      connectivity.unregisterNetworkCallback(this);
      Log.i(MainActivity.TAG, "Boot completed: " + why);
      run.run();
    }
  }

  /** The Firefox web app saved with --es boot_firefox_app, or "" for none. */
  static String firefoxApp(Context context) {
    return context.getSharedPreferences(MainActivity.PREFS, Context.MODE_PRIVATE)
        .getString(MainActivity.PREF_BOOT_FIREFOX_APP, "");
  }

  /** Opens a web app installed in Firefox, with the intent of the shortcut Firefox pins for it. */
  static boolean openFirefoxApp(Context context, String app) {
    try {
      context.startActivity(new Intent("mozilla.components.feature.pwa.PWA_LAUNCHER", Uri.parse(app))
          .setComponent(new ComponentName("org.mozilla.firefox",
              "mozilla.components.feature.pwa.WebAppLauncherActivity"))
          .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
      return true;
    } catch (ActivityNotFoundException e) {
      Log.w(MainActivity.TAG, "Firefox is missing, can't open " + app);
      return false;
    }
  }
}
