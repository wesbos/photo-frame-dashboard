package com.photoframe.homebutton;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class HomeSettingsActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int padding = (int)(24 * getResources().getDisplayMetrics().density);
        layout.setPadding(padding, padding, padding, padding);
        TextView instructions = new TextView(this);
        instructions.setText("Tap the floating house to return to Home. Drag it to move it.\n"
                + "The button starts automatically after a reboot. This app has no internet permission.");
        instructions.setTextSize(22);
        layout.addView(instructions);
        if (HomeStartup.supported(this)) {
            CheckBox restore = new CheckBox(this);
            restore.setText("Reload saved Allwinner Auto run settings at boot");
            restore.setChecked(getSharedPreferences("home", 0)
                    .getBoolean(HomeStartup.RESTORE_AUTO_RUN, false));
            restore.setOnCheckedChangeListener((view, checked) -> getSharedPreferences("home", 0)
                    .edit().putBoolean(HomeStartup.RESTORE_AUTO_RUN, checked).apply());
            layout.addView(restore);
        }
        Button show = new Button(this);
        show.setText("Show Home button");
        show.setOnClickListener(view -> {
            getSharedPreferences("home", 0).edit().putBoolean("enabled", true).apply();
            if (Settings.canDrawOverlays(this)) {
                HomeStartup.start(this, 0, () -> {});
            } else {
                startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:" + getPackageName())));
            }
        });
        layout.addView(show);
        Button hide = new Button(this);
        hide.setText("Hide Home button");
        hide.setOnClickListener(view -> {
            getSharedPreferences("home", 0).edit().putBoolean("enabled", false).apply();
            stopService(new Intent(this, HomeService.class));
        });
        layout.addView(hide);
        Button home = new Button(this);
        home.setText("Go to Home");
        home.setOnClickListener(view -> {
            startActivity(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME));
            finish();
        });
        layout.addView(home);
        setContentView(layout);
    }
}
