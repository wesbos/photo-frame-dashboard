package com.photoframe.firefoxhome;

import android.app.Activity;
import android.app.AlertDialog;
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
        LauncherApps.PinItemRequest request = launcherApps == null ? null
                : launcherApps.getPinItemRequest(getIntent());
        if (request == null || !request.isValid()
                || request.getRequestType() != LauncherApps.PinItemRequest.REQUEST_TYPE_SHORTCUT) {
            finish();
            return;
        }
        ShortcutInfo shortcut = request.getShortcutInfo();
        if (shortcut == null || !HomeActivity.FIREFOX.equals(shortcut.getPackage())) {
            finish();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Use this Firefox dashboard?")
                .setMessage("Replace the current dashboard with \"" + shortcut.getShortLabel() + "\"?")
                .setPositiveButton("Use dashboard", (dialog, which) -> {
                    try {
                        if (request.isValid() && request.accept()) {
                            getSharedPreferences("home", MODE_PRIVATE).edit()
                                    .putString("shortcutPackage", shortcut.getPackage())
                                    .putString("shortcutId", shortcut.getId()).apply();
                            Toast.makeText(this, "Firefox dashboard saved", Toast.LENGTH_LONG).show();
                        }
                    } catch (IllegalStateException | SecurityException e) {
                        Toast.makeText(this, "Shortcut expired; try pinning again", Toast.LENGTH_LONG).show();
                    } finally {
                        finish();
                    }
                })
                .setNegativeButton("Cancel", (dialog, which) -> finish())
                .setOnCancelListener(dialog -> finish())
                .show();
    }
}
