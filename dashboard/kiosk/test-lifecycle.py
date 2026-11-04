#!/usr/bin/env python3
"""Exercise actual kiosk lifecycle/retry methods with host Android fakes.

Needs Python 3 and JDK 17 on PATH, no SDK/device/network. These checks model callback ordering;
they do not prove real Android gestures, WebView internals, brightness or permission enforcement.
"""
from pathlib import Path
import subprocess
import tempfile


KIOSK = Path(__file__).resolve().parent
PACKAGE = Path("com/wesbos/homehq")
SOURCE = (KIOSK / "src" / PACKAGE / "MainActivity.java").read_text(encoding="utf-8")


def member(marker):
    """Copy a complete method or anonymous callback from the production class."""
    start = SOURCE.index(marker)
    opening = SOURCE.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (SOURCE[end] == "{") - (SOURCE[end] == "}")
        end += 1
    if SOURCE[end:end + 1] == ";":
        end += 1
    return SOURCE[start:end]


MEMBERS = "\n".join(member(marker) for marker in (
    "  private final Runnable retry =",
    "  private final Runnable stall =",
    "  private final BroadcastReceiver networkChange =",
    "      public void onReceivedError(WebView view, int code, String desc, String failingUrl)",
    "      public void onReceivedHttpError(WebView view, WebResourceRequest req, WebResourceResponse res)",
    "      public void onReceivedSslError(WebView view, SslErrorHandler h, SslError error)",
    "  protected void onResume()",
    "  protected void onPause()",
    "  private void checkPortal()",
    "  private void onProbe(int result)",
))

