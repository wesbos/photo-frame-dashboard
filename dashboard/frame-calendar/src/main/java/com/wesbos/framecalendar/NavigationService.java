package com.wesbos.framecalendar;

import android.accessibilityservice.AccessibilityService;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.ProviderInfo;
import android.database.Cursor;
import android.database.SQLException;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.CancellationSignal;
import android.os.Handler;
import android.os.OperationCanceledException;
import android.util.Log;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Optional navigation for frames without Android's navigation bar. */
public class NavigationService extends AccessibilityService {
    private static final String DREAM_AUTHORITY = "io.github.martinwoodward.iphotoframesaver.playback";
    private static final String DREAM_PACKAGE = "io.github.martinwoodward.iphotoframesaver";
    private static NavigationService instance;
    private static boolean calendarVisible;
    private final Handler handler = new Handler();
    private WindowManager windows;
    private LinearLayout bar;
    private WindowManager.LayoutParams position;
    private boolean attached, dreaming, receiverRegistered;
    private int dreamVersion;
    private CancellationSignal dreamQuery;
    private final BroadcastReceiver dreamEvents = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            dreamVersion++;
            if (Intent.ACTION_DREAMING_STARTED.equals(intent.getAction())) dreaming = true;
            else if (Intent.ACTION_DREAMING_STOPPED.equals(intent.getAction())) dreaming = false;
            updateVisibility();
        }
    };

    @Override protected void onServiceConnected() {
        if (bar != null) return;
        instance = this;
        windows = (WindowManager) getSystemService(WINDOW_SERVICE);
        bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(4), dp(4), dp(4), dp(4));
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.rgb(28, 28, 28));
        background.setCornerRadius(dp(14));
        background.setStroke(dp(1), Color.GRAY);
        bar.setBackground(background);
        position = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT);
        position.gravity = Gravity.BOTTOM | Gravity.RIGHT;
        position.x = getSharedPreferences("navigation", MODE_PRIVATE).getInt("x", dp(12));
        position.y = getSharedPreferences("navigation", MODE_PRIVATE).getInt("y", dp(12));
        position.setTitle("Frame Calendar navigation");

        TextView handle = new TextView(this);
        handle.setText("\u22ee");
        handle.setTextColor(Color.LTGRAY);
        handle.setTextSize(26);
        handle.setGravity(Gravity.CENTER);
        handle.setContentDescription("Drag navigation buttons");
        bar.addView(handle, new LinearLayout.LayoutParams(dp(40), dp(48)));
        handle.setOnTouchListener(new View.OnTouchListener() {
            float startX, startY;
            int oldX, oldY;
            @Override public boolean onTouch(View view, MotionEvent event) {
                if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                    startX = event.getRawX();
                    startY = event.getRawY();
                    oldX = position.x;
                    oldY = position.y;
                } else if (event.getActionMasked() == MotionEvent.ACTION_MOVE) {
                    int maxX = Math.max(0, getResources().getDisplayMetrics().widthPixels - bar.getWidth());
                    int maxY = Math.max(0, getResources().getDisplayMetrics().heightPixels - bar.getHeight());
                    position.x = Math.max(0, Math.min(maxX, oldX - (int) (event.getRawX() - startX)));
                    position.y = Math.max(0, Math.min(maxY, oldY - (int) (event.getRawY() - startY)));
                    windows.updateViewLayout(bar, position);
                } else if (event.getActionMasked() == MotionEvent.ACTION_UP) {
                    getSharedPreferences("navigation", MODE_PRIVATE).edit()
                            .putInt("x", position.x).putInt("y", position.y).apply();
                    view.performClick();
                }
                return true;
            }
        });
        addButton("Back", view -> performGlobalAction(GLOBAL_ACTION_BACK));
        addButton("Dashboard", view -> startActivity(new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP)));
        IntentFilter filter = new IntentFilter(Intent.ACTION_DREAMING_STARTED);
        filter.addAction(Intent.ACTION_DREAMING_STOPPED);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(dreamEvents, filter, Context.RECEIVER_EXPORTED);
        else registerReceiver(dreamEvents, filter);
        receiverRegistered = true;
        restoreDreamState();
    }

    private void restoreDreamState() {
        dreaming = true;
        int version = dreamVersion;
        CancellationSignal signal = new CancellationSignal();
        dreamQuery = signal;
        Runnable timeout = () -> {
            signal.cancel();
            if (receiverRegistered && version == dreamVersion) {
                dreamVersion++;
                Log.w("FrameCalendar", "Screensaver state timed out; showing navigation");
                dreaming = false;
                updateVisibility();
            }
        };
        handler.postDelayed(timeout, 2000);
        new Thread(() -> {
            boolean value = false, failed = false;
            try {
                ProviderInfo provider = getPackageManager().resolveContentProvider(DREAM_AUTHORITY, 0);
                if (provider != null && DREAM_PACKAGE.equals(provider.packageName)) {
                    try (Cursor cursor = getContentResolver().query(
                            Uri.parse("content://" + DREAM_AUTHORITY + "/dream"),
                            new String[]{"active"}, null, null, null, signal)) {
                        if (cursor != null && cursor.moveToFirst() && !cursor.isNull(0)) {
                            int state = cursor.getInt(0);
                            value = state == 1;
                            failed = state != 0 && state != 1;
                        } else failed = true;
                    }
                }
            } catch (SecurityException | IllegalArgumentException | IllegalStateException
                    | SQLException | OperationCanceledException error) {
                failed = true;
            }
            boolean active = value, error = failed;
            handler.post(() -> {
                handler.removeCallbacks(timeout);
                if (!receiverRegistered || version != dreamVersion) return;
                if (error) Log.w("FrameCalendar", "Screensaver state unavailable; showing navigation");
                dreaming = active;
                updateVisibility();
            });
        }, "frame-dream-state").start();
    }

    private void updateVisibility() {
        if (bar == null) return;
        boolean visible = !dreaming && !calendarVisible;
        if (visible && !attached) {
            try {
                windows.addView(bar, position);
                attached = true;
            } catch (WindowManager.BadTokenException error) {
                Log.w("FrameCalendar", "Navigation overlay unavailable; accessibility service disconnected");
            }
        } else if (!visible && attached) {
            windows.removeView(bar);
            attached = false;
        }
    }

    private void addButton(String label, View.OnClickListener click) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextColor(Color.WHITE);
        button.setTextSize(17);
        button.setBackgroundColor(Color.TRANSPARENT);
        button.setPadding(dp(14), 0, dp(14), 0);
        button.setOnClickListener(click);
        bar.addView(button, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, dp(48)));
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    static void setCalendarVisible(boolean visible) {
        calendarVisible = visible;
        if (instance != null) instance.updateVisibility();
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent event) { }
    @Override public void onInterrupt() { }
    @Override public void onDestroy() {
        if (receiverRegistered) unregisterReceiver(dreamEvents);
        receiverRegistered = false;
        if (dreamQuery != null) dreamQuery.cancel();
        handler.removeCallbacksAndMessages(null);
        if (attached) windows.removeView(bar);
        attached = false;
        if (instance == this) instance = null;
        bar = null;
        super.onDestroy();
    }
}
