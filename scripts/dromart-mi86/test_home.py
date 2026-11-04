"""Host JVM tests of the real PersistentHome source against tiny Android API doubles.

No SDK or frame needed for these tests. A separate real SDK/d8 build verifies dex compilation.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from build_home import build

HERE = Path(__file__).resolve().parent
FINGERPRINT = "rockchip/rk312x/rk312x:6.0.1/MXC89K/user.zcx.20250822.060141:user/release-keys"
JAVA_HOME = os.environ.get("JAVA_HOME")
JAVA = str(Path(JAVA_HOME) / "bin/java") if JAVA_HOME else shutil.which("java")
JAVAC = str(Path(JAVA_HOME) / "bin/javac") if JAVA_HOME else shutil.which("javac")

STUBS = {
    "android/os/Process.java": """
package android.os;
public class Process { public static int myUid() { return Integer.getInteger("fixture.uid"); } }
""",
    "android/os/SystemProperties.java": """
package android.os;
public class SystemProperties {
  public static String get(String key) {
    if (!key.equals("ro.build.fingerprint")) throw new AssertionError(key);
    if (Boolean.getBoolean("fixture.propertyError")) throw new IllegalStateException("property read failed");
    return System.getProperty("fixture.fingerprint", "");
  }
}
""",
    "android/content/ComponentName.java": """
package android.content;
public class ComponentName {
  public final String pkg, cls;
  public ComponentName(String p, String c) { pkg=p; cls=c; }
  public boolean equals(Object o) {
    return o instanceof ComponentName && pkg.equals(((ComponentName)o).pkg) && cls.equals(((ComponentName)o).cls);
  }
  public int hashCode() { return pkg.hashCode() ^ cls.hashCode(); }
  public String toString() { return pkg + "/" + cls; }
}
""",
    "android/content/Intent.java": """
package android.content;
public class Intent {
  public static final String ACTION_MAIN="android.intent.action.MAIN";
  public static final String CATEGORY_HOME="android.intent.category.HOME";
  public static final String CATEGORY_DEFAULT="android.intent.category.DEFAULT";
}
""",
    "android/content/IntentFilter.java": """
package android.content;
import java.util.HashSet;
import java.util.Set;
public class IntentFilter {
  public final String action;
  public final Set<String> categories=new HashSet<String>();
  public IntentFilter(String a) { action=a; }
  public void addCategory(String c) { categories.add(c); }
}
""",
    "android/content/pm/ActivityInfo.java": """
package android.content.pm;
public class ActivityInfo { public String packageName, name; }
""",
    "android/content/pm/ResolveInfo.java": """
package android.content.pm;
public class ResolveInfo { public ActivityInfo activityInfo; }
""",
    "android/content/pm/IPackageManager.java": """
package android.content.pm;
import android.content.*;
import java.util.List;
public interface IPackageManager {
  ComponentName getHomeActivities(List<ResolveInfo> homes);
  void addPersistentPreferredActivity(IntentFilter f, ComponentName c, int user);
  void clearPackagePersistentPreferredActivities(String pkg, int user);
}
""",
    "android/app/AppGlobals.java": """
