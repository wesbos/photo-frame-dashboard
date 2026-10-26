#!/usr/bin/env python3
"""Run the actual navigation repair method against host settings/permission fakes.

Requires Python 3 and a JDK on PATH. No Android device, SDK or third-party packages.
This checks setting transitions, not Android service binding or boot timing.
"""
from pathlib import Path
import subprocess
import tempfile


SOURCE = Path(__file__).resolve().parent / "src/com/wesbos/homehq/MainActivity.java"
text = SOURCE.read_text(encoding="utf-8")
start = text.index("  private void keepNavigationEnabled() {")
end = text.index("\n  private void openLauncher()", start)
method = text[start:end]

HARNESS = r'''
package com.wesbos.homehq;
import java.util.Objects;

class NavigationService {
  static boolean connected = true;
  static boolean isConnected() { return connected; }
}
class Handler {
  static boolean runNow;
  void postDelayed(Runnable r, long delayMillis) { if (runNow) r.run(); }
}
class PackageManager { static final int PERMISSION_GRANTED = 0; }
class Log {
  static void i(String tag, String msg) {}
  static void w(String tag, String msg, Exception e) {}
}
class ComponentName {
  final String pkg, cls;
  ComponentName(NavigationHarness activity, Class<?> cls) {
    this(activity.getPackageName(), cls.getName());
  }
  ComponentName(String pkg, String cls) { this.pkg = pkg; this.cls = cls; }
  static ComponentName unflattenFromString(String value) {
    int slash = value.indexOf('/');
    if (slash < 0 || slash + 1 == value.length()) return null;
    String pkg = value.substring(0, slash), cls = value.substring(slash + 1);
    return new ComponentName(pkg, cls.startsWith(".") ? pkg + cls : cls);
  }
  public boolean equals(Object value) {
    if (!(value instanceof ComponentName)) return false;
    ComponentName other = (ComponentName) value;
    return pkg.equals(other.pkg) && cls.equals(other.cls);
  }
  public int hashCode() { return Objects.hash(pkg, cls); }
}
class Settings {
  static class Secure {
    static final String ENABLED_ACCESSIBILITY_SERVICES = "services";
    static final String ACCESSIBILITY_ENABLED = "master";
    static String services;
    static int master, reads, serviceWrites, masterWrites;
    static boolean refuseWrites;
    static String getString(Object resolver, String key) {
      reads++; return services;
    }
    static int getInt(Object resolver, String key, int fallback) {
      reads++; return master;
    }
    static boolean putString(Object resolver, String key, String value) {
      if (refuseWrites) throw new SecurityException("permission revoked");
      if (key.equals(ENABLED_ACCESSIBILITY_SERVICES)) {
        services = value; serviceWrites++;
      } else { master = Integer.parseInt(value); masterWrites++; }
      return true;
    }
  }
}
public class NavigationHarness {
  static final String TAG = "test";
  static final long NAV_CHECK_MS = 5000;
  static final long NAV_REBIND_MS = 1000;
  final Handler handler = new Handler();
  final Handler rebindHandler = new Handler();
  static final String OWN = "com.wesbos.homehq/com.wesbos.homehq.NavigationService";
  static final String SHORT = "com.wesbos.homehq/.NavigationService";
  static final String OTHER = "example.other/.NavigationService";
  int permission;
  int checkSelfPermission(String value) { return permission; }
  String getPackageName() { return "com.wesbos.homehq"; }
  Object getContentResolver() { return null; }

__METHOD__

  static void check(String name, String before, int master, int permission,
                    boolean refuseWrites, String after, int expectedMaster,
                    int serviceWrites, int masterWrites) {
    Settings.Secure.services = before;
    Settings.Secure.master = master;
    Settings.Secure.reads = Settings.Secure.serviceWrites = Settings.Secure.masterWrites = 0;
    Settings.Secure.refuseWrites = refuseWrites;
    NavigationHarness activity = new NavigationHarness();
    activity.permission = permission;
    activity.keepNavigationEnabled();
    if (!Objects.equals(after, Settings.Secure.services) ||
        expectedMaster != Settings.Secure.master ||
        serviceWrites != Settings.Secure.serviceWrites ||
        masterWrites != Settings.Secure.masterWrites ||
        (permission != 0 && Settings.Secure.reads != 0)) {
      throw new AssertionError(name);
    }
    System.out.println("PASS " + name);
  }
  public static void main(String[] args) {
    check("selected, master off", OWN, 0, 0, false, OWN, 1, 0, 1);
    check("short component, preserve other services", OTHER + ":" + SHORT, 0, 0,
          false, OTHER + ":" + SHORT, 1, 0, 1);
    check("selected, master already on", OWN, 1, 0, false, OWN, 1, 0, 0);
    check("absent, preserve other service", OTHER, 0, 0, false, OTHER + ":" + OWN, 1, 1, 1);
    check("absent, master already on", OTHER, 1, 0, false, OTHER + ":" + OWN, 1, 1, 0);
    check("null list", null, 0, 0, false, OWN, 1, 1, 1);
    check("empty list", "", 0, 0, false, OWN, 1, 1, 1);
    check("not granted or revoked before check", OWN, 0, -1, false, OWN, 0, 0, 0);
    check("permission lost before master write", OWN, 0, 0, true, OWN, 0, 0, 0);
    check("permission lost before list write", OTHER, 0, 0, true, OTHER, 0, 0, 0);
    // The delayed check runs and the service isn't bound: take it off the list, then put it back.
    // PF1508 (Android 15): after boot the switch alone doesn't bind it, so this must follow too.
    NavigationService.connected = false;
    Handler.runNow = true;
    check("selected, master off, still unbound: rebind", OWN, 0, 0, false, OWN, 1, 2, 1);
    check("selected, master on, unbound: rebind", OWN, 1, 0, false, OWN, 1, 2, 0);
    check("other services kept through a rebind", OTHER + ":" + OWN, 0, 0, false, OTHER + ":" + OWN, 1, 2, 1);
    NavigationService.connected = true;
    check("selected, master off, bound by then: no rebind", OWN, 0, 0, false, OWN, 1, 0, 1);
    Handler.runNow = false;
  }
}
'''

with tempfile.TemporaryDirectory(prefix="homehq-navigation-") as directory:
    root = Path(directory)
    java = root / "NavigationHarness.java"
    java.write_text(HARNESS.replace("__METHOD__", method), encoding="utf-8")
    subprocess.run(["javac", "--release", "8", "-d", str(root), str(java)],
                   check=True, timeout=30)
    subprocess.run(["java", "-cp", str(root), "com.wesbos.homehq.NavigationHarness"],
                   check=True, timeout=30)
