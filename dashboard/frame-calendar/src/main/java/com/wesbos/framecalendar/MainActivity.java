package com.wesbos.framecalendar;

import android.app.Activity;
import android.app.AlertDialog;
import android.animation.ValueAnimator;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.view.WindowManager;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.net.URI;
import java.time.YearMonth;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Collections;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.json.JSONException;
import org.json.JSONObject;
import org.mozilla.geckoview.GeckoResult;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoView;
import org.mozilla.geckoview.WebExtension;

public class MainActivity extends Activity {
    private final Handler handler = new Handler();
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private SharedPreferences prefs;
    private CalendarView calendar;
    private MonthPreviewsView previews;
    private TextView monthTitle, status, panelStatus;
    private ProgressBar syncIndicator;
    private GeckoView browser;
    private GeckoSession session;
    private ZoneId zone;
    private YearMonth month;
    private CalendarRange cachedRange;
    private CalendarStore.Result cachedCalendars;
    private int generation;
    private boolean active, loading, calendarRefreshPending, panelFailed, extensionReady, panelRetryScheduled;
    private boolean refreshScheduled, connected, dreamWasActive;
    private ValueAnimator wakeFade;
    private final Runnable retryPanel = () -> {
        panelRetryScheduled = false;
        if (!extensionReady || session == null || !session.isOpen()) return;
        if (networkAvailable()) loadPanel();
        else {
            panelStatus.setText("Home Assistant unavailable - waiting for network");
            panelStatus.setVisibility(View.VISIBLE);
            schedulePanelRetry();
        }
    };
    private final Runnable refresh = () -> {
        refreshScheduled = false;
        loadCalendars();
        scheduleRefresh();
    };
    private final BroadcastReceiver systemEvents = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
            if (ConnectivityManager.CONNECTIVITY_ACTION.equals(action)) {
                boolean nowConnected = networkAvailable();
                if (!nowConnected && connected) {
                    panelFailed = true;
                    panelStatus.setText("Home Assistant unavailable - waiting for network");
                    panelStatus.setVisibility(View.VISIBLE);
                    if (extensionReady) schedulePanelRetry();
                } else if (nowConnected && !connected) {
                    if (extensionReady) loadPanel();
                    loadCalendars();
                }
                connected = nowConnected;
            } else if (Intent.ACTION_DREAMING_STARTED.equals(action)) {
                dreamWasActive = true;
            } else if (Intent.ACTION_DREAMING_STOPPED.equals(action) && active) {
                fadeFromDream();
            }
        }
    };

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("frame-calendar", MODE_PRIVATE);
        importConfig(getIntent());
        zone = ZoneId.of(prefs.getString("timezone", "Europe/London"));
        month = state == null ? YearMonth.now(zone) : YearMonth.parse(state.getString("month"));
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
        buildUi();
        session = new GeckoSession();
        browser = new GeckoView(this);
        browser.setBackgroundColor(CalendarView.BACKGROUND);
        browser.coverUntilFirstPaint(CalendarView.BACKGROUND);
        View surface = browser.getChildAt(0);
        if (surface instanceof SurfaceView) {
            ((SurfaceView) surface).getHolder().addCallback(new SurfaceHolder.Callback() {
                @Override public void surfaceCreated(SurfaceHolder holder) { }
                @Override public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) { }
                @Override public void surfaceDestroyed(SurfaceHolder holder) {
                    handler.post(() -> {
                        if (!isDestroyed() && session != null && session.isOpen()) session.setActive(true);
                    });
                }
            });
        }
        ((LinearLayout) panelStatus.getParent()).addView(browser, new LinearLayout.LayoutParams(-1, 0, 1));
        session.setNavigationDelegate(new GeckoSession.NavigationDelegate() {
            @Override public GeckoResult<String> onLoadError(GeckoSession s, String uri,
                    org.mozilla.geckoview.WebRequestError error) {
                panelStatus.setText("Home Assistant unavailable - check Wi-Fi; Reload to retry");
                panelStatus.setVisibility(View.VISIBLE);
                panelFailed = true;
                schedulePanelRetry();
                return GeckoResult.fromValue("data:text/html,<body style='background:%231e1e2e;color:%23cdd6f4'>Connection unavailable</body>");
            }
        });
        session.setProgressDelegate(new GeckoSession.ProgressDelegate() {
            @Override public void onPageStart(GeckoSession s, String url) {
                panelFailed = true;
                browser.coverUntilFirstPaint(CalendarView.BACKGROUND);
                schedulePanelRetry();
            }
            @Override public void onPageStop(GeckoSession s, boolean success) {
                if (!success) {
                    panelStatus.setText("Home Assistant unavailable - retrying shortly");
                    panelStatus.setVisibility(View.VISIBLE);
                    panelFailed = true;
                    schedulePanelRetry();
                }
            }
        });
        session.open(((FrameApplication) getApplication()).runtime());
        applyConsoleFlag(getIntent());
        browser.setSession(session);
        ((FrameApplication) getApplication()).runtime().getWebExtensionController()
                .ensureBuiltIn("resource://android/assets/frame-panel/", "frame-panel@framecalendar.local")
                .accept(extension -> handler.post(() -> {
                    if (isDestroyed() || !session.isOpen()) return;
                    session.getWebExtensionController().setMessageDelegate(extension, new WebExtension.MessageDelegate() {
                        @Override public GeckoResult<Object> onMessage(String app, Object message, WebExtension.MessageSender sender) {
                            if (sender.session != session || !sender.isTopLevel()
                                    || !sameOrigin(sender.url, prefs.getString("ha_url", ""))) return null;
                            if (!(message instanceof JSONObject)) return null;
                            JSONObject object = (JSONObject) message;
                            try {
                                if ("config".equals(object.optString("type"))) {
                                    JSONObject config = new JSONObject();
                                    config.put("url", prefs.getString("ha_url", ""));
                                    config.put("auth", new JSONObject(prefs.getString("ha_auth", "{}")));
                                    return GeckoResult.fromValue(config.toString());
                                }
                                if ("auth".equals(object.optString("type"))) {
                                    JSONObject auth = object.getJSONObject("auth");
                                    if (auth.has("refresh_token") && auth.has("clientId")) {
                                        prefs.edit().putString("ha_auth", auth.toString()).apply();
                                    }
                                } else if ("status".equals(object.optString("type"))) {
                                    String messageText = object.optString("text", "Home Assistant");
                                    panelStatus.setText(messageText);
                                    panelStatus.setVisibility("Frame - live".equals(messageText) ? View.GONE : View.VISIBLE);
                                    String state = object.optString("state", "connecting");
                                    panelFailed = !"ready".equals(state) && !"login".equals(state);
                                    if (!panelFailed) {
                                        handler.removeCallbacks(retryPanel);
                                        panelRetryScheduled = false;
                                    } else {
                                        schedulePanelRetry();
                                    }
                                }
                            } catch (JSONException e) {
                                panelStatus.setText("Home Assistant integration error - Reload to retry");
                                panelStatus.setVisibility(View.VISIBLE);
                            }
                            return null;
                        }
                    }, "frame");
                    extensionReady = true;
                    loadPanel();
                }), error -> handler.post(() -> {
                    if (isDestroyed()) return;
                    panelStatus.setText("Browser integration failed - restart the app");
                    panelStatus.setVisibility(View.VISIBLE);
                }));
        connected = networkAvailable();
        IntentFilter systemFilter = new IntentFilter(ConnectivityManager.CONNECTIVITY_ACTION);
        systemFilter.addAction(Intent.ACTION_DREAMING_STARTED);
        systemFilter.addAction(Intent.ACTION_DREAMING_STOPPED);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(systemEvents, systemFilter, Context.RECEIVER_EXPORTED);
        else registerReceiver(systemEvents, systemFilter);
        applyHome(getIntent());
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.HORIZONTAL);
        root.setBackgroundColor(CalendarView.BACKGROUND);
        LinearLayout left = new LinearLayout(this), right = new LinearLayout(this);
        FrameLayout leftPane = new FrameLayout(this);
        left.setOrientation(LinearLayout.VERTICAL);
        right.setOrientation(LinearLayout.VERTICAL);
        root.addView(leftPane, new LinearLayout.LayoutParams(0, -1, 3));
        leftPane.addView(left, new FrameLayout.LayoutParams(-1, -1));
        root.addView(right, new LinearLayout.LayoutParams(0, -1, 1));
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(10, 4, 10, 4);
        left.addView(toolbar, new LinearLayout.LayoutParams(-1, 56));
        iconButton(toolbar, R.drawable.mdi_calendar_today, "Today", () -> changeMonth(YearMonth.now(zone)));
        iconButton(toolbar, R.drawable.mdi_chevron_left, "Previous month", () -> changeMonth(month.minusMonths(1)));
        iconButton(toolbar, R.drawable.mdi_chevron_right, "Next month", () -> changeMonth(month.plusMonths(1)));
        monthTitle = text("", 23);
        toolbar.addView(monthTitle, new LinearLayout.LayoutParams(0, -2, 1));
        iconButton(toolbar, R.drawable.mdi_reload, "Reload", () -> { loadCalendars(); loadPanel(); });
        iconButton(toolbar, R.drawable.mdi_cog, "Settings", this::controls);
        calendar = new CalendarView(this);
        left.addView(calendar, new LinearLayout.LayoutParams(-1, 0, 1));
        previews = new MonthPreviewsView(this);
        left.addView(previews, new LinearLayout.LayoutParams(-1, 160));
        status = text("", 11);
        status.setPadding(12, 6, 10, 6);
        status.setVisibility(View.GONE);
        left.addView(status);
        syncIndicator = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        syncIndicator.setIndeterminate(true);
        syncIndicator.setIndeterminateTintList(ColorStateList.valueOf(CalendarView.TODAY));
        syncIndicator.setVisibility(View.GONE);
        leftPane.addView(syncIndicator, new FrameLayout.LayoutParams(-1, 2, Gravity.BOTTOM));
        panelStatus = text("Home Assistant - connecting...", 11);
        panelStatus.setPadding(8, 8, 8, 8);
        right.addView(panelStatus);
        setContentView(root);
        calendar.show(month, Collections.emptyList(), zone);
        previews.show(month, Collections.emptyList(), zone);
        updateMonthTitle();
    }

    private TextView text(String label, int size) {
        TextView view = new TextView(this);
        view.setText(label);
        view.setTextColor(CalendarView.TEXT);
        view.setTextSize(size);
        return view;
    }

    private void iconButton(LinearLayout row, int drawable, String label, Runnable action) {
        ImageButton button = new ImageButton(this);
        button.setImageResource(drawable);
        button.setColorFilter(CalendarView.MUTED);
        button.setContentDescription(label);
        android.util.TypedValue background = new android.util.TypedValue();
        getTheme().resolveAttribute(android.R.attr.selectableItemBackgroundBorderless, background, true);
        button.setBackgroundResource(background.resourceId);
        row.addView(button, new LinearLayout.LayoutParams(44, 44));
        button.setOnClickListener(view -> action.run());
    }

    private void changeMonth(YearMonth value) {
        month = value;
        updateMonthTitle();
        if (!showCachedCalendars()) {
            calendar.show(month, Collections.emptyList(), zone);
            previews.show(month, Collections.emptyList(), zone);
            loadCalendars();
        }
    }

    private void updateMonthTitle() {
        monthTitle.setText("  " + month.format(DateTimeFormatter.ofPattern("MMMM yyyy", Locale.UK)));
    }

    private void loadCalendars() {
        if (loading) { calendarRefreshPending = true; return; }
        loading = true;
        syncIndicator.setVisibility(View.VISIBLE);
        int request = generation;
        YearMonth requestedMonth = month;
        ZoneId requestedZone = zone;
        CalendarRange range = CalendarRange.around(requestedMonth, requestedZone);
        boolean needSaved = cachedRange == null || !cachedRange.covers(requestedMonth, requestedZone);
        worker.execute(() -> {
            CalendarStore store = new CalendarStore(this, prefs);
            if (needSaved) {
                CalendarStore.Result saved = store.loadCached(range.from, range.until, requestedZone);
                handler.post(() -> {
                    if (isDestroyed() || request != generation || !range.covers(month, zone)) return;
                    cachedRange = range;
                    cachedCalendars = saved;
                    showCachedCalendars();
                });
            }
            CalendarStore.Result result = store.load(range.from, range.until, requestedZone);
            handler.post(() -> {
                loading = false;
                if (isDestroyed()) return;
                boolean refreshAgain = calendarRefreshPending;
                calendarRefreshPending = false;
                if (request == generation) {
                    cachedRange = range;
                    cachedCalendars = result;
                    if (showCachedCalendars()) {
                        calendarStatus(android.text.TextUtils.join("  |  ", result.notices));
                    }
                }
                if (refreshAgain || request != generation || cachedRange == null || !cachedRange.covers(month, zone)) {
                    loadCalendars();
                } else syncIndicator.setVisibility(View.GONE);
            });
        });
    }

    private boolean showCachedCalendars() {
        if (cachedRange == null || cachedCalendars == null || !cachedRange.covers(month, zone)) return false;
        calendar.show(month, cachedCalendars.events, zone);
        previews.show(month, cachedCalendars.events, zone);
        return true;
    }

    private void calendarStatus(String message) {
        status.setText(message);
        status.setVisibility(message.isEmpty() ? View.GONE : View.VISIBLE);
    }

    private void loadPanel() {
        if (!extensionReady) return;
        panelStatus.setVisibility(View.VISIBLE);
        String url = prefs.getString("ha_url", "");
        if (url.isEmpty()) {
            panelStatus.setText("Connect Home Assistant in Settings");
            panelFailed = false;
            handler.removeCallbacks(retryPanel);
            panelRetryScheduled = false;
            return;
        }
        panelStatus.setText("Home Assistant - connecting...");
        panelFailed = true;
        browser.coverUntilFirstPaint(CalendarView.BACKGROUND);
        schedulePanelRetry();
        session.loadUri(url);
    }

    private void schedulePanelRetry() {
        handler.removeCallbacks(retryPanel);
        handler.postDelayed(retryPanel, 30000);
        panelRetryScheduled = true;
    }

    private boolean networkAvailable() {
        ConnectivityManager manager = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
        NetworkInfo network = manager == null ? null : manager.getActiveNetworkInfo();
        return network != null && network.isConnected();
    }

    private void fadeFromDream() {
        if (!dreamWasActive) return;
        dreamWasActive = false;
        if (wakeFade != null) wakeFade.cancel();
        WindowManager.LayoutParams attributes = getWindow().getAttributes();
        attributes.alpha = 0f;
        getWindow().setAttributes(attributes);
        wakeFade = ValueAnimator.ofFloat(0f, 1f);
        wakeFade.setDuration(450);
        wakeFade.addUpdateListener(animation -> {
            WindowManager.LayoutParams frame = getWindow().getAttributes();
            frame.alpha = (Float) animation.getAnimatedValue();
            getWindow().setAttributes(frame);
        });
        wakeFade.start();
    }

    private void controls() {
        new AlertDialog.Builder(this).setTitle("Frame Calendar")
                .setItems(new String[]{"Connections and time zone", "Android settings", "Wi-Fi settings",
                        "Reload calendars and panel", "Use another Home app"}, (dialog, choice) -> {
                    if (choice == 0) connections();
                    if (choice == 1) startActivity(new Intent(Settings.ACTION_SETTINGS));
                    if (choice == 2) startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS));
                    if (choice == 3) { loadCalendars(); loadPanel(); }
                    if (choice == 4) {
                        getPackageManager().setComponentEnabledSetting(new ComponentName(this, "com.wesbos.framecalendar.Home"),
                                PackageManager.COMPONENT_ENABLED_STATE_DISABLED, PackageManager.DONT_KILL_APP);
                        startActivity(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME));
                    }
                }).setNegativeButton("Close", null).show();
    }

    private void connections() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(24, 10, 24, 10);
        scroll.addView(form);
        form.addView(text("Use Google Calendar Settings > Integrate calendar > Secret address in iCal format."
                + "\nAlternatively enter ha:calendar.entity_id for a Home Assistant calendar."
                + "\nSign in to Home Assistant in the right-hand panel. Keep feed links private.", 13));
        String[] keys = {"personal", "family", "tripit", "holidays", "ha_url", "timezone"};
        String[] labels = {"Martin", "Catherine", "TripIt private feed", "UK holidays",
                "Home Assistant panel URL", "Time zone"};
        EditText[] fields = new EditText[keys.length];
        for (int i = 0; i < keys.length; i++) {
            form.addView(text(labels[i], 14));
            fields[i] = new EditText(this);
            fields[i].setText(prefs.getString(keys[i], "timezone".equals(keys[i]) ? "Europe/London" : ""));
            fields[i].setInputType(i < CalendarStore.KEYS.length ? InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD
                    : InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
            fields[i].setTextColor(Color.WHITE);
            fields[i].setSingleLine(true);
            form.addView(fields[i]);
        }
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("Private connections").setView(scroll)
                .setPositiveButton("Save", null).setNegativeButton("Cancel", null).create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            try {
                JSONObject config = new JSONObject();
                for (int i = 0; i < keys.length; i++) config.put(keys[i], fields[i].getText().toString().trim());
                validate(config);
                String previousUrl = prefs.getString("ha_url", "");
                SharedPreferences.Editor edit = prefs.edit();
                for (String key : keys) edit.putString(key, config.getString(key));
                if (!sameOrigin(previousUrl, config.getString("ha_url"))) edit.remove("ha_auth");
                edit.apply();
                zone = ZoneId.of(config.getString("timezone"));
                generation++;
                cachedRange = null;
                cachedCalendars = null;
                loadCalendars();
                loadPanel();
                dialog.dismiss();
            } catch (IllegalArgumentException | JSONException e) {
                Toast.makeText(this, "Check the time zone, HTTPS feed links and panel URL", Toast.LENGTH_LONG).show();
            }
        }));
        dialog.show();
    }

    private static void validate(JSONObject config) throws JSONException {
        ZoneId.of(config.optString("timezone", "Europe/London"));
        for (String key : CalendarStore.KEYS) {
            String value = config.optString(key);
            if (!value.isEmpty() && !value.matches("ha:calendar\\.[a-z0-9_]+")
                    && !validUrl(value, false)) throw new IllegalArgumentException("Invalid feed URL");
        }
        if (!config.optString("ha_url").isEmpty() && !validUrl(config.getString("ha_url"), true)) {
            throw new IllegalArgumentException("Invalid panel URL");
        }
    }

    private static boolean validUrl(String value, boolean allowHttp) {
        try {
            URI uri = URI.create(value);
            return uri.getHost() != null && uri.getUserInfo() == null
                    && ("https".equals(uri.getScheme()) || (allowHttp && "http".equals(uri.getScheme())));
        } catch (IllegalArgumentException e) { return false; }
    }

    private static boolean sameOrigin(String a, String b) {
        try {
            URI left = URI.create(a), right = URI.create(b);
            return left.getHost() != null && left.getHost().equalsIgnoreCase(right.getHost())
                    && left.getScheme().equals(right.getScheme()) && left.getPort() == right.getPort();
        } catch (IllegalArgumentException | NullPointerException e) { return false; }
    }

    private void importConfig(Intent intent) {
        if (!intent.getBooleanExtra("import_config", false)) return;
        File file = new File(getFilesDir(), "config-import.json");
        try (FileInputStream in = new FileInputStream(file)) {
            JSONObject config = new JSONObject(CalendarStore.read(in));
            validate(config);
            SharedPreferences.Editor edit = prefs.edit();
            for (String key : new String[]{"personal", "family", "tripit", "holidays", "ha_url", "timezone"}) {
                if (config.has(key)) edit.putString(key, config.getString(key));
            }
            if (config.has("ha_auth")) edit.putString("ha_auth", config.getJSONObject("ha_auth").toString());
            if (!edit.commit()) throw new IOException("Configuration could not be saved");
            if (!file.delete()) android.util.Log.w("FrameCalendar", "Private import file could not be removed");
        } catch (IOException | JSONException | IllegalArgumentException e) {
            Toast.makeText(this, "Private configuration import failed", Toast.LENGTH_LONG).show();
            android.util.Log.w("FrameCalendar", "Configuration import failed: " + e.getClass().getSimpleName());
        }
    }

    private void applyHome(Intent intent) {
        if (!intent.hasExtra("home")) return;
        getPackageManager().setComponentEnabledSetting(new ComponentName(this, "com.wesbos.framecalendar.Home"),
                intent.getBooleanExtra("home", false) ? PackageManager.COMPONENT_ENABLED_STATE_ENABLED
                        : PackageManager.COMPONENT_ENABLED_STATE_DISABLED, PackageManager.DONT_KILL_APP);
    }

    private void applyConsoleFlag(Intent intent) {
        if (intent.hasExtra("debug")) {
            ((FrameApplication) getApplication()).runtime().getSettings()
                    .setConsoleOutputEnabled(intent.getBooleanExtra("debug", false));
        }
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        importConfig(intent);
        applyHome(intent);
        applyConsoleFlag(intent);
        if (intent.getBooleanExtra("import_config", false)) {
            zone = ZoneId.of(prefs.getString("timezone", "Europe/London"));
            generation++;
            cachedRange = null;
            cachedCalendars = null;
            loadCalendars();
            loadPanel();
        }
    }

    private void scheduleRefresh() {
        handler.removeCallbacks(refresh);
        handler.postDelayed(refresh, 5 * 60 * 1000);
        refreshScheduled = true;
    }

    @Override protected void onResume() {
        super.onResume();
        active = true;
        NavigationService.setCalendarVisible(true);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        if (session != null) session.setActive(true);
        if (dreamWasActive) fadeFromDream();
        if (panelFailed && !panelRetryScheduled) schedulePanelRetry();
        if (cachedRange == null && !loading) loadCalendars();
        if (!refreshScheduled) scheduleRefresh();
    }

    @Override protected void onPause() {
        active = false;
        NavigationService.setCalendarVisible(false);
        super.onPause();
        handler.postDelayed(() -> {
            if (!isDestroyed() && session != null && session.isOpen()) session.setActive(true);
        }, 500);
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        state.putString("month", month.toString());
        super.onSaveInstanceState(state);
    }

    @Override protected void onDestroy() {
        unregisterReceiver(systemEvents);
        if (wakeFade != null) wakeFade.cancel();
        handler.removeCallbacksAndMessages(null);
        worker.shutdownNow();
        if (session != null) session.close();
        super.onDestroy();
    }

    @Override public void onBackPressed() { controls(); }
}
