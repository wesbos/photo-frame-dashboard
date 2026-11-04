package com.wesbos.homehq;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.SslErrorHandler;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Full-screen kiosk WebView for the Home HQ wall tablet.
 * - Immersive mode hides the status + navigation bars (true 1280x800).
 * - Controls: hold two fingers still on the screen for 1.5s for launcher/settings/Wi-Fi/reload.
 *   Optional single-tap Menu button: launch with --ez menu_button true (false removes it).
 * - Offline: a failed page load shows a native screen instead of WebView's error page (which
 *   prints the full URL, including any token in it). With no Wi-Fi it offers Wi-Fi settings.
 * - Remote debugging is OFF unless launched with the debug extra (every app on this device
 *   gets root, so the devtools socket should only exist while actively debugging):
 *     adb shell am start -n com.wesbos.homehq/.MainActivity --ez debug true
 * - Launch with a URL: adb shell am start -a android.intent.action.VIEW -d <url> -n com.wesbos.homehq/.MainActivity
 * - Set the saved URL, used on every later launch: adb shell am start -n com.wesbos.homehq/.MainActivity --es url <url>
 * - A site bundled at build time (KIOSK_SITE) is answered at http://127.0.0.1:8765/ from the
 *   APK's assets/site/, with no server; every other URL goes to the network as usual.
 * - Offer the kiosk as a Home app (--ez home false undoes it), then pick it:
 *     adb shell am start -n com.wesbos.homehq/.MainActivity --ez home true
 *     adb shell cmd package set-home-activity com.wesbos.homehq/.Home
 * - Wi-Fi with a sign-in page (captive portal): when the dashboard can't load on Wi-Fi, the kiosk
 *   checks for one and shows it, so the terms can be accepted; then it returns to the dashboard.
 */
public class MainActivity extends Activity {
  static final String TAG = "HomeHQ";
  static final String DEFAULT_URL = "https://home-dashboard.wesbos.workers.dev/";
  static final String PREFS = "kiosk";
  static final String PREF_URL = "url";
  static final String PREF_MENU_BUTTON = "menu_button";
  static final String PREF_BOOTANIM_EXIT = "bootanim_exit";
  static final long EXIT_HOLD_MS = 1500;
  static final int CANCEL_POINTER_IDS = 10; // touch ids 0-9
  static final long RETRY_MS = 5000;
  static final long STALL_MS = 15000;
  static final long NAV_CHECK_MS = 5000;
  static final long NAV_REBIND_MS = 1000;
  static final float EXIT_SLOP_PX = 60;
  static final String LOCAL_HOST = "127.0.0.1";
  static final int LOCAL_PORT = 8765;
  static final String LOCAL_ASSETS = "site";
  // Android's own captive portal check: 204 when online, anything else when a portal answers.
  // Plain HTTP so a portal can redirect it, and so it works before the clock is set.
  static final String PORTAL_PROBE = "http://connectivitycheck.gstatic.com/generate_204";
  static final int PROBE_TIMEOUT_MS = 10000;
  static final long PORTAL_CHECK_MS = 5000;
  static final long PORTAL_GIVE_UP_MS = 10 * 60 * 1000;
  static final int PROBE_ONLINE = 0, PROBE_PORTAL = 1, PROBE_FAILED = 2;
  static final long TIME_NUDGE_MS = 60 * 1000;

  private WebView web;
  private Button menuButton;
  private final Handler handler = new Handler(Looper.getMainLooper());
  // Not cleared in onDestroy, so a navigation rebind that has started always finishes.
  private final Handler rebindHandler = new Handler(Looper.getMainLooper());
  private final int[] exitIds = new int[2];
  private final float[] exitX = new float[2];
  private final float[] exitY = new float[2];
  private boolean exitArmed;
  private String retryUrl;
  private String mainUrl;
  private boolean pageFailed;
  // A retry is queued: keep the offline screen up until it runs, even if the failed load "finishes".
  private boolean retryPending;
  private LinearLayout offline;
  private TextView offlineTitle, offlineText;
  private Button signIn;
  // Captive portal: found by the last probe, on screen, closed by the owner, or its page failed.
  private boolean probing, portalFound, portalMode, portalDismissed, portalFailed;
  private long portalSince;
  private long lastTimeNudge = -TIME_NUDGE_MS;
  private LinearLayout portalBar;
  private TextView portalText;

  private final Runnable retry = new Runnable() {
    @Override
    public void run() {
      retryPending = false;
      if (retryUrl == null) return;
      load(retryUrl);
      // A retry started while Wi-Fi is joining can hang for about a minute with no error and no
      // finish, so no further retry is posted. Start a new one if it is still pending.
      handler.removeCallbacks(stall);
      handler.postDelayed(stall, STALL_MS);
    }
  };

