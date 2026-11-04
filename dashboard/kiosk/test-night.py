#!/usr/bin/env python3
"""Exercise actual kiosk lifecycle/retry methods and NightActivity with host Android fakes.

Needs Python 3 and JDK 17 on PATH, no SDK/device/network. These checks model callback ordering;
they do not prove real Android gestures, WebView internals, brightness or permission enforcement.
"""
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET


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
    "      public void onReceivedSslError(WebView view, SslErrorHandler h, SslError error)",
    "  protected void onResume()",
    "  protected void onPause()",
    "  private void checkPortal()",
    "  private void onProbe(int result)",
))

# Tiny framework fakes shared by the actual night activity and extracted dashboard methods.
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
    "android/graphics/Color.java": "package android.graphics; public class Color { public static final int BLACK=0; }",
    "android/view/WindowManager.java": """package android.view;
public class WindowManager { public static class LayoutParams {
  public static final int FLAG_KEEP_SCREEN_ON=1, FLAG_FULLSCREEN=2;
  public static final float BRIGHTNESS_OVERRIDE_OFF=0;
  public float screenBrightness=-1, buttonBrightness=-1;
}}""",
    "android/view/View.java": """package android.view;
import android.content.Context;
public class View {
  public static final int VISIBLE=0, GONE=8, SYSTEM_UI_FLAG_FULLSCREEN=1,
    SYSTEM_UI_FLAG_HIDE_NAVIGATION=2, SYSTEM_UI_FLAG_IMMERSIVE_STICKY=4,
    SYSTEM_UI_FLAG_LAYOUT_STABLE=8, SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN=16,
    SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION=32;
  public interface OnClickListener { void onClick(View v); }
  public OnClickListener click; public int visibility=GONE, color, systemUi;
  public String description; public boolean focusable;
  public View(Context c) {} public void setBackgroundColor(int v) { color=v; }
  public void setContentDescription(String v) { description=v; }
  public void setFocusable(boolean v) { focusable=v; }
  public void setOnClickListener(OnClickListener v) { click=v; }
  public boolean performClick() { if(click==null) return false; click.onClick(this); return true; }
  public void setSystemUiVisibility(int v) { systemUi=v; }
  public int getVisibility() { return visibility; }
} """,
    "android/view/Window.java": """package android.view;
public class Window {
  public int flags; public final View decor=new View(null);
  public WindowManager.LayoutParams attrs=new WindowManager.LayoutParams();
  public void addFlags(int f) { flags |= f; }
  public WindowManager.LayoutParams getAttributes() { return attrs; }
  public void setAttributes(WindowManager.LayoutParams v) { attrs=v; }
  public View getDecorView() { return decor; }
}""",
    "android/app/Activity.java": """package android.app;
import android.content.*; import android.os.Bundle; import android.view.*;
public class Activity extends Context {
  public final Window window=new Window(); public View content; public Intent launched;
  public int launches, finishes; public boolean destroyed;
  protected void onCreate(Bundle s) {} protected void onResume() {}
  protected void onPause() {} protected void onStop() {}
  public void onBackPressed() {} public void onWindowFocusChanged(boolean f) {}
  public Window getWindow() { return window; }
  public String getString(int id) { return "Night view. Tap to return to the dashboard."; }
  public void setContentView(View v) { content=v; }
  public void startActivity(Intent i) { launches++; launched=i; }
  public void finishAndRemoveTask() { finishes++; }
  public boolean isDestroyed() { return destroyed; }
}""",
    str(PACKAGE / "R.java"): "package com.wesbos.homehq; class R { static class string { static final int night_description=1; }}",
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
  long portalSince; String retryUrl, mainUrl; boolean wifi=true; int loads, opened, left;
  void cancelExit() {} void load(String url) { loads++; }
  boolean wifiConnected() { return wifi; } void showOffline() { checkPortal(); }
  static int probePortal() { return PROBE_PORTAL; }
  String savedUrl() { return "http://example.invalid/"; }
  void leavePortal() { left++; } void openPortal() { opened++; } void setOfflineText() {}
