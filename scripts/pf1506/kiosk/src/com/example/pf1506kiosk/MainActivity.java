package com.example.pf1506kiosk;

import android.app.Activity;
import android.app.ActivityManager;
import android.app.admin.DevicePolicyManager;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Full-screen web-page kiosk for the PF1506 frame (LineageOS 20 GSI).
 *
 * - Shows a calendar in a WebView; it is the home app and runs in lock-task mode (no
 *   status/navigation bars) when it is device owner. Two modes:
 *   - Standalone (default): the calendar page is built in (assets/web/) and reads your
 *     calendars' iCal addresses itself. Settings come from a phone, through the setup page
 *     the app serves on the home network (SetupServer). Needs internet.
 *   - URL: shows a page you host yourself (set over adb, see AdminCommandReceiver).
 * - After IDLE_MS without a touch it drops the backlight to its minimum and covers the page
 *   with black. The display stays on, so the touch controller stays awake and a tap wakes it.
 *   The waking tap is swallowed so it never opens an event by accident.
 * - Quiet hours (02:00-07:00, see ScheduleReceiver): the idle timeout turns the screen fully
 *   off instead of dimming; an alarm turns it back on at 07:00.
 * - Clock (URL mode): for a frame kept off the internet (no NTP), every CLOCK_SYNC_MS it requests
 *   <page origin>/healthz and reads the HTTP Date header of a 200 response and, as device owner, corrects the system clock if it is off by
 *   more than MAX_DRIFT_MS (e.g. after a power cut).
 *
 * Settings via adb (persisted):
 *   See AdminCommandReceiver (url, standalone, release_owner). Lock-task mode keeps the
 *   frame's own UI out of reach; it is a convenience, not a security boundary.
 */
public class MainActivity extends Activity {
    private static final String TAG = "FrameKiosk";
    private static final long IDLE_MS = 60_000;
    private static final long RETRY_MS = 15_000;
    private static final long FAST_RETRY_MS = 5_000;        // while Wi-Fi comes up after boot
    private static final long FAST_RETRY_UNTIL_UPTIME_MS = 5 * 60_000;
    private static final long RELOAD_AFTER_PAUSE_MS = 10 * 60_000;
    private static final float BRIGHT = 0.8f;
    private static final float DIM = 0.0f;
    private static final long CLOCK_SYNC_MS = 5 * 60_000;
    private static final long CLOCK_RETRY_MS = 30_000;       // until the first successful sync
    private static final long MAX_DRIFT_MS = 2_000;
    static final String ACTION_QUIET_NOW = "com.example.pf1506kiosk.QUIET_NOW";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private WebView web;
    private View blackout;
    private boolean dimmed;
    private boolean swallowGesture;
    private boolean loadFailed;
    private long pausedAt;
    private String url;              // "" = standalone
    private LocalContent local;
    private SetupServer setup;

    // Named inner classes: javac against android.jar has no LambdaMetafactory, and d8 34
    // crashes on anonymous classes created in field initializers.
    private final class DimTask implements Runnable {
        @Override public void run() { dim(); }
    }

    private final class RetryTask implements Runnable {
        @Override public void run() {
            Log.i(TAG, "retrying " + url);
            loadFailed = false;
            load();
        }
    }

    /** Runs one clock sync off the main thread, then schedules the next. */
    private final class ClockTask implements Runnable {
        @Override public void run() {
            new Thread(new ClockSync(), "clock-sync").start();
        }
    }

    private final class ClockSync implements Runnable {
        @Override public void run() {
            boolean ok = syncClock();
            handler.postDelayed(clockRunnable, ok ? CLOCK_SYNC_MS : CLOCK_RETRY_MS);
        }
    }

    /** Any wall-clock or timezone change moves "next 02:00 / 07:00": reschedule. */
    private final class TimeChangeReceiver extends BroadcastReceiver {
        @Override public void onReceive(Context c, Intent i) {
            Log.i(TAG, "time changed: " + i.getAction());
            ScheduleReceiver.schedule(c);
        }
    }