package android.app;
import android.content.*;
import android.content.pm.*;
import java.util.*;
public class AppGlobals {
  private static final FakePm PM=new FakePm();
  public static IPackageManager getPackageManager() { return PM; }
  public static class FakePm implements IPackageManager {
    private ComponentName selected=new ComponentName("other.launcher", "other.launcher.Home");
    public ComponentName getHomeActivities(List<ResolveInfo> homes) {
      if (!Boolean.getBoolean("fixture.noHome")) {
        ResolveInfo r=new ResolveInfo(); r.activityInfo=new ActivityInfo();
        r.activityInfo.packageName="com.wesbos.homehq"; r.activityInfo.name="com.wesbos.homehq.Home";
        homes.add(r);
      }
      return Boolean.getBoolean("fixture.badReadback") ? null : selected;
    }
    public void addPersistentPreferredActivity(IntentFilter f, ComponentName c, int user) {
      if (user!=0 || !f.action.equals(Intent.ACTION_MAIN)
          || !f.categories.equals(new HashSet<String>(Arrays.asList(Intent.CATEGORY_HOME, Intent.CATEGORY_DEFAULT)))
          || !c.toString().equals("com.wesbos.homehq/com.wesbos.homehq.Home")) throw new AssertionError("wrong Home filter/target");
      System.out.println("MUTATE set user=0 " + c);
      selected=c;
    }
    public void clearPackagePersistentPreferredActivities(String pkg, int user) {
      if (user!=0 || !pkg.equals("com.wesbos.homehq")) throw new AssertionError("wrong clear target");
      System.out.println("MUTATE clear user=0 " + pkg);
      // The ordinary Home preference may still resolve to Home HQ after persistent clear.
      selected=new ComponentName(pkg, pkg + ".Home");
    }
  }
}
""",
}


@unittest.skipUnless(JAVA and JAVAC, "JDK is required for host JVM tests")
class PersistentHomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="mi86-home-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        cls.classes = root / "classes"
        cls.classes.mkdir()
        sources = []
        for name, text in STUBS.items():
            source = root / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(text)
            sources.append(str(source))
        subprocess.run([
            JAVAC, "--release", "8", "-d", str(cls.classes),
            *sources, str(HERE / "PersistentHome.java"),
        ], capture_output=True, text=True, check=True)

    def invoke(self, operation: str, uid: int = 1000, **properties: str) -> subprocess.CompletedProcess:
        options = {"uid": str(uid), "fingerprint": FINGERPRINT, **properties}
        return subprocess.run([
            JAVA, *["-Dfixture." + key + "=" + value for key, value in options.items()],
            "-cp", str(self.classes), "PersistentHome", operation,
        ], capture_output=True, text=True, timeout=10)

    def test_set_requires_system_uid_and_exact_home_filter(self) -> None:
        result = self.invoke("set")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MUTATE set user=0 com.wesbos.homehq/com.wesbos.homehq.Home", result.stdout)
        self.assertIn("Resolved Home: com.wesbos.homehq/com.wesbos.homehq.Home", result.stdout)

    def test_root_can_inspect_without_mutation(self) -> None:
        result = self.invoke("inspect", uid=0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("MUTATE", result.stdout)

    def test_root_and_shell_cannot_mutate(self) -> None:
        for uid in [0, 2000]:
            for operation in ["set", "clear"]:
                with self.subTest(uid=uid, operation=operation):
                    result = self.invoke(operation, uid=uid)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("system UID 1000", result.stderr)
                    self.assertNotIn("MUTATE", result.stdout)

    def test_wrong_missing_or_unreadable_fingerprint_cannot_mutate(self) -> None:
        for properties in [{"fingerprint": ""}, {"fingerprint": FINGERPRINT + "-other"}, {"propertyError": "true"}]:
            for operation in ["set", "clear"]:
                with self.subTest(properties=properties, operation=operation):
                    result = self.invoke(operation, **properties)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("MUTATE", result.stdout)

    def test_missing_home_alias_refuses_set(self) -> None:
        result = self.invoke("set", noHome="true")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Enable the Home HQ .Home alias", result.stderr)
        self.assertNotIn("MUTATE", result.stdout)

    def test_failed_set_readback_is_an_error(self) -> None:
        result = self.invoke("set", badReadback="true")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MUTATE set", result.stdout)
        self.assertIn("Home readback differs", result.stderr)

    def test_clear_allows_missing_alias_and_does_not_assume_other_home(self) -> None:
        result = self.invoke("clear", noHome="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MUTATE clear user=0 com.wesbos.homehq", result.stdout)
        self.assertIn("Verify persistent XML entry removal", result.stdout)

    def test_invalid_operation_does_not_mutate(self) -> None:
        result = self.invoke("erase")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inspect|set|clear", result.stderr)
        self.assertNotIn("MUTATE", result.stdout)


class BuildHomeTests(unittest.TestCase):
    def test_existing_output_is_rejected_before_dependency_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "existing"
            out.mkdir()
            marker = out / "keep"
            marker.write_text("original")
            with self.assertRaisesRegex(SystemExit, "already exists"):
                build(out, Path(directory) / "missing-sdk", "android-35", "36.1.0")
            self.assertEqual(marker.read_text(), "original")


if __name__ == "__main__":
    unittest.main(verbosity=2)
