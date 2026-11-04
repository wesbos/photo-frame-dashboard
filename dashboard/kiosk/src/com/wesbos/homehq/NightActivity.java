package com.wesbos.homehq;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;

/** Opt-in static black window; touch stays available and daytime brightness is unchanged. */
public final class NightActivity extends Activity {
  private boolean leaving;

  @Override protected void onCreate(Bundle state) {
    super.onCreate(state);
    getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
        | WindowManager.LayoutParams.FLAG_FULLSCREEN);
    WindowManager.LayoutParams attributes = getWindow().getAttributes();
    attributes.screenBrightness = WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_OFF;
    attributes.buttonBrightness = WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_OFF;
    getWindow().setAttributes(attributes);
    View black = new View(this);
    black.setBackgroundColor(Color.BLACK);
    black.setContentDescription(getString(R.string.night_description));
    // Use Android's click handling for touch, keyboard and accessibility activation.
    black.setFocusable(true);
    black.setOnClickListener(view -> returnToDashboard());
    setContentView(black);
    immersive();
  }

  private void immersive() {
    getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN
        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
  }

  @Override public void onWindowFocusChanged(boolean focused) {
    super.onWindowFocusChanged(focused);
    if (focused) immersive();
  }

  @Override protected void onResume() {
    super.onResume();
    // Hide the bright floating controls over this native Home HQ window too.
    NavigationService.setDashboardVisible(true);
  }

  @Override protected void onPause() {
    NavigationService.setDashboardVisible(false);
    super.onPause();
  }

  @Override protected void onStop() {
    super.onStop();
    // A morning command may open MainActivity directly. Do not leave a stale night task behind.
    finishAndRemoveTask();
  }

  @Override public void onBackPressed() { returnToDashboard(); }

  private void returnToDashboard() {
    if (leaving) return;
    leaving = true;
    // No URL extra: returning must preserve the current page and saved dashboard URL.
    startActivity(new Intent(this, MainActivity.class)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP));
    finishAndRemoveTask();
  }
}
