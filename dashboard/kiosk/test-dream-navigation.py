#!/usr/bin/env python3
"""Exercise the real playback monitor and navigation visibility with host Android fakes."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
service = (ROOT / "src/com/wesbos/homehq/NavigationService.java").read_text()
visibility = service[service.index("  private void updateVisibility() {"):]
visibility = visibility[:visibility.index("\n  private int dp(")]

FAKES = {
    "android/net/Uri.java": """
package android.net;
public class Uri {
  final String value;
  private Uri(String value) { this.value = value; }
  public static Uri parse(String value) { return new Uri(value); }
  public String toString() { return value; }
}
""",
    "android/os/Looper.java": """
package android.os;
public class Looper { public static Looper getMainLooper() { return new Looper(); } }
""",
    "android/os/Handler.java": """
package android.os;
import java.util.*;
import java.util.concurrent.*;
public class Handler {
  public static final BlockingQueue<Runnable> ready = new LinkedBlockingQueue<>();
  public static final Map<Runnable, Long> delayed = new LinkedHashMap<>();
  public Handler(Looper looper) {}
  public boolean post(Runnable task) { ready.add(task); return true; }
  public boolean postDelayed(Runnable task, long delay) {
    delayed.put(task, delay); return true;
  }
  public void removeCallbacks(Runnable task) { delayed.remove(task); ready.remove(task); }
  public static void completeQuery() throws Exception {
    Runnable task = ready.poll(3, TimeUnit.SECONDS);
    if (task == null) throw new AssertionError("No query result");
    task.run();
  }
  public static void advance(long delay) {
    for (Map.Entry<Runnable, Long> entry : new ArrayList<>(delayed.entrySet())) {
      if (entry.getValue() == delay) {
        delayed.remove(entry.getKey()); entry.getKey().run(); return;
      }
    }
    throw new AssertionError("No scheduled callback: " + delay);
  }
}
""",
    "android/os/OperationCanceledException.java": """
package android.os;
public class OperationCanceledException extends RuntimeException {}
""",
    "android/util/Log.java": """
package android.util;
public class Log {
  public static int warnings;
  public static int w(String tag, String value) {
    if (value.contains("content://")) throw new AssertionError("Provider URI logged");
    warnings++; return 0;
  }
}
""",
    "android/database/SQLException.java": """
package android.database;
public class SQLException extends RuntimeException {}
""",
    "android/database/ContentObserver.java": """
package android.database;
import android.os.Handler;
public abstract class ContentObserver {
  public ContentObserver(Handler handler) {}
  public void onChange(boolean selfChange) {}
}
""",
    "android/database/Cursor.java": """
package android.database;
public interface Cursor extends AutoCloseable {
  boolean moveToFirst();
  int getColumnIndex(String column);
  boolean isNull(int column);
  int getInt(int column);
  void close();
}
""",
    "android/content/pm/ProviderInfo.java": """
package android.content.pm;
public class ProviderInfo { public String packageName; }
""",
    "android/content/pm/PackageManager.java": """
package android.content.pm;
public class PackageManager {
  public ProviderInfo provider;
  public ProviderInfo resolveContentProvider(String authority, int flags) {
    if (!authority.equals("io.github.martinwoodward.iphotoframesaver.playback"))
      throw new AssertionError("Wrong authority");
    return provider;
  }
}
""",
    "android/content/ContentResolver.java": """
package android.content;
import android.database.*;
import android.net.Uri;
public abstract class ContentResolver {
  public ContentObserver observer;
  public boolean denyObserve;
  public void registerContentObserver(Uri uri, boolean children, ContentObserver value) {
    if (denyObserve) throw new SecurityException();
    if (children) throw new AssertionError("Overbroad observation");
    observer = value;
  }
  public void unregisterContentObserver(ContentObserver value) {
    if (observer != value) throw new AssertionError("Wrong observer");
    observer = null;
  }
  public abstract Cursor query(Uri uri, String[] projection, String selection,
      String[] args, String order);
}
""",
    "android/content/Context.java": """
package android.content;
import android.content.pm.PackageManager;
public abstract class Context {
  public abstract ContentResolver getContentResolver();
  public abstract PackageManager getPackageManager();
}
""",
}

HARNESS = r"""
package com.wesbos.homehq;
import android.content.*;
import android.content.pm.*;
import android.database.*;
import android.os.*;
import android.util.Log;
import java.util.concurrent.*;

