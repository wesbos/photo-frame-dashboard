#!/usr/bin/env python3
"""Compile the real screen policy against small Android host fakes."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
FAKES = {
    "android/content/SharedPreferences.java": """
package android.content;
public interface SharedPreferences {
  boolean getBoolean(String key, boolean fallback);
  Editor edit();
  interface Editor {
    Editor putBoolean(String key, boolean value);
    void apply();
  }
}
""",
    "android/content/Intent.java": """
package android.content;
import java.util.*;
public class Intent {
  Map<String, Boolean> extras = new HashMap<>();
  public boolean hasExtra(String key) { return extras.containsKey(key); }
  public boolean getBooleanExtra(String key, boolean fallback) {
    return extras.getOrDefault(key, fallback);
  }
  public Intent putExtra(String key, boolean value) { extras.put(key, value); return this; }
}
""",
    "android/content/DialogInterface.java": """
package android.content;
public interface DialogInterface {
  void dismiss();
  interface OnClickListener { void onClick(DialogInterface dialog, int which); }
}
""",
    "android/view/WindowManager.java": """
package android.view;
public class WindowManager {
  public static class LayoutParams {
    public static final int FLAG_KEEP_SCREEN_ON = 128, FLAG_FULLSCREEN = 1024;
  }
}
""",
    "android/view/Window.java": """
package android.view;
public class Window {
  public int flags = 1024;
  public void addFlags(int value) { flags |= value; }
  public void clearFlags(int value) { flags &= ~value; }
}
""",
    "android/app/Activity.java": """
package android.app;
import android.content.SharedPreferences;
import android.view.Window;
public abstract class Activity {
  public static final int MODE_PRIVATE = 0;
  public abstract SharedPreferences getSharedPreferences(String name, int mode);
  public abstract Window getWindow();
}
""",
    "android/app/AlertDialog.java": """
package android.app;
import android.content.DialogInterface;
public class AlertDialog implements DialogInterface {
  public boolean dismissed;
  public void dismiss() { dismissed = true; }
  public static class Builder {
    public static Builder latest;
    public int selected;
    public String title;
    public String[] items;
    public DialogInterface.OnClickListener listener;
    public Builder(Activity activity) { latest = this; }
    public Builder setTitle(String value) { title = value; return this; }
    public Builder setSingleChoiceItems(String[] values, int checked,
        DialogInterface.OnClickListener callback) {
      items = values; selected = checked; listener = callback; return this;
    }
    public Builder setNegativeButton(String title, DialogInterface.OnClickListener callback) {
      return this;
    }
    public AlertDialog show() { return new AlertDialog(); }
  }
}
""",
}

HARNESS = r"""
package com.wesbos.homehq;
import android.app.*;
import android.content.*;
import android.view.*;
import java.util.*;
public class ScreenAwakeHarness {
  static int assertions;
  static class Preferences implements SharedPreferences, SharedPreferences.Editor {
    Map<String, Boolean> values = new HashMap<>();
    public boolean getBoolean(String key, boolean fallback) {
      return values.getOrDefault(key, fallback);
    }
    public SharedPreferences.Editor edit() { return this; }
    public SharedPreferences.Editor putBoolean(String key, boolean value) {
      values.put(key, value); return this;
    }
    public void apply() {}
  }
  static class App extends Activity {
    final Preferences prefs;
    final Window window = new Window();
    App(Preferences prefs) { this.prefs = prefs; }
    public SharedPreferences getSharedPreferences(String name, int mode) {
      check(name.equals("kiosk") && mode == 0, "Private existing preferences");
      return prefs;
    }
    public Window getWindow() { return window; }
  }
  static void check(boolean value, String message) {
    assertions++;
    if (!value) throw new AssertionError(message);
  }
  static boolean awake(App app) { return (app.window.flags & 128) != 0; }
  public static void main(String[] args) {
    Preferences preferences = new Preferences();
    App first = new App(preferences);
    ScreenAwakeSettings.apply(first);
    check(awake(first), "Existing keep-awake behavior is default");
    Intent staleLaunch = new Intent().putExtra("keep_awake", true);
    ScreenAwakeSettings.onNewIntent(first, staleLaunch);
    ScreenAwakeSettings.onNewIntent(first, new Intent().putExtra("keep_awake", false));
    check(!awake(first), "Explicit false clears window flag");
    check(first.window.flags == 1024, "Fullscreen preserved");
    App recreated = new App(preferences);
    ScreenAwakeSettings.apply(recreated);
    check(!awake(recreated), "Disabled persists on cold launch");
    ScreenAwakeSettings.apply(recreated);
    check(!awake(recreated) && !preferences.getBoolean("keep_awake", true),
        "Cold recreation cannot replay stale true launch extra");
    ScreenAwakeSettings.onNewIntent(recreated, new Intent().putExtra("unrelated", true));
    check(!awake(recreated), "Unrelated intent does not reset preference");
    ScreenAwakeSettings.onNewIntent(recreated, new Intent().putExtra("keep_awake", true));
    check(awake(recreated), "Explicit true restores keep-awake");
    ScreenAwakeSettings.show(recreated);
    AlertDialog.Builder builder = AlertDialog.Builder.latest;
    check(builder.selected == 0 && builder.items.length == 2, "Dialog shows saved enabled state");
    AlertDialog dialog = new AlertDialog();
    builder.listener.onClick(dialog, 1);
    check(!awake(recreated) && dialog.dismissed, "UI disables immediately and dismisses");
    ScreenAwakeSettings.show(recreated);
    check(AlertDialog.Builder.latest.selected == 1, "Dialog shows saved disabled state");
    AlertDialog.Builder.latest.listener.onClick(new AlertDialog(), 0);
    check(awake(recreated), "UI enables immediately");
    check(recreated.window.flags == 1152, "Only keep-awake flag changed");
    System.out.println("PASS " + assertions + " screen policy assertions");
  }
}
"""

activity = (ROOT / "src/com/wesbos/homehq/MainActivity.java").read_text()
assert "ScreenAwakeSettings.apply(this);" in activity
assert "ScreenAwakeSettings.onNewIntent(this, intent);" in activity
create = activity[activity.index("  protected void onCreate("):activity.index("  protected void onResume(")]
assert "ScreenAwakeSettings.onNewIntent" not in create
assert "ScreenAwakeSettings.apply(this, getIntent())" not in create
assert "ScreenAwakeSettings.show(MainActivity.this);" in activity
assert "FLAG_KEEP_SCREEN_ON" not in activity

with tempfile.TemporaryDirectory(prefix="homehq-screen-") as directory:
    root = Path(directory)
    for name, content in FAKES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (root / "ScreenAwakeHarness.java").write_text(HARNESS, encoding="utf-8")
    subprocess.run(
        ["javac", "--release", "8", "-d", str(root),
         str(ROOT / "src/com/wesbos/homehq/ScreenAwakeSettings.java")]
        + [str(path) for path in root.rglob("*.java")],
        check=True, timeout=30,
    )
    subprocess.run(
        ["java", "-cp", str(root), "com.wesbos.homehq.ScreenAwakeHarness"],
        check=True, timeout=30,
    )
