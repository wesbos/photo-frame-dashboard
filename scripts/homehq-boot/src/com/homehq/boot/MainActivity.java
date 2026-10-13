package com.homehq.boot;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * The frame's HOME activity, and the whole point of this app: Android launches HOME at boot,
 * which is how the dashboard gets started on a firmware that blocks BOOT_COMPLETED.
 *
 * It stays on screen behind the browser so pressing Home lands somewhere sensible, with a
 * button to bring the dashboard back without a reboot. The UI is built in code so the app
 * needs no resource files.
 */
public class MainActivity extends Activity {

    private static final int BACKGROUND = Color.parseColor("#F2EEE6");
    private static final int INK = Color.parseColor("#1A1A1A");
    private TextView status;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(buildUi());

        // Only on a cold start, which at boot is the real one. The script's own delay lets
        // the system settle before it opens the browser.
        if (state == null) {
            BootReceiver.start("");
            status.setText("Starting the dashboard…");
        }
    }

    private View buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setBackgroundColor(BACKGROUND);

        TextView title = new TextView(this);
        title.setText("Home HQ");
        title.setTextColor(INK);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 34);
        title.setGravity(Gravity.CENTER);

        status = new TextView(this);
        status.setText("Ready");
        status.setTextColor(INK);
        status.setAlpha(0.6f);
        status.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        status.setGravity(Gravity.CENTER);
        status.setPadding(0, 16, 0, 40);

        Button open = new Button(this);
        open.setText("Open dashboard");
        open.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                // --now skips the boot delay: the system is clearly already up.
                BootReceiver.start("--now");
                status.setText("Opening…");
            }
        });

        root.addView(title);
        root.addView(status);
        root.addView(open);
        return root;
    }
}
