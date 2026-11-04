package local.kodak.adbcheck;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.provider.Settings;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.util.regex.Pattern;

public class MainActivity extends Activity {
  private static final String SYSTEM_UI = "com.android.systemui";
  private static final String FINGERPRINT =
      "rockchip/rk312x/rk312x:6.0.1/MXC89K/user.fyl.20170927.202757:userdebug/test-keys";
  private static final String ENABLE = "pm enable " + SYSTEM_UI;
  private static final Pattern ROOT = Pattern.compile("(?m)^uid=0(?:\\D|$)");
  private Button rootButton, enableButton;
  private TextView status;
  private boolean rootConfirmed, busy;
  private String result = "";

  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    getSharedPreferences("diagnostics", MODE_PRIVATE).edit()
        .remove("root").remove("change").remove("last_report").apply();
    LinearLayout layout = new LinearLayout(this);
    layout.setOrientation(LinearLayout.VERTICAL);
    layout.setPadding(20, 20, 20, 20);
    TextView title = new TextView(this);
    title.setText("Kodak Recovery");
    title.setTextSize(22);
    layout.addView(title);
    rootButton = addButton(layout, "Check root", () -> run(false));
    enableButton = addButton(layout, "Enable System UI", () -> confirmEnable());
    addButton(layout, "Settings", () -> open(Settings.ACTION_SETTINGS));
    addButton(layout, "USB debugging", () ->
        open(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS));
    status = new TextView(this);
    status.setTextSize(18);
    status.setTextIsSelectable(true);
    ScrollView scroll = new ScrollView(this);
    scroll.addView(status);
    layout.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
    setContentView(layout);
    refresh();
  }

  private Button addButton(LinearLayout layout, String label, final Runnable action) {
    Button button = new Button(this);
    button.setText(label);
    button.setOnClickListener(v -> action.run());
    layout.addView(button);
    return button;
  }

  @Override protected void onResume() {
    super.onResume();
    if (status != null) refresh();
  }

  private boolean matchesDevice() {
    return "RCF-1018".equals(Build.MODEL) && FINGERPRINT.equals(Build.FINGERPRINT);
  }

  private int override() throws PackageManager.NameNotFoundException {
    return getPackageManager().getApplicationEnabledSetting(SYSTEM_UI);
  }

  private boolean isDisabledAsExpected() {
    try {
      ApplicationInfo app = getPackageManager().getApplicationInfo(
          SYSTEM_UI, PackageManager.GET_DISABLED_COMPONENTS);
      return !app.enabled && override() == PackageManager.COMPONENT_ENABLED_STATE_DISABLED;
    } catch (Exception e) { return false; }
  }

  private void refresh() {
    String state;
    try {
      ApplicationInfo app = getPackageManager().getApplicationInfo(
          SYSTEM_UI, PackageManager.GET_DISABLED_COMPONENTS);
      state = "System UI: " + (app.enabled ? "enabled" : "disabled");
    } catch (Exception e) { state = "System UI unavailable"; }
    rootButton.setEnabled(!busy && matchesDevice());
    enableButton.setEnabled(!busy && matchesDevice() && rootConfirmed && isDisabledAsExpected());
    status.setText((matchesDevice() ? "" : "Unsupported firmware\n")
        + state + (result.isEmpty() ? "" : "\n" + result));
  }

  private void message(String title, String text) {
    if (!isFinishing() && !isDestroyed()) new AlertDialog.Builder(this)
        .setTitle(title).setMessage(text).setPositiveButton("OK", null).show();
  }

  private void open(String action) {
    try { startActivity(new Intent(action)); }
    catch (Exception e) { message("Cannot open settings", e.toString()); }
  }

  private void confirmEnable() {
    if (busy || !matchesDevice() || !rootConfirmed || !isDisabledAsExpected()) return;
    new AlertDialog.Builder(this).setTitle("Enable existing System UI?")
        .setMessage("Restore the USB authorization prompt.")
        .setNegativeButton("Cancel", null)
        .setPositiveButton("Enable", (dialog, which) -> run(true)).show();
  }

  private void run(final boolean enable) {
    if (busy || !matchesDevice()) return;
    if (enable) {
      if (!rootConfirmed || !isDisabledAsExpected()) return;
      int original = overrideUnchecked();
      if (original != PackageManager.COMPONENT_ENABLED_STATE_DISABLED) return;
      if (!getSharedPreferences("recovery", MODE_PRIVATE).edit()
          .putInt("original_systemui_override", original).commit()) {
        message("Stopped", "Could not save recovery state.");
        return;
      }
    } else rootConfirmed = false;
    busy = true;
    result = enable ? "Enabling..." : "Checking root...";
    refresh();
    new Thread(() -> {
      final CommandResult command = execute(enable ? ENABLE : "id");
      runOnUiThread(() -> {
        busy = false;
        if (!enable) rootConfirmed = command.exit == 0 && ROOT.matcher(command.output).find();
        result = enable
            ? (command.exit == 0 ? "" : command.text)
            : (rootConfirmed ? "Root available" : "Root unavailable"
                + (command.exit == 0 ? "" : "\n" + command.text));
        if (!isDestroyed()) refresh();
      });
    }, "kodak-recovery").start();
  }

  private int overrideUnchecked() {
    try { return override(); } catch (Exception e) { return -1; }
  }

  private static class CommandResult {
    final int exit;
    final String output, text;
    CommandResult(int exit, String output, String text) {
      this.exit = exit; this.output = output; this.text = text;
    }
  }

  private CommandResult execute(String command) {
    if (!"id".equals(command) && !ENABLE.equals(command))
      return new CommandResult(-1, "", "Command rejected.");
    java.lang.Process process = null;
    final StringBuffer output = new StringBuffer();
    try {
      process = new ProcessBuilder("/system/xbin/su", "-c", command).redirectErrorStream(true).start();
      process.getOutputStream().close();
      final InputStream stream = process.getInputStream();
      Thread reader = new Thread(() -> {
        try {
          InputStreamReader input = new InputStreamReader(stream, "UTF-8");
          char[] buffer = new char[512];
          int count;
          while ((count = input.read(buffer)) != -1) synchronized (output) {
            int room = 8192 - output.length();
            if (room > 0) output.append(buffer, 0, Math.min(room, count));
          }
        } catch (Exception ignored) { }
      }, "recovery-output");
      reader.setDaemon(true);
      reader.start();
      long deadline = SystemClock.elapsedRealtime() + 10000;
      while (true) {
        try {
          int exit = process.exitValue();
          reader.join(500);
          return new CommandResult(exit, output.toString(),
              exit == 0 ? "Done" : "Exit " + exit + ": " + output);
        } catch (IllegalThreadStateException running) {
          if (SystemClock.elapsedRealtime() >= deadline)
            return new CommandResult(-1, output.toString(), "Timed out (10 s)");
          Thread.sleep(100);
        }
      }
    } catch (Exception e) { return new CommandResult(-1, "", "Command failed: " + e); }
    finally {
      if (process != null) {
        process.destroy();
        try { process.getInputStream().close(); } catch (Exception ignored) { }
      }
    }
  }
}