__MEMBERS__
  public static void test() {
    MainActivity a=new MainActivity();
    a.onResume();
    NightHarness.check(!a.web.paused && !a.web.timersPaused && NavigationService.visible,
        "visible dashboard resumed");
    a.retryUrl="http://example.invalid/"; a.offline.visibility=View.VISIBLE;
    a.handler.post(a.retry); a.handler.post(a.stall); a.handler.post(a.portalCheck);
    a.onPause();
    NightHarness.check(a.handler.tasks.isEmpty() && a.web.paused && a.web.timersPaused,
        "covering dashboard pauses page and native recovery callbacks");
    a.retry.run(); a.stall.run(); a.networkChange.onReceive(a, new Intent()); a.checkPortal();
    a.onProbe(PROBE_PORTAL);
    NightHarness.check(a.loads==0 && a.opened==0 && a.handler.tasks.isEmpty() && !a.probing,
        "late retry, network broadcast and probe cannot run behind night view");
    a.onReceivedError(a.web, -2, "offline", "http://example.invalid/");
    NightHarness.check(a.retryPending && a.handler.tasks.isEmpty(),
        "late page failure retains retry intent without starting background work");
    SslErrorHandler ssl=new SslErrorHandler();
    a.onReceivedSslError(a.web, ssl, new SslError());
    NightHarness.check(ssl.cancelled && a.retryPending && a.handler.tasks.isEmpty(),
        "late TLS failure stays blocked and waits for visible retry");
    a.onResume(); a.handler.runNext();
    NightHarness.check(a.loads==1 && !a.web.timersPaused && a.handler.tasks.contains(a.stall),
        "offline recovery resumes on return");
    a.onPause(); a.offline.visibility=View.GONE; a.onResume();
    NightHarness.check(a.loads==1 && a.handler.tasks.isEmpty(), "healthy page returns without reload");
    a.offline.visibility=View.VISIBLE; a.checkPortal();
    Runnable background=Thread.pending; a.onPause(); background.run(); a.handler.runNext();
    NightHarness.check(!a.probing && a.opened==0 && a.handler.tasks.isEmpty(),
        "probe completing while hidden cannot open sign-in or schedule another probe");
    a.portalMode=true; a.onResume(); a.handler.runNext();
    NightHarness.check(a.probing, "Wi-Fi sign-in recovery restarts on return");
    Thread.pending.run(); a.handler.runNext();
    NightHarness.check(a.handler.tasks.contains(a.portalCheck), "visible sign-in keeps checking");
    a.onPause(); a.portalMode=false; a.offline.visibility=View.GONE; a.onResume();
    a.checkPortal(); a.destroyed=true; Thread.pending.run(); a.handler.runNext();
    NightHarness.check(a.opened==0, "destroyed dashboard ignores late probe result");
  }
}
""".replace("__MEMBERS__", MEMBERS),
    str(PACKAGE / "NightHarness.java"): """package com.wesbos.homehq;
import android.view.WindowManager;
public class NightHarness {
  static void check(boolean ok, String name) {
    if(!ok) throw new AssertionError(name); System.out.println("PASS " + name);
  }
  public static void main(String[] args) {
    MainActivity.test();
    NightActivity n=new NightActivity(); n.onCreate(null); n.onResume();
    check(n.getWindow().attrs.screenBrightness==0 && n.getWindow().attrs.buttonBrightness==0
        && (n.getWindow().flags & WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)!=0,
        "night view uses window brightness and keeps touch/display awake");
    check(NavigationService.visible && n.content.focusable && n.content.click!=null,
        "night view hides navigation and offers standard accessible click");
    n.content.performClick(); n.onBackPressed(); n.content.performClick();
    check(n.launches==1 && n.launched.target==MainActivity.class && n.launched.flags==3,
        "click/Back returns once to existing dashboard without URL replacement");
    n.onPause(); n.onStop();
    check(!NavigationService.visible && n.finishes>=1, "leaving night view removes its task");
    NightActivity back=new NightActivity(); back.onCreate(null); back.onBackPressed();
    check(back.launches==1 && back.finishes==1, "Back returns without requiring a touch");
    NightActivity morning=new NightActivity(); morning.onCreate(null); morning.onStop();
    check(morning.launches==0 && morning.finishes==1,
        "external morning return removes night task without launching dashboard again");
  }
}
""",
}


# These are packaging invariants: host Activity fakes cannot enforce Android permissions.
android = "{http://schemas.android.com/apk/res/android}"
manifest = ET.parse(KIOSK / "AndroidManifest.xml").getroot()
night = manifest.find("application/activity[@" + android + "name='.NightActivity']")
assert night is not None
assert night.get(android + "permission") == "android.permission.DUMP"
assert night.get(android + "exported") == "true"
assert night.get(android + "excludeFromRecents") == "true"
assert night.find("intent-filter") is None
print("PASS night activity requires DUMP and has no implicit intent filter", flush=True)

with tempfile.TemporaryDirectory(prefix="homehq-night-") as directory:
    root = Path(directory)
    for name, source in SOURCES.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    target = root / PACKAGE / "NightActivity.java"
    target.write_text((KIOSK / "src" / PACKAGE / "NightActivity.java").read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["javac", "--release", "8", "-d", str(root)] +
                   [str(file) for file in root.rglob("*.java")], check=True, timeout=30)
    subprocess.run(["java", "-cp", str(root), "com.wesbos.homehq.NightHarness"],
                   check=True, timeout=30)
