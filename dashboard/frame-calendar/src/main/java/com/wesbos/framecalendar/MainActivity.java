package com.wesbos.framecalendar;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ComponentName;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
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
    private TextView monthTitle, status, panelStatus;
    private GeckoSession session;
    private ZoneId zone;
    private YearMonth month;
    private int generation;
    private boolean active, loading, panelFailed;
    private final Runnable retryPanel = () -> { if (active) loadPanel(); };
    private final Runnable refresh = () -> {
        if (active) {
            loadCalendars();
            scheduleRefresh();
        }
    };

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("frame-calendar", MODE_PRIVATE);
        importConfig(getIntent());
        zone = ZoneId.of(prefs.getString("timezone", "Europe/London"));
        month = state == null ? YearMonth.now(zone) : YearMonth.parse(state.getString("month"));
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        buildUi();
        session = new GeckoSession();
        GeckoView browser = new GeckoView(this);
        ((LinearLayout) panelStatus.getParent()).addView(browser, new LinearLayout.LayoutParams(-1, 0, 1));
        session.setNavigationDelegate(new GeckoSession.NavigationDelegate() {
            @Override public GeckoResult<String> onLoadError(GeckoSession s, String uri,
                    org.mozilla.geckoview.WebRequestError error) {
                panelStatus.setText("Home Assistant unavailable - check Wi-Fi; Reload to retry");
                panelFailed = true;
                handler.removeCallbacks(retryPanel);
                handler.postDelayed(retryPanel, 30000);
                return GeckoResult.fromValue("data:text/html,<body style='background:%231e1e2e;color:%23cdd6f4'>Connection unavailable</body>");
            }
        });
        session.setProgressDelegate(new GeckoSession.ProgressDelegate() {
            @Override public void onPageStop(GeckoSession s, boolean success) {
                if (success && !panelFailed) handler.removeCallbacks(retryPanel);
                else {
                    panelStatus.setText("Home Assistant unavailable - retrying shortly");
                    handler.removeCallbacks(retryPanel);
                    handler.postDelayed(retryPanel, 30000);
                }
            }
        });
        session.open(((FrameApplication) getApplication()).runtime());
        browser.setSession(session);
        ((FrameApplication) getApplication()).runtime().getWebExtensionController()
                .ensureBuiltIn("resource://android/assets/frame-panel/", "frame-panel@framecalendar.local")
                .accept(extension -> handler.post(() -> {
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
                                    panelStatus.setText(object.optString("text", "Home Assistant"));
                                }
                            } catch (JSONException e) {
                                panelStatus.setText("Home Assistant integration error - Reload to retry");
                            }
                            return null;
                        }
                    }, "frame");
                    loadPanel();
                }), error -> handler.post(() -> panelStatus.setText("Browser integration failed - restart the app")));
        applyHome(getIntent());
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.HORIZONTAL);
        root.setBackgroundColor(CalendarView.BACKGROUND);
        LinearLayout left = new LinearLayout(this), right = new LinearLayout(this);
        left.setOrientation(LinearLayout.VERTICAL);
        right.setOrientation(LinearLayout.VERTICAL);
        root.addView(left, new LinearLayout.LayoutParams(0, -1, 3));
        root.addView(right, new LinearLayout.LayoutParams(0, -1, 1));
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(10, 4, 10, 4);
        left.addView(toolbar, new LinearLayout.LayoutParams(-1, 56));
        button(toolbar, "Today", () -> changeMonth(YearMonth.now(zone)));
        button(toolbar, "<", () -> changeMonth(month.minusMonths(1)));
        button(toolbar, ">", () -> changeMonth(month.plusMonths(1)));
        monthTitle = text("", 23);
        toolbar.addView(monthTitle, new LinearLayout.LayoutParams(0, -2, 1));
        button(toolbar, "Reload", () -> { loadCalendars(); loadPanel(); });
        button(toolbar, "Settings", this::controls);
        LinearLayout legend = new LinearLayout(this);
        legend.setPadding(14, 0, 14, 6);
        for (int i = 0; i < CalendarStore.NAMES.length; i++) {
            TextView label = text(CalendarStore.NAMES[i] + "    ", 12);
            label.setTextColor(CalendarStore.COLORS[i]);
            legend.addView(label);
        }
        left.addView(legend);
        calendar = new CalendarView(this);
        left.addView(calendar, new LinearLayout.LayoutParams(-1, 0, 1));
        status = text("Loading calendars...", 11);
        status.setPadding(12, 6, 10, 6);
        left.addView(status);
        panelStatus = text("Home Assistant - connecting...", 11);
        panelStatus.setPadding(8, 8, 8, 8);
        right.addView(panelStatus);
        setContentView(root);
        calendar.show(month, Collections.emptyList(), zone);
        updateMonthTitle();
    }

    private TextView text(String label, int size) {
        TextView view = new TextView(this);
        view.setText(label);
        view.setTextColor(CalendarView.TEXT);
        view.setTextSize(size);
        return view;
    }

    private void button(LinearLayout row, String label, Runnable action) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(CalendarView.TEXT);
        button.setTextSize(12);
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        row.addView(button, new LinearLayout.LayoutParams(-2, 44));
        button.setOnClickListener(view -> action.run());
    }

    private void changeMonth(YearMonth value) {
        month = value;
        generation++;
        calendar.show(month, Collections.emptyList(), zone);
        updateMonthTitle();
        loadCalendars();
    }

    private void updateMonthTitle() {
        monthTitle.setText("  " + month.format(DateTimeFormatter.ofPattern("MMMM yyyy", Locale.UK)));
    }

    private void loadCalendars() {
        if (loading) { status.setText("Calendar refresh queued..."); return; }
        loading = true;
        int request = ++generation;
        YearMonth requestedMonth = month;
        ZoneId requestedZone = zone;
        CalendarLayout layout = new CalendarLayout(requestedMonth, Collections.emptyList(), requestedZone);
        status.setText("Syncing calendars...");
        worker.execute(() -> {
            CalendarStore.Result result = new CalendarStore(this, prefs)
                    .load(layout.first, layout.first.plusDays(layout.weeks * 7L), requestedZone);
            handler.post(() -> {
                loading = false;
                if (!active) return;
                if (request != generation) { loadCalendars(); return; }
                calendar.show(requestedMonth, result.events, requestedZone);
                status.setText(result.notices.isEmpty() ? "Updated " + java.time.LocalTime.now(zone)
                        .format(DateTimeFormatter.ofPattern("HH:mm")) + "  -  refreshes every 5 minutes"
                        : android.text.TextUtils.join("  |  ", result.notices));
            });
        });
    }

    private void loadPanel() {
        String url = prefs.getString("ha_url", "");
        if (url.isEmpty()) {
            panelStatus.setText("Connect Home Assistant in Settings");
            return;
        }
        panelStatus.setText("Home Assistant - connecting...");
        panelFailed = false;
        session.loadUri(url);
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
        String[] keys = {"personal", "family", "tripit", "ha_url", "timezone"};
        String[] labels = {"Personal (Woodwardweb)", "Catherine Woodward", "TripIt private feed",
                "Home Assistant panel URL", "Time zone"};
        EditText[] fields = new EditText[keys.length];
        for (int i = 0; i < keys.length; i++) {
            form.addView(text(labels[i], 14));
            fields[i] = new EditText(this);
            fields[i].setText(prefs.getString(keys[i], i == 4 ? "Europe/London" : ""));
            fields[i].setInputType(i < 3 ? InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD
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
            for (String key : new String[]{"personal", "family", "tripit", "ha_url", "timezone"}) {
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

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        importConfig(intent);
        applyHome(intent);
        zone = ZoneId.of(prefs.getString("timezone", "Europe/London"));
        generation++;
        loadCalendars();
        loadPanel();
    }

    private void scheduleRefresh() {
        handler.removeCallbacks(refresh);
        handler.postDelayed(refresh, 5 * 60 * 1000);
    }

    @Override protected void onResume() {
        super.onResume();
        active = true;
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        if (session != null) session.setActive(true);
        if (panelFailed) handler.postDelayed(retryPanel, 30000);
        loadCalendars();
        scheduleRefresh();
    }

    @Override protected void onPause() {
        active = false;
        handler.removeCallbacks(refresh);
        handler.removeCallbacks(retryPanel);
        if (session != null) session.setActive(false);
        super.onPause();
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        state.putString("month", month.toString());
        super.onSaveInstanceState(state);
    }

    @Override protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        worker.shutdownNow();
        if (session != null) session.close();
        super.onDestroy();
    }

    @Override public void onBackPressed() { controls(); }
}
