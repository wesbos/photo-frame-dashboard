package com.photoframe.c1nav;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        SharedPreferences preferences = getSharedPreferences(NavRestore.PREFERENCES,
                Context.MODE_PRIVATE);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int padding = (int) (24 * getResources().getDisplayMetrics().density);
        layout.setPadding(padding, padding, padding, padding);
        TextView title = new TextView(this);
        title.setText("C1 navigation restore");
        title.setTextSize(24);
        layout.addView(title);
        TextView status = new TextView(this);
        status.setTextSize(20);
        status.setText(preferences.getBoolean(NavRestore.ENABLED, false)
                ? "Boot restore is enabled. It has not been verified after reboot."
                : "Boot restore is disabled. This app has no internet access.");
        layout.addView(status);
        Button enable = new Button(this);
        enable.setText("Enable navigation restore at boot");
        enable.setOnClickListener(view -> {
            String error = NavRestore.restore(this);
            if (error != null) {
                status.setText(error);
            } else if (preferences.edit().putBoolean(NavRestore.ENABLED, true).commit()) {
                status.setText("Boot restore enabled. Check the bar now and after a reboot.");
            } else {
                status.setText("The bar was requested, but the boot preference could not be saved.");
            }
        });
        layout.addView(enable);
        Button disable = new Button(this);
        disable.setText("Disable navigation restore at boot");
        disable.setOnClickListener(view -> {
            if (preferences.edit().putBoolean(NavRestore.ENABLED, false).commit()) {
                status.setText("Boot restore disabled. The current bar setting was not changed.");
            } else {
                status.setText("The boot preference could not be saved.");
            }
        });
        layout.addView(disable);
        setContentView(layout);
    }
}
