package com.photoframe.firefoxhome;

import android.app.Activity;
import android.content.pm.LauncherApps;
import android.content.pm.ShortcutInfo;
import android.os.Bundle;
import android.widget.Toast;

/**
 * Accepts a pinned-shortcut request. Firefox only offers "Add app to Home screen" when the
 * default Home app can pin shortcuts; the accepted web-app shortcut is what HomeActivity
 * launches, which opens the site full screen.
 */
public final class PinActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LauncherApps launcherApps = getSystemService(LauncherApps.class);
        LauncherApps.PinItemRequest request = launcherApps.getPinItemRequest(getIntent());
        if (request != null && request.isValid()
                && request.getRequestType() == LauncherApps.PinItemRequest.REQUEST_TYPE_SHORTCUT) {
            ShortcutInfo shortcut = request.getShortcutInfo();
            if (shortcut != null && request.accept()) {
                getSharedPreferences("home", MODE_PRIVATE).edit()
                        .putString("shortcutPackage", shortcut.getPackage())
                        .putString("shortcutId", shortcut.getId())
                        .apply();
                Toast.makeText(this, "Saved \"" + shortcut.getShortLabel()
                        + "\" as the dashboard", Toast.LENGTH_LONG).show();
            }
        }
        finish();
    }
}
