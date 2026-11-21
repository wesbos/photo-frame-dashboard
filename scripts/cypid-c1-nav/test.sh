#!/usr/bin/env bash
# Host-only checks against a Settings provider that denies hidden-key reads.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
JAVA="${JAVA_HOME:?Set JAVA_HOME to a JDK 17 installation}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/android/content/pm" "$work/android/os" "$work/android/provider" \
    "$work/android/util" "$work/com/photoframe/c1nav" "$work/classes"
cat > "$work/android/Manifest.java" <<'JAVA'
package android;
public final class Manifest { public static final class permission { public static final String WRITE_SECURE_SETTINGS = "android.permission.WRITE_SECURE_SETTINGS"; } }
JAVA
cat > "$work/android/content/pm/PackageManager.java" <<'JAVA'
package android.content.pm;
public final class PackageManager { public static final int PERMISSION_GRANTED = 0, PERMISSION_DENIED = -1; }
JAVA
cat > "$work/android/os/Build.java" <<'JAVA'
package android.os;
public final class Build { public static String MODEL, DISPLAY, FINGERPRINT; }
JAVA
cat > "$work/android/content/Context.java" <<'JAVA'
package android.content;
public abstract class Context { public static final int MODE_PRIVATE = 0; public abstract int checkSelfPermission(String permission); public abstract ContentResolver getContentResolver(); public abstract SharedPreferences getSharedPreferences(String name, int mode); }
JAVA
cat > "$work/android/content/ContentResolver.java" <<'JAVA'
package android.content;
public class ContentResolver {}
JAVA
cat > "$work/android/content/SharedPreferences.java" <<'JAVA'
package android.content;
public interface SharedPreferences { boolean getBoolean(String key, boolean defValue); }
JAVA
cat > "$work/android/content/BroadcastReceiver.java" <<'JAVA'
package android.content;
public abstract class BroadcastReceiver { public abstract void onReceive(Context context, Intent intent); }
JAVA
cat > "$work/android/content/Intent.java" <<'JAVA'
package android.content;
public class Intent { public static final String ACTION_BOOT_COMPLETED = "android.intent.action.BOOT_COMPLETED"; private final String action; public Intent(String action) { this.action = action; } public String getAction() { return action; } }
JAVA
cat > "$work/android/provider/Settings.java" <<'JAVA'
package android.provider;
import android.content.ContentResolver;
public final class Settings {
    public static final class Global {
        public static int value = 2, reads, writes;
        public static boolean refuse, denied;
        public static int getInt(ContentResolver resolver, String key, int fallback) { reads++; throw new SecurityException("hidden key"); }
        public static boolean putInt(ContentResolver resolver, String key, int newValue) {
            if (!"navigationbars_state".equals(key)) throw new AssertionError(key);
            writes++;
            if (denied) throw new SecurityException("write denied");
            if (refuse) return false;
            value = newValue;
            return true;
        }
    }
}
JAVA
cat > "$work/android/util/Log.java" <<'JAVA'
package android.util;
public final class Log { public static int i(String t, String m) { return 0; } public static int w(String t, String m) { return 0; } public static int w(String t, String m, Throwable e) { return 0; } }
JAVA
cat > "$work/com/photoframe/c1nav/NavTest.java" <<'JAVA'
package com.photoframe.c1nav;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.Build;
import android.provider.Settings;
public final class NavTest {
    static final class FakeContext extends Context {
        boolean granted, optedIn;
        final ContentResolver resolver = new ContentResolver();
        public int checkSelfPermission(String p) { return granted ? PackageManager.PERMISSION_GRANTED : PackageManager.PERMISSION_DENIED; }
        public ContentResolver getContentResolver() { return resolver; }
        public SharedPreferences getSharedPreferences(String name, int mode) { return (key, fallback) -> optedIn; }
    }
    static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
    static void reset() { Settings.Global.value = 2; Settings.Global.reads = 0; Settings.Global.writes = 0; Settings.Global.refuse = false; Settings.Global.denied = false; }
    public static void main(String[] args) {
        FakeContext ctx = new FakeContext();
        Build.MODEL = "C1"; Build.DISPLAY = "C1_216_SY15_20260801";
        Build.FINGERPRINT = "Allwinner/a537_pro_arm64/a537-pro:15/AP3A.241105.008/26080114:user/release-keys";
        reset(); check(NavRestore.restore(ctx) != null && Settings.Global.writes == 0, "permission guard");
        ctx.granted = true; Build.MODEL = "other";
        check(NavRestore.restore(ctx) != null && Settings.Global.writes == 0, "model guard");
        Build.MODEL = "C1"; Build.DISPLAY = "other";
        check(NavRestore.restore(ctx) != null && Settings.Global.writes == 0, "display guard");
        Build.DISPLAY = "C1_216_SY15_20260801"; Build.FINGERPRINT = "other";
        check(NavRestore.restore(ctx) != null && Settings.Global.writes == 0, "fingerprint guard");
        Build.FINGERPRINT = "Allwinner/a537_pro_arm64/a537-pro:15/AP3A.241105.008/26080114:user/release-keys";
        check(NavRestore.restore(ctx) == null && Settings.Global.value == 1
                && Settings.Global.reads == 0, "restore despite denied hidden-key reads");
        reset(); Settings.Global.refuse = true;
        check(NavRestore.restore(ctx) != null && Settings.Global.value == 2, "refused write");
        reset(); Settings.Global.denied = true;
        check(NavRestore.restore(ctx) != null && Settings.Global.value == 2, "denied write");
        reset(); BootReceiver receiver = new BootReceiver();
        receiver.onReceive(ctx, null); receiver.onReceive(ctx, new Intent(Intent.ACTION_BOOT_COMPLETED));
        check(Settings.Global.writes == 0, "disabled boot restore");
        ctx.optedIn = true; receiver.onReceive(ctx, new Intent("unexpected"));
        check(Settings.Global.writes == 0, "unexpected broadcast");
        receiver.onReceive(ctx, new Intent(Intent.ACTION_BOOT_COMPLETED));
        check(Settings.Global.value == 1 && Settings.Global.reads == 0, "boot restore");
        System.out.println("C1 navigation helper checks passed");
    }
}
JAVA
"$JAVA/bin/javac" --release 8 -d "$work/classes" \
    $(find "$work/android" -name '*.java' -print) \
    "$work/com/photoframe/c1nav/NavTest.java" \
    "$ROOT/scripts/cypid-c1-nav/src/com/photoframe/c1nav/NavRestore.java" \
    "$ROOT/scripts/cypid-c1-nav/src/com/photoframe/c1nav/BootReceiver.java"
"$JAVA/bin/java" -cp "$work/classes" com.photoframe.c1nav.NavTest