# Tiny framework fakes for extracted dashboard methods.
SOURCES = {
    "android/content/Context.java": "package android.content; public class Context {}",
    "android/content/Intent.java": """package android.content;
public class Intent {
  public static final int FLAG_ACTIVITY_NEW_TASK=1, FLAG_ACTIVITY_CLEAR_TOP=2;
  public Class<?> target; public int flags;
  public Intent() {} public Intent(Context c, Class<?> t) { target=t; }
  public Intent addFlags(int f) { flags |= f; return this; }
} """,
    "android/content/BroadcastReceiver.java": """package android.content;
public abstract class BroadcastReceiver { public abstract void onReceive(Context c, Intent i); }""",
    "android/os/Bundle.java": "package android.os; public class Bundle {}",
    "android/view/View.java": """package android.view;
import android.content.Context;
public class View {
  public static final int VISIBLE=0, GONE=8;
  public int visibility=GONE;
  public View(Context c) {} public int getVisibility() { return visibility; }
}""",
    "android/app/Activity.java": """package android.app;
import android.content.Context;
public class Activity extends Context {
  public boolean destroyed;
  protected void onResume() {} protected void onPause() {}
  public boolean isDestroyed() { return destroyed; }
}""",
    str(PACKAGE / "Fakes.java"): """package com.wesbos.homehq;
import java.util.*;
class NavigationService { static boolean visible; static void setDashboardVisible(boolean v) { visible=v; }}
class WebView {
  boolean timersPaused, paused;
  void resumeTimers() { timersPaused=false; } void onResume() { paused=false; }
  void onPause() { paused=true; } void pauseTimers() { timersPaused=true; }
}
class Handler {
  final List<Runnable> tasks=new ArrayList<>();
  void post(Runnable r) { tasks.add(r); } void postDelayed(Runnable r, long d) { tasks.add(r); }
  void removeCallbacks(Runnable r) { tasks.removeIf(t -> t==r); }
  void runNext() { tasks.remove(0).run(); }
}
class Thread {
  static Runnable pending;
  final Runnable task; Thread(Runnable r, String name) { task=r; }
  void start() { pending=task; }
}
class SystemClock { static long elapsedRealtime() { return 0; }}
class Log { static void i(String t, String m) {} static void w(String t, String m) {} }
class Label { void setText(String s) {} }
class WebResourceRequest {
  final boolean main; WebResourceRequest(boolean main) { this.main=main; }
  boolean isForMainFrame() { return main; }
  String getUrl() { return "https://example.invalid/dashboard"; }
}
class WebResourceResponse {
  final int status; WebResourceResponse(int status) { this.status=status; }
  int getStatusCode() { return status; }
}
class SslErrorHandler { boolean cancelled; void cancel() { cancelled=true; } }
class SslError {
  static final int SSL_NOTYETVALID=1, SSL_EXPIRED=2, SSL_DATE_INVALID=3;
  int getPrimaryError() { return SSL_DATE_INVALID; }
  String getUrl() { return "http://example.invalid/"; }
  boolean hasError(int code) { return code==SSL_DATE_INVALID; }
}
""",
    str(PACKAGE / "MainActivity.java"): """package com.wesbos.homehq;
import android.app.Activity; import android.content.*; import android.view.View;
public class MainActivity extends Activity {
  static final String TAG="test", PORTAL_PROBE="http://probe.invalid/";
  static final long RETRY_MS=5000, STALL_MS=15000, PORTAL_CHECK_MS=5000, PORTAL_GIVE_UP_MS=600000;
  static final int PROBE_ONLINE=0, PROBE_PORTAL=1;
  final Handler handler=new Handler(); final WebView web=new WebView();
  final View offline=new View(this);
  final Label portalText=new Label(), offlineTitle=new Label(), offlineText=new Label();
  final Runnable portalCheck=this::checkPortal;
  boolean resumed, retryPending, probing, portalMode, portalFound, portalDismissed, portalFailed, pageFailed;
  long portalSince; String retryUrl, mainUrl; boolean wifi=true; int loads, opened, left, clockNudges;
  void nudgeNetworkTime() { clockNudges++; }
  void cancelExit() {} void load(String url) { loads++; }
  boolean wifiConnected() { return wifi; } void showOffline() { checkPortal(); }
  static int probePortal() { return PROBE_PORTAL; }
  String savedUrl() { return "http://example.invalid/"; }
  void leavePortal() { left++; } void openPortal() { opened++; } void setOfflineText() {}
__MEMBERS__
  public static void test() {
    MainActivity http=new MainActivity();
    http.onReceivedHttpError(http.web, new WebResourceRequest(false), new WebResourceResponse(503));
    http.onReceivedHttpError(http.web, new WebResourceRequest(true), new WebResourceResponse(404));
    http.onReceivedHttpError(http.web, new WebResourceRequest(true), new WebResourceResponse(600));
    LifecycleHarness.check(!http.retryPending && !http.pageFailed && http.handler.tasks.isEmpty(),
        "subresource and non-5xx responses do not retry the dashboard");
    http.onReceivedHttpError(http.web, new WebResourceRequest(true), new WebResourceResponse(503));
    LifecycleHarness.check(http.retryPending && http.pageFailed && http.handler.tasks.isEmpty()
        && "https://example.invalid/dashboard".equals(http.retryUrl),
        "paused HTTP 5xx retains the failing main URL without starting retry");
    http.offline.visibility=View.VISIBLE; http.onResume(); http.handler.runNext();
    LifecycleHarness.check(http.loads==1 && !http.retryPending,
        "pending HTTP 5xx recovery runs on resume");
    http.onReceivedHttpError(http.web, new WebResourceRequest(true), new WebResourceResponse(500));
    LifecycleHarness.check(http.retryPending && http.handler.tasks.contains(http.retry),
        "visible HTTP 5xx schedules recovery");
    MainActivity a=new MainActivity();
    a.onResume();
    LifecycleHarness.check(!a.web.paused && !a.web.timersPaused && NavigationService.visible,
        "visible dashboard resumed");
    a.retryUrl="http://example.invalid/"; a.offline.visibility=View.VISIBLE;
    a.handler.post(a.retry); a.handler.post(a.stall); a.handler.post(a.portalCheck);
    a.onPause();
    LifecycleHarness.check(a.handler.tasks.isEmpty() && a.web.paused && a.web.timersPaused,
        "covering dashboard pauses page and native recovery callbacks");
    a.retry.run(); a.stall.run(); a.networkChange.onReceive(a, new Intent()); a.checkPortal();
    a.onProbe(PROBE_PORTAL);
    LifecycleHarness.check(a.loads==0 && a.opened==0 && a.handler.tasks.isEmpty() && !a.probing,
        "late retry, network broadcast and probe cannot run while the kiosk is paused");
    a.onReceivedError(a.web, -2, "offline", "http://example.invalid/");
    LifecycleHarness.check(a.retryPending && a.handler.tasks.isEmpty(),
        "late page failure retains retry intent without starting background work");
    SslErrorHandler ssl=new SslErrorHandler();
    a.onReceivedSslError(a.web, ssl, new SslError());
    LifecycleHarness.check(ssl.cancelled && a.retryPending && a.handler.tasks.isEmpty() && a.clockNudges==0,
        "late TLS failure stays blocked and waits for visible retry");
    a.onResume(); a.handler.runNext();
    LifecycleHarness.check(a.loads==1 && !a.web.timersPaused && a.handler.tasks.contains(a.stall),
        "offline recovery resumes on return");
    a.onPause(); a.offline.visibility=View.GONE; a.onResume();
    LifecycleHarness.check(a.loads==1 && a.handler.tasks.isEmpty(), "healthy page returns without reload");
    a.offline.visibility=View.VISIBLE; a.checkPortal();
    Runnable background=Thread.pending; a.onPause(); background.run(); a.handler.runNext();
    LifecycleHarness.check(!a.probing && a.opened==0 && a.handler.tasks.isEmpty(),
        "probe completing while hidden cannot open sign-in or schedule another probe");
    a.portalMode=true; a.onResume(); a.handler.runNext();
    LifecycleHarness.check(a.probing, "Wi-Fi sign-in recovery restarts on return");
    Thread.pending.run(); a.handler.runNext();
    LifecycleHarness.check(a.handler.tasks.contains(a.portalCheck), "visible sign-in keeps checking");
    a.onPause(); a.portalMode=false; a.offline.visibility=View.GONE; a.onResume();
    a.checkPortal(); a.destroyed=true; Thread.pending.run(); a.handler.runNext();
    LifecycleHarness.check(a.opened==0, "destroyed dashboard ignores late probe result");
  }
}
""".replace("__MEMBERS__", MEMBERS),
    str(PACKAGE / "LifecycleHarness.java"): """package com.wesbos.homehq;
public class LifecycleHarness {
  static void check(boolean ok, String name) {
    if(!ok) throw new AssertionError(name); System.out.println("PASS " + name);
  }
  public static void main(String[] args) {
    MainActivity.test();

  }
}
""",
}


with tempfile.TemporaryDirectory(prefix="homehq-lifecycle-") as directory:
    root = Path(directory)
    for name, source in SOURCES.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    subprocess.run(["javac", "--release", "8", "-d", str(root)] +
                   [str(file) for file in root.rglob("*.java")], check=True, timeout=30)
    subprocess.run(["java", "-cp", str(root), "com.wesbos.homehq.LifecycleHarness"],
                   check=True, timeout=30)