public class DreamNavigationHarness {
  static int assertions;
  static void check(boolean value, String message) {
    assertions++;
    if (!value) throw new AssertionError(message);
  }
  static class Windows {
    int adds, removes;
    void addView(Object view, Object position) { adds++; }
    void removeView(Object view) { removes++; }
  }
  static class Navigation {
    Object bar = new Object(), position = new Object();
    Windows windows = new Windows();
    boolean dashboardVisible, dreaming, attached;
__VISIBILITY__
    void setDreaming(boolean value) { dreaming = value; updateVisibility(); }
    void dashboard(boolean value) { dashboardVisible = value; updateVisibility(); }
  }
  static class Resolver extends ContentResolver {
    volatile int value, queries, closed;
    volatile boolean invalidColumn, nullValue, empty, nullCursor;
    volatile RuntimeException failure;
    volatile CountDownLatch entered, release;
    public Cursor query(android.net.Uri uri, String[] projection, String selection,
        String[] args, String order) {
      check(uri.toString().equals(
          "content://io.github.martinwoodward.iphotoframesaver.playback/dream"), "URI");
      check(projection.length == 1 && projection[0].equals("active"), "Minimal projection");
      check(selection == null && args == null && order == null, "Read-only request");
      queries++;
      if (entered != null) entered.countDown();
      if (release != null) {
        try { release.await(); }
        catch (InterruptedException e) { throw new OperationCanceledException(); }
      }
      if (failure != null) throw failure;
      if (nullCursor) return null;
      return new Cursor() {
        public boolean moveToFirst() { return !empty; }
        public int getColumnIndex(String column) { return invalidColumn ? -1 : 0; }
        public boolean isNull(int column) { return nullValue; }
        public int getInt(int column) { return value; }
        public void close() { closed++; }
      };
    }
    void notifyState() { observer.onChange(false); }
  }
  static class App extends Context {
    Resolver resolver = new Resolver();
    PackageManager packages = new PackageManager();
    public ContentResolver getContentResolver() { return resolver; }
    public PackageManager getPackageManager() { return packages; }
    void provider(String owner) {
      packages.provider = new ProviderInfo();
      packages.provider.packageName = owner;
    }
  }
  static final String OWNER = "io.github.martinwoodward.iphotoframesaver";

  static void lifecycle() throws Exception {
    App app = new App();
    app.provider(OWNER);
    app.resolver.value = 1;
    Navigation nav = new Navigation();
    nav.updateVisibility();
    check(nav.attached, "Navigation initially available");
    DreamPlaybackMonitor monitor = new DreamPlaybackMonitor(app, nav::setDreaming);
    try {
      monitor.start();
      Handler.completeQuery();
      check(!nav.attached, "Hide during actual dream");
      check(app.resolver.closed == 1, "Close active cursor");
      int queries = app.resolver.queries;
      monitor.start();
      check(app.resolver.queries == queries, "Idempotent start");
      app.resolver.value = 0;
      app.resolver.notifyState();
      Handler.completeQuery();
      check(nav.attached, "Restore after stop");
      nav.dashboard(true);
      app.resolver.value = 1;
      app.resolver.notifyState();
      Handler.completeQuery();
      app.resolver.value = 0;
      app.resolver.notifyState();
      Handler.completeQuery();
      check(!nav.attached, "Keep hidden on dashboard");
      nav.dashboard(false);
      check(nav.attached, "Leave dashboard restores buttons");
      app.resolver.value = 1;
      app.resolver.notifyState();
      Handler.completeQuery();
      app.resolver.value = 0;
      Handler.advance(5000);
      Handler.completeQuery();
      check(nav.attached, "Poll recovers provider process reset/missed notification");
      check(nav.windows.adds == nav.windows.removes + 1, "Balanced window lifecycle");
    } finally {
      monitor.stop();
    }
    check(app.resolver.observer == null, "Observer released");
    check(Handler.delayed.isEmpty(), "Callbacks removed");
  }

  static void unavailable(String owner) throws Exception {
    App app = new App();
    if (owner != null) app.provider(owner);
    Navigation nav = new Navigation();
    nav.updateVisibility();
    DreamPlaybackMonitor monitor = new DreamPlaybackMonitor(app, nav::setDreaming);
    try {
      monitor.start();
      Handler.completeQuery();
      check(nav.attached, "Missing/wrong provider leaves navigation");
      check(app.resolver.queries == 0, "Do not query unrelated provider");
      app.provider(OWNER);
      app.resolver.value = 1;
      Handler.advance(5000);
      Handler.completeQuery();
      check(!nav.attached, "Discover newly available provider");
      app.packages.provider = null;
      Handler.advance(5000);
      Handler.completeQuery();
      check(nav.attached, "Uninstall restores navigation");
    } finally { monitor.stop(); }
  }