    /** 02:00 alarm: switch off now if nobody is using it, else the idle timeout will. */
    private final class QuietReceiver extends BroadcastReceiver {
        @Override public void onReceive(Context c, Intent i) {
            if (dimmed) screenOff();
        }
    }

    private final class ReloadTask implements Runnable {
        // Standalone only: in URL mode the page doesn't show setup state, and a queued
        // reload could otherwise land on the old built-in page right after a mode switch.
        @Override public void run() { if (web != null && url.isEmpty()) load(); }
    }

    /** Setup page started/stopped or settings saved: reload so the page shows it. */
    private final class SetupListener implements SetupServer.Listener {
        @Override public void onSetupChanged(String address, String pin) {
            local.setSetupInfo(address, pin);
            handler.post(reloadRunnable);
        }
        @Override public void onConfigSaved() {
            handler.post(reloadRunnable);
        }
    }

    private final Runnable reloadRunnable = new ReloadTask();
    private final Runnable dimRunnable = new DimTask();
    private final Runnable retryRunnable = new RetryTask();
    private final Runnable clockRunnable = new ClockTask();
    private final BroadcastReceiver timeChangeReceiver = new TimeChangeReceiver();
    private final BroadcastReceiver quietReceiver = new QuietReceiver();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setShowWhenLocked(true);
        setTurnScreenOn(true);

