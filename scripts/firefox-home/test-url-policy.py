#!/usr/bin/env python3
"""Test actual URL validation and HomeActivity setting transitions with small host fakes.

Requires Python 3 and a JDK on PATH, without Android SDK, network or a device.
The SharedPreferences fake stages edits until apply(), as Android does. This does not test
Firefox launches, shortcut confirmation UI or Android lifecycle behavior.
"""
from pathlib import Path
import subprocess
import tempfile


SOURCE = Path(__file__).resolve().parent / "src/com/photoframe/firefoxhome"


def extract_method(source, signature):
    """Copy the method under test, so changes to production behavior exercise these cases."""
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


HARNESS = r'''
package com.photoframe.firefoxhome;
import java.util.HashMap;
public class UrlPolicyTest {
 static int tests;
 static final String FIREFOX = "org.mozilla.firefox";
 final SharedPreferences saved = new SharedPreferences();
 SharedPreferences prefs() { return saved; }
 static class Intent { String url; Intent(String u) { url=u; } String getStringExtra(String key) { return url; } }
 static class SharedPreferences {
  HashMap<String,String> values=new HashMap<>();
  String getString(String k,String d) { return values.containsKey(k)?values.get(k):d; }
  Editor edit(){ return new Editor(); }
  class Editor {
   HashMap<String,String> pending=new HashMap<>();
   Editor putString(String k,String v) { pending.put(k,v); return this; }
   Editor remove(String k) {pending.put(k,null);return this;}
   void apply() { for(String k:pending.keySet()) { if(pending.get(k)==null) values.remove(k); else values.put(k,pending.get(k)); } }
  }
 }
 static void check(boolean v,String name) { tests++; if(!v) throw new AssertionError(name); }
 static void valid(String url) { check(UrlPolicy.normalize(url).equals(url.trim()),"accept "+url); }
 static void invalid(String url) { check(UrlPolicy.normalize(url).isEmpty(),"reject "+url); }
 public static void main(String[] args) {
  for(String u: new String[]{"https://dashboard.example/","http://192.168.1.2:8123/path?foo=bar#x","https://[::1]:8123/","HTTP://localhost/","  https://example.com/  "}) valid(u);
  for(String u: new String[]{null,""," ","javascript:alert(1)","intent://example","file:///data/data/secrets","content://example/path","data:text/html,hi","https:","https:///path","https://","//example.com","http://exa mple.com/","https://example.com/\nfoo","https://example.com/%zz","https://example.com/\rfoo"}) invalid(u);
  UrlPolicyTest app=new UrlPolicyTest();
  app.saveUrlFromIntent(new Intent("https://first.example/"));
  app.prefs().edit().putString("shortcutPackage",FIREFOX).putString("shortcutId","old").apply();
  app.saveUrlFromIntent(new Intent("javascript:alert(1)"));
  check(app.url().equals("https://first.example/") && app.hasShortcut(),"invalid update preserves dashboard and pin");
  app.saveUrlFromIntent(null);
  check(app.url().equals("https://first.example/"),"missing extra preserves URL");
  app.saveUrlFromIntent(new Intent(" https://first.example/ "));
  check(app.hasShortcut(),"same URL preserves pin");
  app.saveUrlFromIntent(new Intent("https://second.example/"));
  check(!app.hasShortcut() && app.url().equals("https://second.example/"),"new URL clears pin");
  app.prefs().edit().putString("url","javascript:alert(1)").apply();
  check(app.url().isEmpty(),"invalid legacy saved URL blocked on read");
  app.prefs().edit().putString("shortcutPackage","other.app").putString("shortcutId","x").apply();
  check(!app.hasShortcut(),"legacy non-Firefox pin not accepted");
  System.out.println(tests+" Firefox URL/state regression checks passed");
 }
__METHODS__
}
'''


def main():
    source = (SOURCE / "HomeActivity.java").read_text(encoding="utf-8")
    methods = "\n".join(extract_method(source, signature) for signature in (
        "private String url()",
        "private void saveUrlFromIntent(Intent intent)",
        "private boolean hasShortcut()",
    ))
    with tempfile.TemporaryDirectory(prefix="firefox-url-policy-") as temporary:
        output = Path(temporary)
        (output / "UrlPolicy.java").write_text(
            (SOURCE / "UrlPolicy.java").read_text(encoding="utf-8"), encoding="utf-8")
        (output / "UrlPolicyTest.java").write_text(
            HARNESS.replace("__METHODS__", methods), encoding="utf-8")
        subprocess.run([
            "javac", "--release", "8", "-d", str(output),
            str(output / "UrlPolicy.java"), str(output / "UrlPolicyTest.java"),
        ], check=True)
        subprocess.run([
            "java", "-cp", str(output), "com.photoframe.firefoxhome.UrlPolicyTest",
        ], check=True)


if __name__ == "__main__":
    main()