  static void invalidAndDenied() throws Exception {
    App app = new App();
    app.provider(OWNER);
    app.resolver.value = 1;
    Navigation nav = new Navigation();
    nav.updateVisibility();
    DreamPlaybackMonitor monitor = new DreamPlaybackMonitor(app, nav::setDreaming);
    try {
      monitor.start();
      Handler.completeQuery();
      RuntimeException[] errors = {new SecurityException(), new IllegalArgumentException(),
          new IllegalStateException(), new SQLException(), new OperationCanceledException()};
      for (RuntimeException error : errors) {
        app.resolver.failure = error;
        app.resolver.notifyState();
        Handler.completeQuery();
        check(nav.attached, "Restore on " + error.getClass().getSimpleName());
        app.resolver.failure = null;
        app.resolver.notifyState();
        Handler.completeQuery();
        check(!nav.attached, "Recover after query failure");
      }
      for (int invalid = 0; invalid < 6; invalid++) {
        app.resolver.invalidColumn = invalid == 0;
        app.resolver.nullValue = invalid == 1;
        app.resolver.empty = invalid == 2;
        app.resolver.nullCursor = invalid == 3;
        app.resolver.value = invalid == 4 ? 2 : invalid == 5 ? -1 : 1;
        app.resolver.notifyState();
        Handler.completeQuery();
        check(nav.attached, "Invalid state fails open " + invalid);
      }
      check(Log.warnings > 0, "Unavailable state is logged without URLs");
    } finally { monitor.stop(); }
  }

  static void timeoutAndStop() throws Exception {
    App app = new App();
    app.provider(OWNER);
    app.resolver.value = 1;
    Navigation nav = new Navigation();
    nav.updateVisibility();
    DreamPlaybackMonitor monitor = new DreamPlaybackMonitor(app, nav::setDreaming);
    try {
      monitor.start();
      Handler.completeQuery();
      app.resolver.entered = new CountDownLatch(1);
      app.resolver.release = new CountDownLatch(1);
      app.resolver.notifyState();
      check(app.resolver.entered.await(3, TimeUnit.SECONDS), "Worker began query");
      int queries = app.resolver.queries;
      app.resolver.notifyState();
      app.resolver.notifyState();
      check(app.resolver.queries == queries, "Coalesce concurrent notifications");
      Handler.advance(2000);
      check(nav.attached, "Timeout restores buttons while provider blocked");
      app.resolver.release.countDown();
      Handler.completeQuery();
      check(nav.attached, "Ignore late active result after timeout");
      Handler.completeQuery();
      check(!nav.attached, "Fresh query recovers after timeout");
      app.resolver.entered = new CountDownLatch(1);
      app.resolver.release = new CountDownLatch(1);
      app.resolver.notifyState();
      check(app.resolver.entered.await(3, TimeUnit.SECONDS), "Final query began");
      int adds = nav.windows.adds, removes = nav.windows.removes;
      monitor.stop();
      app.resolver.release.countDown();
      Handler.completeQuery();
      check(nav.windows.adds == adds && nav.windows.removes == removes,
          "Ignore result after service destruction");
    } finally {
      app.resolver.release.countDown();
      monitor.stop();
    }
    check(Handler.delayed.isEmpty(), "No delayed work after stop");
  }

  static void deniedObservation() throws Exception {
    App app = new App();
    app.provider(OWNER);
    app.resolver.denyObserve = true;
    app.resolver.value = 1;
    Navigation nav = new Navigation();
    nav.updateVisibility();
    DreamPlaybackMonitor monitor = new DreamPlaybackMonitor(app, nav::setDreaming);
    try {
      monitor.start();
      Handler.completeQuery();
      check(!nav.attached, "Polling works when observation denied");
      app.resolver.value = 0;
      Handler.advance(5000);
      Handler.completeQuery();
      check(nav.attached, "Restore without observer");
    } finally { monitor.stop(); }
  }

  public static void main(String[] args) throws Exception {
    lifecycle();
    unavailable(null);
    unavailable("example.unrelated");
    invalidAndDenied();
    timeoutAndStop();
    deniedObservation();
    System.out.println("PASS " + assertions + " dream navigation assertions");
  }
}
"""

with tempfile.TemporaryDirectory(prefix="homehq-dream-") as directory:
    root = Path(directory)
    for name, content in FAKES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    harness = root / "DreamNavigationHarness.java"
    harness.write_text(HARNESS.replace("__VISIBILITY__", visibility), encoding="utf-8")
    source = ROOT / "src/com/wesbos/homehq/DreamPlaybackMonitor.java"
    subprocess.run(
        ["javac", "--release", "8", "-d", str(root), str(source)]
        + [str(path) for path in root.rglob("*.java")],
        check=True, timeout=30,
    )
    subprocess.run(
        ["java", "-cp", str(root), "com.wesbos.homehq.DreamNavigationHarness"],
        check=True, timeout=30,
    )