        SharedPreferences prefs = getSharedPreferences("kiosk", Context.MODE_PRIVATE);
        url = prefs.getString("url", "");
        local = new LocalContent(this);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(true);
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);
        web.setBackgroundColor(Color.BLACK);
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView v, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) {
                    Log.w(TAG, "load failed: " + err.getDescription());
                    loadFailed = true;
                    handler.removeCallbacks(retryRunnable);
                    boolean early = SystemClock.elapsedRealtime() < FAST_RETRY_UNTIL_UPTIME_MS;
                    handler.postDelayed(retryRunnable, early ? FAST_RETRY_MS : RETRY_MS);
                }
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest req) {
                if (!url.isEmpty() || !"kiosk.invalid".equals(req.getUrl().getHost())) return null;
                return local.handle(req.getUrl(), req.getMethod());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
                return !req.getUrl().toString().startsWith(base());  // stay on the calendar
            }
        });
        root.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        blackout = new View(this);
        blackout.setBackgroundColor(Color.BLACK);
        blackout.setVisibility(View.GONE);
        root.addView(blackout, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);

        load();
        startSetupIfStandalone();
        ScheduleReceiver.schedule(this);
        IntentFilter timeFilter = new IntentFilter(Intent.ACTION_TIME_CHANGED);
        timeFilter.addAction(Intent.ACTION_TIMEZONE_CHANGED);
        registerReceiver(timeChangeReceiver, timeFilter);
        registerReceiver(quietReceiver, new IntentFilter(ACTION_QUIET_NOW), Context.RECEIVER_NOT_EXPORTED);
        registerReceiver(applyReceiver, new IntentFilter(AdminCommandReceiver.ACTION_APPLY), Context.RECEIVER_NOT_EXPORTED);
        running = true;
        applySettings();  // a release requested while the app wasn't running
        handler.post(clockRunnable);
    }

    @Override
    protected void onDestroy() {
        unregisterReceiver(timeChangeReceiver);
        unregisterReceiver(quietReceiver);
        unregisterReceiver(applyReceiver);
        running = false;
        if (setup != null) setup.shutdown();
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    // Exported as the home app, so extras from other apps are ignored; admin commands
    // arrive through AdminCommandReceiver instead.
    static volatile boolean running;
    private final BroadcastReceiver applyReceiver = new ApplyReceiver();

    /** Settings changed over adb (AdminCommandReceiver): re-read them and apply. */
    private void applySettings() {
        SharedPreferences prefs = getSharedPreferences("kiosk", Context.MODE_PRIVATE);
        String newUrl = prefs.getString("url", "");
        if (!newUrl.equals(url)) {
            url = newUrl;
            load();
            startSetupIfStandalone();
            enterKiosk();
            Log.i(TAG, url.isEmpty() ? "standalone mode" : "url set to " + url);
        }
        if (prefs.getBoolean(AdminCommandReceiver.PREF_RELEASE, false)) {
            prefs.edit().remove(AdminCommandReceiver.PREF_RELEASE).apply();
            DevicePolicyManager dpm = getSystemService(DevicePolicyManager.class);
            if (dpm.isDeviceOwnerApp(getPackageName())) {
                try { stopLockTask(); } catch (Exception ignored) { }
                dpm.clearDeviceOwnerApp(getPackageName());
                Log.i(TAG, "device owner released");
            }
        }
    }

    private final class ApplyReceiver extends BroadcastReceiver {
        @Override public void onReceive(Context c, Intent i) { applySettings(); }
    }

    @Override
    protected void onResume() {
        super.onResume();
        enterKiosk();
        hideSystemBars();
        if (pausedAt != 0 && SystemClock.elapsedRealtime() - pausedAt > RELOAD_AFTER_PAUSE_MS) {
            web.reload();  // e.g. after the overnight screen-off
        }
        pausedAt = 0;
        wake();
    }

    @Override
    protected void onPause() {
        super.onPause();
        pausedAt = SystemClock.elapsedRealtime();
        handler.removeCallbacks(dimRunnable);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideSystemBars();
    }

    /** Device owner: whitelist ourselves, hide all lock-task UI, disable keyguard, pin. */
    private void enterKiosk() {
        DevicePolicyManager dpm = getSystemService(DevicePolicyManager.class);
        if (!dpm.isDeviceOwnerApp(getPackageName())) return;
        ComponentName admin = new ComponentName(this, AdminReceiver.class);
        try {
            dpm.setLockTaskPackages(admin, new String[]{getPackageName()});
            dpm.setLockTaskFeatures(admin, DevicePolicyManager.LOCK_TASK_FEATURE_NONE);
            dpm.setKeyguardDisabled(admin, true);
            dpm.setStatusBarDisabled(admin, true);
            // setTime() needs automatic time off: off in URL mode (the app keeps the clock),
            // on in standalone mode (network time).
            if (android.os.Build.VERSION.SDK_INT >= 30) dpm.setAutoTimeEnabled(admin, url.isEmpty());
            ActivityManager am = getSystemService(ActivityManager.class);
            if (am.getLockTaskModeState() == ActivityManager.LOCK_TASK_MODE_NONE) startLockTask();
        } catch (Exception e) {
            Log.w(TAG, "kiosk setup failed", e);
        }
    }

    private String base() {
        return url.isEmpty() ? LocalContent.ORIGIN + "/" : url;
    }

    private void load() {
        web.loadUrl(base());
    }

    /** Standalone: serve the setup page on the LAN for a while after each start. */
    private void startSetupIfStandalone() {
        if (!url.isEmpty()) {
            if (setup != null) setup.shutdown();
            return;
        }
        if (local == null || (setup != null && setup.isAlive())) return;
        setup = new SetupServer(this, new SetupListener());
        setup.start();
    }

    private void hideSystemBars() {
        WindowInsetsController c = getWindow().getInsetsController();
        if (c != null) {
            c.hide(WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
            c.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
        }
    }

    private void setBrightness(float b) {
        WindowManager.LayoutParams lp = getWindow().getAttributes();
        lp.screenBrightness = b;
        getWindow().setAttributes(lp);
    }

    private void dim() {
        if (dimmed) return;
        dimmed = true;
        blackout.setVisibility(View.VISIBLE);
        setBrightness(DIM);
        // Stop drawing and JS timers while nobody can see the page.
        web.setVisibility(View.INVISIBLE);
        web.onPause();
        web.pauseTimers();
        Log.i(TAG, "dimmed");
        if (ScheduleReceiver.inQuietHours()) screenOff();
    }

    /** Screen fully off (quiet hours). Touch can't wake it; the 07:00 alarm or power button does. */
    private void screenOff() {
        DevicePolicyManager dpm = getSystemService(DevicePolicyManager.class);
        try {
            dpm.lockNow();
            Log.i(TAG, "screen off (quiet hours)");
        } catch (SecurityException e) {
            Log.w(TAG, "lockNow not allowed", e);
        }
    }

    /**
     * Sets the system clock from the page server's HTTP Date header when it has drifted.
     * Returns true when the clock is (now) in sync. Runs on a background thread.
     */
    private boolean syncClock() {
        if (url.isEmpty()) return true;  // standalone: the frame has internet, so it uses network time
        HttpURLConnection c = null;
        try {
            URL u = new URL(new URL(url), "/healthz");
            long t0 = SystemClock.elapsedRealtime();
            c = (HttpURLConnection) u.openConnection();
            c.setConnectTimeout(5_000);
            c.setReadTimeout(5_000);
            c.setUseCaches(false);
            int code = c.getResponseCode();
            long t1 = SystemClock.elapsedRealtime();
            long serverDate = c.getDate();
            if (code != 200 || serverDate == 0) return false;
            // The Date header has 1 s resolution: assume the middle of that second, stamped
            // halfway through the request.
            long serverNow = serverDate + 500 + (t1 - t0) / 2;
            long drift = System.currentTimeMillis() - serverNow;
            if (Math.abs(drift) <= MAX_DRIFT_MS) return true;

            DevicePolicyManager dpm = getSystemService(DevicePolicyManager.class);
            if (!dpm.isDeviceOwnerApp(getPackageName())) return false;
            ComponentName admin = new ComponentName(this, AdminReceiver.class);
            boolean set = dpm.setTime(admin, serverNow + (SystemClock.elapsedRealtime() - t1));
            Log.i(TAG, "clock " + (set ? "corrected" : "NOT corrected") + " by " + (-drift) + " ms");
            if (set) ScheduleReceiver.schedule(getApplicationContext());  // alarms use wall time
            return set;
        } catch (Exception e) {
            Log.w(TAG, "clock sync failed: " + e);
            return false;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private void wake() {
        boolean wasDimmed = dimmed;
        if (wasDimmed) Log.i(TAG, "woke");
        dimmed = false;
        if (wasDimmed) {
            web.resumeTimers();
            web.onResume();
            web.setVisibility(View.VISIBLE);
            // Clock catches up on its own; refresh events/weather straight away.
            web.evaluateJavascript("typeof load === 'function' && load()", null);
        }
        blackout.setVisibility(View.GONE);
        setBrightness(BRIGHT);
        handler.removeCallbacks(dimRunnable);
        handler.postDelayed(dimRunnable, IDLE_MS);
        if (loadFailed) {
            handler.removeCallbacks(retryRunnable);
            handler.post(retryRunnable);
        }
    }

    @Override
    public boolean dispatchTouchEvent(MotionEvent ev) {
        int action = ev.getActionMasked();
        if (action == MotionEvent.ACTION_DOWN) {
            swallowGesture = dimmed;  // the tap that wakes the screen does nothing else
            wake();
        } else if (!swallowGesture) {
            handler.removeCallbacks(dimRunnable);
            handler.postDelayed(dimRunnable, IDLE_MS);
        }
        if (swallowGesture) {
            if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL) swallowGesture = false;
            return true;
        }
        return super.dispatchTouchEvent(ev);
    }

    @Override
    public void onBackPressed() {
        // Kiosk: back does nothing.
    }
}
