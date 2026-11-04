import android.content.ComponentName;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.ResolveInfo;
import java.lang.reflect.InvocationTargetException;
import java.util.ArrayList;
import java.util.List;

/** MI86 Android 6 Home preference; no device-owner policy or direct settings-file writes. */
public final class PersistentHome {
  private static final String FINGERPRINT =
      "rockchip/rk312x/rk312x:6.0.1/MXC89K/user.zcx.20250822.060141:user/release-keys";
  private static final String PACKAGE = "com.wesbos.homehq";

  public static void main(String[] args) {
    try {
      run(args);
    } catch (Exception error) {
      Throwable cause = error;
      while (cause instanceof InvocationTargetException && cause.getCause() != null) {
        cause = cause.getCause();
      }
      System.err.println("PersistentHome: " + cause);
      System.exit(1);
    }
  }

  private static void run(String[] args) throws Exception {
    if (args.length != 1 || !("inspect".equals(args[0]) || "set".equals(args[0])
        || "clear".equals(args[0]))) {
      throw new IllegalArgumentException("Usage: PersistentHome inspect|set|clear");
    }
    int uid = android.os.Process.myUid();
    if (uid != 1000 && !(uid == 0 && "inspect".equals(args[0]))) {
      throw new SecurityException("Run set/clear as system UID 1000 through root su");
    }
    String fingerprint = (String) Class.forName("android.os.SystemProperties")
        .getMethod("get", String.class).invoke(null, "ro.build.fingerprint");
    if (!FINGERPRINT.equals(fingerprint)) {
      throw new SecurityException("Firmware fingerprint mismatch; no preference changed");
    }

    Class<?> api = Class.forName("android.content.pm.IPackageManager");
    Object pm = Class.forName("android.app.AppGlobals").getMethod("getPackageManager").invoke(null);
    ComponentName home = new ComponentName(PACKAGE, PACKAGE + ".Home");
    List<ResolveInfo> candidates = new ArrayList<ResolveInfo>();
    Object resolved = api.getMethod("getHomeActivities", List.class).invoke(pm, candidates);

    if ("set".equals(args[0])) {
      boolean found = false;
      for (ResolveInfo candidate : candidates) {
        if (candidate.activityInfo != null && PACKAGE.equals(candidate.activityInfo.packageName)
            && (PACKAGE + ".Home").equals(candidate.activityInfo.name)) found = true;
      }
      if (!found) throw new IllegalStateException("Enable the Home HQ .Home alias first");
      IntentFilter filter = new IntentFilter(Intent.ACTION_MAIN);
      filter.addCategory(Intent.CATEGORY_HOME);
      filter.addCategory(Intent.CATEGORY_DEFAULT);
      api.getMethod("addPersistentPreferredActivity", IntentFilter.class, ComponentName.class, int.class)
          .invoke(pm, filter, home, 0);
      candidates.clear();
      resolved = api.getMethod("getHomeActivities", List.class).invoke(pm, candidates);
      if (!home.equals(resolved)) {
        throw new IllegalStateException("Home readback differs; keep the existing access route");
      }
      System.out.println("Home HQ resolves as Home. Verify the saved XML before reboot/removal.");
    } else if ("clear".equals(args[0])) {
      api.getMethod("clearPackagePersistentPreferredActivities", String.class, int.class)
          .invoke(pm, PACKAGE, 0);
      candidates.clear();
      resolved = api.getMethod("getHomeActivities", List.class).invoke(pm, candidates);
      System.out.println("Clear requested. Verify persistent XML entry removal before uninstalling.");
    }
    System.out.println("Resolved Home: " + resolved);
    System.out.println("Home candidates: " + candidates);
  }
}