  private final Runnable stall = new Runnable() {
    @Override
    public void run() {
      if (retryUrl == null || offline.getVisibility() != View.VISIBLE) return;
      Log.w(TAG, "Retry still pending after " + STALL_MS + " ms, starting a new one");
      retry.run();
    }
  };

  // On frames that start Wi-Fi after boot, the error screen is up when Wi-Fi connects. Retry then,
  // and correct the "Connect to Wi-Fi?" text, instead of waiting for the next error.
  private final BroadcastReceiver networkChange = new BroadcastReceiver() {
    @Override
    public void onReceive(Context context, Intent intent) {
      if (retryUrl == null || offline.getVisibility() != View.VISIBLE || !wifiConnected()) return;
      Log.i(TAG, "Wi-Fi connected or clock changed, retrying now");
      showOffline();
      handler.removeCallbacks(retry);
      handler.removeCallbacks(stall);
      retryPending = true;
      handler.post(retry);
    }
  };

  // While the sign-in page is up, check every few seconds whether the frame is online yet.
  private final Runnable portalCheck = this::checkPortal;

  private final Runnable showControls = new Runnable() {
    @Override
    public void run() {
      exitArmed = false;
      handler.removeCallbacks(showControls);
      Log.i(TAG, "Opening kiosk controls");
      cancelPageTouches();
      new AlertDialog.Builder(MainActivity.this)
          .setTitle("Home HQ")
          .setItems(new String[] {"Open launcher", "Android settings", "Wi-Fi settings", "Reload dashboard"},
              (dialog, which) -> {
                if (which == 0) openLauncher();
                else if (which == 1) startActivity(new Intent(Settings.ACTION_SETTINGS));
                else if (which == 2) openWifiSettings();
                else web.reload();
              })
          .setNegativeButton("Back to dashboard", null).show();
    }
  };

  @Override
  protected void onCreate(Bundle state) {
    super.onCreate(state);
    applyDebugFlag(getIntent());
    applyHomeFlag(getIntent());
    applyBootanimFlag(getIntent());
    keepNavigationEnabled();
    getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
        | WindowManager.LayoutParams.FLAG_FULLSCREEN);

