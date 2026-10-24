package com.photoframe.firefoxhome;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.LauncherApps;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Process;
import android.provider.Settings;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * A Home activity that opens one URL in Firefox. Some vendor builds block BOOT_COMPLETED and
 * background services for apps outside a whitelist, but Android always starts the Home activity,
 * so this is the one route that runs at boot. It starts no service and needs no root.
 */
public final class HomeActivity extends Activity {
    static final String FIREFOX = "org.mozilla.firefox";
    static final String VIEW_PWA = "mozilla.components.feature.pwa.VIEW_PWA";
    static final int COUNTDOWN_SECONDS = 10;
    static final int NETWORK_WAIT_SECONDS = 120;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView status;
    private int remaining;
    private int waited;
    private boolean cancelled;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        saveUrlFromIntent(getIntent());
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int padding = (int)(32 * getResources().getDisplayMetrics().density);
        layout.setPadding(padding, padding, padding, padding);
        status = new TextView(this);
        status.setTextSize(24);
        layout.addView(status);
        addButton(layout, "Open dashboard now", () -> openDashboard());
        addButton(layout, "Android settings", () -> open(new Intent(Settings.ACTION_SETTINGS)));
        addButton(layout, "Wi-Fi settings", () -> open(new Intent(Settings.ACTION_WIFI_SETTINGS)));
        addButton(layout, "Firefox", () -> open(getPackageManager().getLaunchIntentForPackage(FIREFOX)));
        setContentView(layout);
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        saveUrlFromIntent(intent);
    }

    @Override protected void onResume() {
        super.onResume();
        cancelled = false;
        waited = 0;
        remaining = COUNTDOWN_SECONDS;
        handler.removeCallbacksAndMessages(null);
        handler.post(this::tick);
    }

    @Override protected void onPause() {
        super.onPause();
        handler.removeCallbacksAndMessages(null);
    }

    private void addButton(LinearLayout layout, String label, Runnable action) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(20);
        button.setOnClickListener(view -> {
            cancelled = true;
            handler.removeCallbacksAndMessages(null);
            action.run();
        });
        layout.addView(button);
    }

    private void tick() {
        if (cancelled) return;
        String url = url();
        if (hasShortcut()) url = "Firefox web app (" + (url.isEmpty() ? "pinned shortcut" : url) + ")";
        if (url.isEmpty()) {
            status.setText("No dashboard URL set. Over ADB:\n"
                    + "am start -n " + getPackageName() + "/.HomeActivity --es url https://...");
            return;
        }
        if (!networkUp() && waited < NETWORK_WAIT_SECONDS) {
            waited++;
            status.setText("Waiting for the network (" + waited + " s)\n" + url);
            handler.postDelayed(this::tick, 1000);
            return;
        }
        if (remaining > 0) {
            status.setText("Opening the dashboard in " + remaining + " s\n" + url
                    + "\n\nTap a button to stop.");
            remaining--;
            handler.postDelayed(this::tick, 1000);
            return;
        }
        openDashboard();
    }

    private void openDashboard() {
        // A web-app shortcut pinned by Firefox (see PinActivity) opens the site full screen.
        String shortcutPackage = prefs().getString("shortcutPackage", null);
        String shortcutId = prefs().getString("shortcutId", null);
        if (shortcutPackage != null && shortcutId != null) {
            try {
                getSystemService(LauncherApps.class).startShortcut(
                        shortcutPackage, shortcutId, null, null, Process.myUserHandle());
                return;
            } catch (RuntimeException e) {
                // Shortcut removed or Firefox reinstalled: fall through to the URL.
            }
        }
        Uri uri = Uri.parse(url());
        // Firefox opens an installed web app (https only) with no toolbar from VIEW_PWA;
        // otherwise fall back to an ordinary Firefox tab, then to any browser.
        if (open(new Intent(VIEW_PWA, uri).setPackage(FIREFOX))) return;
        if (open(new Intent(Intent.ACTION_VIEW, uri).setPackage(FIREFOX))) return;
        open(new Intent(Intent.ACTION_VIEW, uri));
    }

    private boolean open(Intent intent) {
        if (intent == null) return false;
        try {
            startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            return true;
        } catch (ActivityNotFoundException e) {
            return false;
        }
    }

    private boolean networkUp() {
        ConnectivityManager cm = getSystemService(ConnectivityManager.class);
        NetworkInfo info = cm == null ? null : cm.getActiveNetworkInfo();
        return info != null && info.isConnected();
    }

    private SharedPreferences prefs() {
        return getSharedPreferences("home", MODE_PRIVATE);
    }

    private boolean hasShortcut() {
        return prefs().getString("shortcutId", null) != null;
    }

    private String url() {
        return prefs().getString("url", "");
    }

    private void saveUrlFromIntent(Intent intent) {
        String url = intent == null ? null : intent.getStringExtra("url");
        if (url != null) prefs().edit().putString("url", url.trim()).apply();
    }
}
