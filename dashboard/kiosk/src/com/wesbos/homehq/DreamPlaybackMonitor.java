package com.wesbos.homehq;

import android.content.ContentResolver;
import android.content.Context;
import android.content.pm.ProviderInfo;
import android.database.ContentObserver;
import android.database.Cursor;
import android.database.SQLException;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.os.OperationCanceledException;
import android.util.Log;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Observes only the photo screensaver's public, live playback flag. */
final class DreamPlaybackMonitor {
  private static final String TAG = "HomeHQ";
  private static final String AUTHORITY =
      "io.github.martinwoodward.iphotoframesaver.playback";
  private static final String PACKAGE = "io.github.martinwoodward.iphotoframesaver";
  private static final Uri STATE = Uri.parse("content://" + AUTHORITY + "/dream");
  private static final long POLL_MS = 5000;
  private static final long QUERY_TIMEOUT_MS = 2000;

  interface Listener {
    void onDreamingChanged(boolean active);
  }

  private final Context context;
  private final Listener listener;
  private final Handler main = new Handler(Looper.getMainLooper());
  private final ExecutorService worker = Executors.newSingleThreadExecutor();
  private boolean running;
  private boolean observing;
  private boolean querying;
  private boolean refreshRequested;
  private boolean timedOut;
  private boolean active;
  private boolean failed;

  private final Runnable poll = new Runnable() {
    @Override public void run() { refresh(); }
  };
  private final Runnable timeout = new Runnable() {
    @Override public void run() {
      timedOut = true;
      reportFailure();
      publish(false);
    }
  };
  private final ContentObserver observer = new ContentObserver(main) {
    @Override public void onChange(boolean selfChange) { refresh(); }
  };

  DreamPlaybackMonitor(Context context, Listener listener) {
    this.context = context;
    this.listener = listener;
  }

  void start() {
    if (running) return;
    running = true;
    try {
      context.getContentResolver().registerContentObserver(STATE, false, observer);
      observing = true;
    } catch (SecurityException | IllegalArgumentException error) {
      reportFailure();
    }
    refresh();
  }

  private void refresh() {
    if (!running) return;
    main.removeCallbacks(poll);
    if (querying) {
      refreshRequested = true;
      return;
    }
    querying = true;
    refreshRequested = false;
    timedOut = false;
    main.postDelayed(timeout, QUERY_TIMEOUT_MS);
    worker.execute(new Runnable() {
      @Override public void run() {
        boolean value = false;
        boolean queryFailed = false;
        try {
          ProviderInfo provider = context.getPackageManager().resolveContentProvider(AUTHORITY, 0);
          if (provider != null && PACKAGE.equals(provider.packageName)) {
            ContentResolver resolver = context.getContentResolver();
            try (Cursor cursor = resolver.query(
                STATE, new String[] {"active"}, null, null, null)) {
              if (cursor != null && cursor.moveToFirst()) {
                int column = cursor.getColumnIndex("active");
                if (column >= 0 && !cursor.isNull(column)) {
                  int state = cursor.getInt(column);
                  value = state == 1;
                  queryFailed = state != 0 && state != 1;
                } else {
                  queryFailed = true;
                }
              } else {
                queryFailed = true;
              }
            }
          }
        } catch (SecurityException | IllegalArgumentException | IllegalStateException
            | SQLException | OperationCanceledException error) {
          queryFailed = true;
        }
        final boolean result = value;
        final boolean error = queryFailed;
        main.post(new Runnable() {
          @Override public void run() {
            querying = false;
            main.removeCallbacks(timeout);
            if (!running) return;
            if (error) reportFailure();
            else if (!timedOut) failed = false;
            publish(!timedOut && !error && result);
            if (refreshRequested) refresh();
            else main.postDelayed(poll, POLL_MS);
          }
        });
      }
    });
  }

  private void reportFailure() {
    if (!failed) Log.w(TAG, "Photo screensaver state unavailable; keeping navigation visible");
    failed = true;
  }

  private void publish(boolean value) {
    if (active == value) return;
    active = value;
    listener.onDreamingChanged(value);
  }

  void stop() {
    running = false;
    main.removeCallbacks(poll);
    main.removeCallbacks(timeout);
    if (observing) {
      context.getContentResolver().unregisterContentObserver(observer);
      observing = false;
    }
    worker.shutdownNow();
  }
}
