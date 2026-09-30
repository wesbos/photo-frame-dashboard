package com.wesbos.homehq;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * Full-screen kiosk WebView for the Home HQ wall tablet.
 * - Remote debugging is on, so Chrome DevTools can attach over ADB.
 * - Immersive mode hides the status + navigation bars (true 1280x800).
 * - Launch with a URL: adb shell am start -a android.intent.action.VIEW -d <url> com.wesbos.homehq
 */
public class MainActivity extends Activity {
  static final String DEFAULT_URL = "https://home-dashboard.wesbos.workers.dev/";
  private WebView web;

  @Override
  protected void onCreate(Bundle state) {
    super.onCreate(state);
    WebView.setWebContentsDebuggingEnabled(true);
    getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
        | WindowManager.LayoutParams.FLAG_FULLSCREEN);

    web = new WebView(this);
    WebSettings s = web.getSettings();
    s.setJavaScriptEnabled(true);
    s.setDomStorageEnabled(true);
    s.setUseWideViewPort(true);
    s.setMediaPlaybackRequiresUserGesture(false);
    web.setWebViewClient(new WebViewClient()); // keep navigation inside the kiosk
    setContentView(web);

    String url = getIntent().getDataString();
    web.loadUrl(url != null ? url : DEFAULT_URL);
  }

  @Override
  protected void onNewIntent(Intent intent) {
    super.onNewIntent(intent);
    String url = intent.getDataString();
    if (url != null) web.loadUrl(url);
  }

  @Override
  public void onWindowFocusChanged(boolean hasFocus) {
    super.onWindowFocusChanged(hasFocus);
    if (hasFocus) hideSystemUi();
  }

  private void hideSystemUi() {
    getWindow().getDecorView().setSystemUiVisibility(
        View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
  }

  @Override
  public void onBackPressed() {
    if (web.canGoBack()) web.goBack();
  }
}