    web = new WebView(this);
    WebSettings s = web.getSettings();
    s.setJavaScriptEnabled(true);
    s.setDomStorageEnabled(true);
    s.setUseWideViewPort(true);
    s.setMediaPlaybackRequiresUserGesture(false);
    // Keep navigation inside the kiosk. When the kiosk starts at boot before Wi-Fi is up, the
    // first load fails and would stay on the error page, so retry failed main-frame loads.
    // The offline screen covers WebView's error page until a load succeeds.
    web.setWebViewClient(new WebViewClient() {
      @Override
      public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
        return localAsset(req.getUrl());
      }

      @Override
      public void onPageStarted(WebView view, String url, Bitmap icon) {
        pageFailed = false;
        mainUrl = url;
      }

      @Override
      public void onPageCommitVisible(WebView view, String url) {
        // The retry reached the server and is drawing; let a slow page finish.
        handler.removeCallbacks(stall);
      }

      @Override
      public void onPageFinished(WebView view, String url) {
        if (!pageFailed && !retryPending) {
          offline.setVisibility(View.GONE);
          handler.removeCallbacks(stall);
        }
      }

      @Override
      @SuppressWarnings("deprecation")
      public void onReceivedError(WebView view, int code, String desc, String failingUrl) {
        if (portalMode) {
          // The sign-in page itself didn't load; the next portal check loads it again.
          Log.w(TAG, "Wi-Fi sign-in page failed (" + desc + ")");
          portalFailed = true;
          return;
        }
        Log.w(TAG, "Load failed (" + desc + "), retrying in " + RETRY_MS + " ms");
        pageFailed = true;
        showOffline();
        retryUrl = failingUrl;
        handler.removeCallbacks(retry);
        handler.removeCallbacks(stall);
        retryPending = true;
        handler.postDelayed(retry, RETRY_MS);
      }

      @Override
      public void onReceivedSslError(WebView view, SslErrorHandler h, SslError error) {
        // Never bypass a certificate error. Frames without a clock battery boot with an old date
        // after a power cut, so every certificate looks invalid until network time arrives. Treat
        // it as a failed load and retry the saved page until the clock is right.
        h.cancel();
        // Images and scripts report certificate errors here too. Android 6 doesn't trust every
        // CA, so one such image must not cover a working page; only the page itself counts.
        if (mainUrl != null && !mainUrl.equals(error.getUrl())) {
          Log.w(TAG, "Certificate error " + error.getPrimaryError() + " on a subresource; blocked");
          return;
        }
        if (portalMode) {
          Log.w(TAG, "Certificate error " + error.getPrimaryError() + " on the Wi-Fi sign-in page");
          portalFailed = true;
          portalText.setText("This Wi-Fi's sign-in page has a certificate problem. Trying again\u2026");
          return;
        }
        Log.w(TAG, "Certificate error " + error.getPrimaryError() + ", retrying in " + RETRY_MS + " ms");
        pageFailed = true;
        showOffline();
        if (error.hasError(SslError.SSL_NOTYETVALID) || error.hasError(SslError.SSL_EXPIRED)
            || error.hasError(SslError.SSL_DATE_INVALID)) {
          offlineTitle.setText("Setting the clock\u2026");
          offlineText.setText("The frame's date is wrong after a power cut. It reloads once the time is set.");
          nudgeNetworkTime();
        }
        retryUrl = error.getUrl() != null ? error.getUrl() : savedUrl();
        handler.removeCallbacks(retry);
        handler.removeCallbacks(stall);
        retryPending = true;
        handler.postDelayed(retry, RETRY_MS);
      }
    });
    LinearLayout column = new LinearLayout(this);
    column.setOrientation(LinearLayout.VERTICAL);
    column.addView(buildPortalBar());
    column.addView(web, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
    FrameLayout root = new FrameLayout(this);
    root.addView(column);
    root.addView(buildOffline());
    menuButton = new Button(this);
    menuButton.setText("Menu");
    menuButton.setAllCaps(false);
    menuButton.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
    menuButton.setTextColor(Color.WHITE);
    menuButton.setContentDescription("Open kiosk controls");
    menuButton.setPadding(0, 0, 0, 0);
    GradientDrawable menuBackground = new GradientDrawable();
    menuBackground.setColor(Color.argb(220, 35, 35, 35));
    menuBackground.setCornerRadius(dp(10));
    menuBackground.setStroke(dp(1), Color.rgb(90, 90, 90));
    menuButton.setBackground(menuBackground);
    menuButton.setOnClickListener(v -> showControls.run());
    FrameLayout.LayoutParams menuPosition = new FrameLayout.LayoutParams(
        dp(72), dp(48), Gravity.BOTTOM | Gravity.LEFT);
    menuPosition.setMargins(dp(12), dp(12), dp(12), dp(12));
    root.addView(menuButton, menuPosition);
    applyMenuButtonFlag(getIntent());
    setContentView(root);

    String url = urlFrom(getIntent());
    load(url != null ? url : savedUrl());
    @SuppressWarnings("deprecation")
    IntentFilter connectivity = new IntentFilter(ConnectivityManager.CONNECTIVITY_ACTION);
    connectivity.addAction(Intent.ACTION_TIME_CHANGED); // network time arrived after a power cut
    registerReceiver(networkChange, connectivity);
  }

  @Override
  protected void onResume() {
    super.onResume();
    NavigationService.setDashboardVisible(true);
  }

  @Override
  protected void onPause() {
    cancelExit();
    NavigationService.setDashboardVisible(false);
    super.onPause();
  }

  @Override
  protected void onNewIntent(Intent intent) {
    super.onNewIntent(intent);
    setIntent(intent);
    applyDebugFlag(intent);
    applyHomeFlag(intent);
    applyMenuButtonFlag(intent);
    applyBootanimFlag(intent);
    String url = urlFrom(intent);
    if (url != null) {
      closePortal();
      handler.removeCallbacks(retry);
      handler.removeCallbacks(stall);
      retryPending = false;
      retryUrl = url;
      load(url);
    }
  }

  /** A "url" extra is saved for later launches. A VIEW link from another app is shown, not saved. */
  private String urlFrom(Intent intent) {
    String saved = intent.getStringExtra(PREF_URL);
    if (saved == null) {
      String link = intent.getDataString();
      return link != null && isWebUrl(link) ? link : null;
    }
    if (!isWebUrl(saved)) return null;
    getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(PREF_URL, saved).apply();
    Log.i(TAG, "Saved kiosk URL: " + forLog(saved));
    return saved;
  }

  /**
   * The activity is exported, and an explicit intent skips the manifest's http/https filter. So
   * check both URL inputs: never load or save file:, content: or javascript:.
   */
  private static boolean isWebUrl(String url) {
    String scheme = Uri.parse(url).getScheme();
    if ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) return true;
    Log.w(TAG, "Ignoring non-web kiosk URL (scheme " + scheme + ")");
    return false;
  }

  /**
   * The URL without user info, query or fragment, for logcat. Those parts can carry API keys or
   * tokens, and any app with READ_LOGS (or anyone with ADB) can read the log.
   */
  static String forLog(String url) {
    Uri u = Uri.parse(url);
    String port = u.getPort() == -1 ? "" : ":" + u.getPort();
    String path = u.getEncodedPath() == null ? "" : u.getEncodedPath();
    boolean hidden = u.getEncodedUserInfo() != null || u.getEncodedQuery() != null
        || u.getEncodedFragment() != null;
    return u.getScheme() + "://" + u.getHost() + port + path + (hidden ? " (query, fragment or user info not logged)" : "");
  }

  // Some WebViews report the page's certificate error before onPageStarted, so remember the
  // page here too.
  private void load(String url) {
    mainUrl = url;
    web.loadUrl(url);
  }

  private String savedUrl() {
    return getSharedPreferences(PREFS, MODE_PRIVATE).getString(PREF_URL, DEFAULT_URL);
  }

  /**
   * Answers http://127.0.0.1:8765/<path> from assets/site/<path> (bundled by build.sh from
   * KIOSK_SITE). Any other URL returns null and goes to the network as usual. Nothing listens on
   * the port; only this WebView sees these responses. Paths ending in / get index.html.
   */
  private WebResourceResponse localAsset(Uri u) {
    if (u == null || !"http".equalsIgnoreCase(u.getScheme()) || !LOCAL_HOST.equals(u.getHost())
        || u.getPort() != LOCAL_PORT) return null;
    String path = u.getPath();
    if (path == null || path.isEmpty()) path = "/";
    if (path.endsWith("/")) path += "index.html";
    Map<String, String> headers = new HashMap<>();
    headers.put("Cache-Control", "no-cache");
    if (path.contains("..") || path.contains("//")) {
      return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found", headers, null);
    }
    try {
      InputStream in = getAssets().open(LOCAL_ASSETS + path);
      return new WebResourceResponse(mimeFor(path), "utf-8", 200, "OK", headers, in);
    } catch (IOException e) {
      Log.w(TAG, "No bundled file for " + path);
      return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found", headers, null);
    }
  }

  static String mimeFor(String path) {
    String p = path.toLowerCase(Locale.ROOT);
    if (p.endsWith(".html") || p.endsWith(".htm")) return "text/html";
    if (p.endsWith(".js") || p.endsWith(".mjs")) return "text/javascript";
    if (p.endsWith(".css")) return "text/css";
    if (p.endsWith(".json")) return "application/json";
    if (p.endsWith(".svg")) return "image/svg+xml";
    if (p.endsWith(".png")) return "image/png";
    if (p.endsWith(".jpg") || p.endsWith(".jpeg")) return "image/jpeg";
    if (p.endsWith(".webp")) return "image/webp";
    if (p.endsWith(".gif")) return "image/gif";
    if (p.endsWith(".woff2")) return "font/woff2";
    if (p.endsWith(".txt")) return "text/plain";
    return "application/octet-stream";
  }

  private int dp(float v) {
    return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
  }

  private View buildOffline() {
    offline = new LinearLayout(this);
    offline.setOrientation(LinearLayout.VERTICAL);
    offline.setGravity(Gravity.CENTER);
    offline.setBackgroundColor(Color.rgb(17, 17, 17));
    offline.setVisibility(View.GONE);
    offline.setClickable(true); // keep taps off the error page underneath

    offlineTitle = new TextView(this);
    offlineTitle.setTextColor(Color.WHITE);
    offlineTitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 40);
    offlineTitle.setGravity(Gravity.CENTER);
    offline.addView(offlineTitle);

    offlineText = new TextView(this);
    offlineText.setTextColor(Color.rgb(170, 170, 170));
    offlineText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20);
    offlineText.setGravity(Gravity.CENTER);
    offlineText.setPadding(dp(24), dp(12), dp(24), dp(28));
    offline.addView(offlineText);

    Button wifi = new Button(this);
    wifi.setText("Open Wi-Fi settings");
    wifi.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
    wifi.setPadding(dp(32), dp(16), dp(32), dp(16));
    wifi.setOnClickListener(v -> openWifiSettings());
    offline.addView(wifi, new LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));

    signIn = new Button(this);
    signIn.setText("Sign in to Wi-Fi");
    signIn.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
    signIn.setPadding(dp(32), dp(16), dp(32), dp(16));
    signIn.setVisibility(View.GONE);
    signIn.setOnClickListener(v -> openPortal());
    LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    lp.topMargin = dp(16);
    offline.addView(signIn, lp);
    return offline;
  }

  /** The strip above the Wi-Fi sign-in page. */
  private View buildPortalBar() {
    portalBar = new LinearLayout(this);
    portalBar.setOrientation(LinearLayout.HORIZONTAL);
    portalBar.setGravity(Gravity.CENTER_VERTICAL);
    portalBar.setBackgroundColor(Color.rgb(17, 17, 17));
    portalBar.setPadding(dp(16), dp(8), dp(8), dp(8));
    portalBar.setVisibility(View.GONE);

    portalText = new TextView(this);
    portalText.setTextColor(Color.WHITE);
    portalText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
    portalBar.addView(portalText, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));

    Button cancel = new Button(this);
    cancel.setText("Cancel");
    cancel.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
    cancel.setOnClickListener(v -> {
      portalDismissed = true;
      leavePortal();
    });
    portalBar.addView(cancel);
    return portalBar;
  }

  /** Probes PORTAL_PROBE off the main thread; the result goes to onProbe. One probe at a time. */
  private void checkPortal() {
    if (probing) return;
    probing = true;
    new Thread(() -> {
      int result = probePortal();
      handler.post(() -> {
        probing = false;
        if (!isDestroyed()) onProbe(result);
      });
    }, "portal-probe").start();
  }

  /** Runs on a background thread. Redirects are not followed, so a portal's redirect counts as a portal. */
  static int probePortal() {
    HttpURLConnection c = null;
    try {
      c = (HttpURLConnection) new URL(PORTAL_PROBE).openConnection();
      c.setInstanceFollowRedirects(false);
      c.setUseCaches(false);
      c.setConnectTimeout(PROBE_TIMEOUT_MS);
      c.setReadTimeout(PROBE_TIMEOUT_MS);
      int code = c.getResponseCode();
      // Like Android: an empty 200 (some proxies send it for 204) also means online.
      if (code == 204 || (code == 200 && c.getContentLength() == 0)) return PROBE_ONLINE;
      if (code >= 200 && code < 400) {
        Log.i(TAG, "Wi-Fi sign-in page found (probe answered " + code + ")");
        return PROBE_PORTAL;
      }
      return PROBE_FAILED;
    } catch (IOException e) {
      return PROBE_FAILED;
    } finally {
      if (c != null) c.disconnect();
    }
  }

  private void onProbe(int result) {
    if (portalMode) {
      if (result == PROBE_ONLINE || !wifiConnected()) {
        Log.i(TAG, result == PROBE_ONLINE ? "Signed in to Wi-Fi, back to the dashboard" : "Wi-Fi dropped during sign-in");
        portalFound = false;
        leavePortal();
        return;
      }
      if (SystemClock.elapsedRealtime() - portalSince > PORTAL_GIVE_UP_MS) {
        Log.w(TAG, "Wi-Fi sign-in page still up after 10 min, retrying the dashboard");
        portalDismissed = true; // the offline screen offers "Sign in to Wi-Fi" instead
        leavePortal();
        return;
      }
      if (portalFailed && result == PROBE_PORTAL) {
        portalFailed = false;
        load(PORTAL_PROBE);
      }
      handler.postDelayed(portalCheck, PORTAL_CHECK_MS);
      return;
    }
    portalFound = result == PROBE_PORTAL;
    if (!portalFound || offline.getVisibility() != View.VISIBLE) return;
    if (portalDismissed) setOfflineText(); // offers the Sign in button instead
    else openPortal();
  }

  /**
   * Shows the network's sign-in page in place of the dashboard. Loading the probe URL lets the
   * portal redirect to its own page, as Android's sign-in app does.
   */
  private void openPortal() {
    portalMode = true;
    portalDismissed = false;
    portalFailed = false;
    portalSince = SystemClock.elapsedRealtime();
    handler.removeCallbacks(retry);
    handler.removeCallbacks(stall);
    handler.removeCallbacks(portalCheck);
    retryPending = false;
    if (retryUrl == null) retryUrl = savedUrl();
    portalText.setText("This Wi-Fi needs you to accept its terms. The dashboard comes back once the frame is online.");
    portalBar.setVisibility(View.VISIBLE);
    offline.setVisibility(View.GONE);
    load(PORTAL_PROBE);
    handler.postDelayed(portalCheck, PORTAL_CHECK_MS);
  }

  /** Closes the sign-in page and loads the dashboard again. */
  private void leavePortal() {
    closePortal();
    load(retryUrl != null ? retryUrl : savedUrl());
  }

  private void closePortal() {
    if (!portalMode) return;
    portalMode = false;
    handler.removeCallbacks(portalCheck);
    portalBar.setVisibility(View.GONE);
  }

  /**
   * Asks Android to fetch network time again, by turning automatic time off and on, at most once a
   * minute while the date is wrong and Wi-Fi is up. Android 6's time service gives up when its
   * boot-time attempts fail (Wi-Fi not ready yet, or a router that doesn't answer NTP) and waits
   * 24 h, leaving a frame with no clock battery in 1969. Seen on an RK3126 Frameo frame, where
   * `settings put global auto_time 0` then `1` set the time within seconds.
   * Needs the same optional grant as the navigation repair (WRITE_SECURE_SETTINGS); does nothing
   * if automatic time was turned off on purpose.
   */
  private void nudgeNetworkTime() {
    if (checkSelfPermission("android.permission.WRITE_SECURE_SETTINGS") != PackageManager.PERMISSION_GRANTED) return;
    if (!wifiConnected()) return;
    long now = SystemClock.elapsedRealtime();
    if (now - lastTimeNudge < TIME_NUDGE_MS) return;
    ContentResolver cr = getContentResolver();
    if (Settings.Global.getInt(cr, Settings.Global.AUTO_TIME, 1) != 1) return;
    lastTimeNudge = now;
    try {
      Settings.Global.putInt(cr, Settings.Global.AUTO_TIME, 0);
      Settings.Global.putInt(cr, Settings.Global.AUTO_TIME, 1);
      Log.i(TAG, "Clock is wrong; asked Android for network time again");
    } catch (SecurityException e) {
      Log.w(TAG, "Could not re-request network time: " + e);
    }
  }

  private boolean wifiConnected() {
    ConnectivityManager cm = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
    @SuppressWarnings("deprecation")
    NetworkInfo n = cm != null ? cm.getNetworkInfo(ConnectivityManager.TYPE_WIFI) : null;
    return n != null && n.isConnected();
  }

  private void showOffline() {
    boolean wifi = setOfflineText();
    offline.setVisibility(View.VISIBLE);
    // On Wi-Fi, a sign-in page may be what's blocking the dashboard.
    if (wifi) checkPortal();
  }

  /** Fills in the offline screen for the current state; returns whether Wi-Fi is connected. */
  private boolean setOfflineText() {
    boolean wifi = wifiConnected();
    if (!wifi) {
      // A new network gets its sign-in page opened again, even if the last one was closed.
      portalFound = false;
      portalDismissed = false;
    }
    signIn.setVisibility(wifi && portalFound ? View.VISIBLE : View.GONE);
    if (wifi && portalFound) {
      offlineTitle.setText("Sign in to Wi-Fi");
      offlineText.setText("This Wi-Fi shows a page where you accept its terms before the frame can go online.");
    } else if (wifi) {
      offlineTitle.setText("Can't reach the dashboard");
      offlineText.setText("Wi-Fi is connected. Retrying every few seconds.");
    } else {
      offlineTitle.setText("Connect to Wi-Fi?");
      offlineText.setText("The frame isn't on Wi-Fi. The dashboard comes back by itself once it is.");
    }
    return wifi;
  }

  private void openWifiSettings() {
    try {
      startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS));
    } catch (Exception e) {
      Log.w(TAG, "No Wi-Fi settings screen, opening Settings", e);
      startActivity(new Intent(Settings.ACTION_SETTINGS));
    }
  }

  /**
   * Some frames (PF1007L) run a vendor BackgroundManagerService that drops the navigation service
   * after the kiosk is updated or force-stopped, leaving no way back from Settings. If the owner
   * opted in by granting WRITE_SECURE_SETTINGS, put the service back on the enabled list:
   *   adb shell pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS
   * Android 6 also leaves the service listed but unbound after the kiosk's process is killed (the
   * Denver PFF-1015's low-RAM mode kills it on every app switch), so rebind it if it isn't running.
   */
  private void keepNavigationEnabled() {
    if (checkSelfPermission("android.permission.WRITE_SECURE_SETTINGS") != PackageManager.PERMISSION_GRANTED) return;
    String cur = Settings.Secure.getString(getContentResolver(), Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
    String others = withoutNavigation(cur);
    if (!isNavigationListed(cur)) {
      setNavigationServices(others.isEmpty() ? navigationService() : others + ":" + navigationService());
      Log.i(TAG, "Re-enabled navigation service");
      return;
    }
    // Some firmware keeps the selected service but resets only the master switch at boot. On a
    // PF1508 (Android 15) the switch alone doesn't bind the service, so still check it below.
    int enabled = Settings.Secure.getInt(getContentResolver(), Settings.Secure.ACCESSIBILITY_ENABLED, 0);
    if (enabled != 1) setAccessibilityEnabled();
    handler.postDelayed(() -> {
      if (NavigationService.isConnected()) return;
      // Writing the same list doesn't notify Android, so take the service off and put it back.
      setNavigationServices(others);
      rebindHandler.postDelayed(() -> setNavigationServices(cur), NAV_REBIND_MS);
      Log.i(TAG, "Navigation service listed but not running, rebinding");
    }, NAV_CHECK_MS);
  }

  private String navigationService() {
    return getPackageName() + "/" + NavigationService.class.getName();
  }

  private boolean isNavigationEntry(String entry) {
    return new ComponentName(this, NavigationService.class).equals(ComponentName.unflattenFromString(entry));
  }

  private boolean isNavigationListed(String services) {
    if (services == null) return false;
    for (String entry : services.split(":")) {
      if (isNavigationEntry(entry)) return true;
    }
    return false;
  }

  /** The enabled services list without the navigation service. */
  private String withoutNavigation(String services) {
    if (services == null) return "";
    StringBuilder rest = new StringBuilder();
    for (String entry : services.split(":")) {
      if (entry.isEmpty() || isNavigationEntry(entry)) continue;
      if (rest.length() > 0) rest.append(':');
      rest.append(entry);
    }
    return rest.toString();
  }

  private void setNavigationServices(String services) {
    try {
      Settings.Secure.putString(getContentResolver(), Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES, services);
      if (Settings.Secure.getInt(getContentResolver(), Settings.Secure.ACCESSIBILITY_ENABLED, 0) != 1) {
        Settings.Secure.putString(getContentResolver(), Settings.Secure.ACCESSIBILITY_ENABLED, "1");
      }
    } catch (SecurityException e) {
      Log.w(TAG, "Could not update navigation service", e);
    }
  }

  /** Master switch only: a correct services list is left untouched. */
  private void setAccessibilityEnabled() {
    try {
      Settings.Secure.putString(getContentResolver(), Settings.Secure.ACCESSIBILITY_ENABLED, "1");
    } catch (SecurityException e) {
      Log.w(TAG, "Could not update accessibility master switch", e);
    }
  }

  private void openLauncher() {
    Intent home = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME);
    for (ResolveInfo info : getPackageManager().queryIntentActivities(home, 0)) {
      String pkg = info.activityInfo.packageName;
      if (pkg.equals(getPackageName()) || pkg.equals("com.android.settings")) continue;
      startActivity(new Intent(home).setComponent(new ComponentName(pkg, info.activityInfo.name)));
      return;
    }
    startActivity(new Intent(Settings.ACTION_SETTINGS));
  }

  @Override
  protected void onDestroy() {
    unregisterReceiver(networkChange);
    handler.removeCallbacksAndMessages(null);
    if (web != null) web.destroy();
    super.onDestroy();
  }

  /** Remote debugging only when explicitly requested; any normal launch turns it back off. */
  private void applyDebugFlag(Intent intent) {
    boolean debug = intent != null && intent.getBooleanExtra("debug", false);
    WebView.setWebContentsDebuggingEnabled(debug);
    Log.i(TAG, "WebView remote debugging " + (debug ? "ON" : "off"));
  }

  /** A saved opt-in for panels where the two-finger gesture is unreliable. */
  private void applyMenuButtonFlag(Intent intent) {
    if (intent != null && intent.hasExtra(PREF_MENU_BUTTON)) {
      getSharedPreferences(PREFS, MODE_PRIVATE).edit()
          .putBoolean(PREF_MENU_BUTTON, intent.getBooleanExtra(PREF_MENU_BUTTON, false)).apply();
    }
    menuButton.setVisibility(getSharedPreferences(PREFS, MODE_PRIVATE)
        .getBoolean(PREF_MENU_BUTTON, false) ? View.VISIBLE : View.GONE);
  }

  /**
   * A saved opt-in for frames whose vendor boot animation keeps covering the kiosk after a power
   * cut. sys.bootanim.exit is a per-boot property, so it has to be set again on every start. It
   * works without root only where SELinux is permissive or the app runs as system; where it is
   * refused, setprop fails, the failure is logged and nothing else changes.
   */
  private void applyBootanimFlag(Intent intent) {
    if (intent != null && intent.hasExtra(PREF_BOOTANIM_EXIT)) {
      getSharedPreferences(PREFS, MODE_PRIVATE).edit()
          .putBoolean(PREF_BOOTANIM_EXIT, intent.getBooleanExtra(PREF_BOOTANIM_EXIT, false)).apply();
    }
    boolean enabled = getSharedPreferences(PREFS, MODE_PRIVATE)
        .getBoolean(PREF_BOOTANIM_EXIT, false);
    Log.i(TAG, "Boot animation exit " + (enabled ? "on" : "off"));
    if (!enabled) return;
    new Thread(new Runnable() {
      @Override
      public void run() {
        // The property service may not be ready at the first start after a power cut, so try
        // twice. Both attempts are cheap and setting it when the animation is already gone is
        // harmless.
        for (int attempt = 0; attempt < 2; attempt++) {
          try {
            Process p = Runtime.getRuntime().exec(
                new String[] {"/system/bin/setprop", "sys.bootanim.exit", "1"});
            int rc = p.waitFor();
            if (rc != 0) Log.w(TAG, "setprop sys.bootanim.exit exited " + rc);
          } catch (IOException | InterruptedException e) {
            Log.w(TAG, "Could not set sys.bootanim.exit: " + e);
            return;
          }
          try {
            Thread.sleep(RETRY_MS);
          } catch (InterruptedException e) {
            return;
          }
        }
      }
    }, "bootanim-exit").start();
  }

  /** Turns the Home alias on or off. The shell can't enable a component of a release app. */
  private void applyHomeFlag(Intent intent) {
    if (intent == null || !intent.hasExtra("home")) return;
    boolean home = intent.getBooleanExtra("home", false);
    getPackageManager().setComponentEnabledSetting(new ComponentName(this, getPackageName() + ".Home"),
        home ? PackageManager.COMPONENT_ENABLED_STATE_ENABLED : PackageManager.COMPONENT_ENABLED_STATE_DEFAULT,
        PackageManager.DONT_KILL_APP);
    Log.i(TAG, "Home alias " + (home ? "on" : "off"));
  }

  /** Watches for the two-finger exit hold; all touches still go to the page (after a stale-touch reset). */
  @Override
  public boolean dispatchTouchEvent(MotionEvent e) {
    switch (e.getActionMasked()) {
      case MotionEvent.ACTION_DOWN:
        // Android sends DOWN only when every earlier finger has lifted. If the page still holds a
        // touch from before (see cancelPageTouches), clear it first so this tap is not read as a
        // second finger. With no stale touch the cancel is a no-op.
        cancelPageTouches();
        break;
      case MotionEvent.ACTION_POINTER_DOWN:
        if (e.getPointerCount() == 2) {
          for (int i = 0; i < 2; i++) {
            exitIds[i] = e.getPointerId(i);
            exitX[i] = e.getX(i);
            exitY[i] = e.getY(i);
          }
          exitArmed = true;
          handler.removeCallbacks(showControls);
          handler.postDelayed(showControls, EXIT_HOLD_MS);
        } else {
          cancelExit(); // 3+ fingers
        }
        break;
      case MotionEvent.ACTION_MOVE:
        if (exitArmed) {
          for (int i = 0; i < 2; i++) {
            int idx = e.findPointerIndex(exitIds[i]);
            if (idx < 0 || Math.hypot(e.getX(idx) - exitX[i], e.getY(idx) - exitY[i]) > EXIT_SLOP_PX) {
              cancelExit();
              break;
            }
          }
        }
        break;
      case MotionEvent.ACTION_POINTER_UP:
      case MotionEvent.ACTION_UP:
      case MotionEvent.ACTION_CANCEL:
        cancelExit();
        break;
      default:
        break;
    }
    return super.dispatchTouchEvent(e);
  }

  private void cancelExit() {
    if (!exitArmed) return;
    exitArmed = false;
    handler.removeCallbacks(showControls);
  }

  /**
   * Ends any touch the page thinks is still down. On a PF1007L (2026-10-16) the WebView sometimes
   * kept one touch "down" for good after the two-finger controls opened (not every time), while
   * Android reported no touch at all. Every later tap then arrived as a second finger and the page
   * ignored it (no pointerdown). A cancel resets the page's touch state; with no touch active it
   * does nothing.
   */
  private void cancelPageTouches() {
    if (web == null) return;
    // The stuck touch was pointer id 1 (the second finger of the hold), so a single-pointer cancel
    // (id 0) left it in place. Name every id the panel can use; the page ignores ids it isn't holding.
    MotionEvent.PointerProperties[] props = new MotionEvent.PointerProperties[CANCEL_POINTER_IDS];
    MotionEvent.PointerCoords[] coords = new MotionEvent.PointerCoords[CANCEL_POINTER_IDS];
    for (int i = 0; i < CANCEL_POINTER_IDS; i++) {
      props[i] = new MotionEvent.PointerProperties();
      props[i].id = i;
      props[i].toolType = MotionEvent.TOOL_TYPE_FINGER;
      coords[i] = new MotionEvent.PointerCoords();
    }
    long now = SystemClock.uptimeMillis();
    MotionEvent cancel = MotionEvent.obtain(now, now, MotionEvent.ACTION_CANCEL, CANCEL_POINTER_IDS,
        props, coords, 0, 0, 1f, 1f, 0, 0, InputDevice.SOURCE_TOUCHSCREEN, 0);
    web.dispatchTouchEvent(cancel);
    cancel.recycle();
  }

  @Override
  public void onWindowFocusChanged(boolean hasFocus) {
    super.onWindowFocusChanged(hasFocus);
    if (hasFocus) hideSystemUi();
    else cancelPageTouches(); // a dialog or another app took over mid-touch
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
