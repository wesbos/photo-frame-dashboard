package com.example.pf1506kiosk;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.regex.Pattern;
import java.util.HashSet;
import java.util.Set;

/**
 * Standalone-mode settings, saved in the app's private preferences:
 *
 * {
 *   "calendars": [{"name": "Family", "url": "https://...ics", "color": "#2f7bf5"}],
 *   "choresUrl": "https://...ics" or "",
 *   "kids": [{"name": "Ana", "color": "#e8577e", "aliases": ["Anabel"]}],
 *   "weather": {"place": "Springfield", "latitude": 39.8, "longitude": -89.6} or null,
 *   "units": "us" | "metric"
 * }
 *
 * The iCal addresses are secret (anyone with one can read that calendar), so the page
 * never sees them: it gets {@link #publicJson} and asks for /feed/<digest>.
 */
final class Config {
    private static final String PREFS = "kiosk";
    private static final String KEY = "standalone_config";
    private static final int MAX_CALENDARS = 12;
    private static final int MAX_KIDS = 8;
    private static final Pattern COLOR = Pattern.compile("#[0-9a-fA-F]{6}");

    private Config() { }

    static JSONObject load(Context c) {
        SharedPreferences p = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        try {
            return new JSONObject(p.getString(KEY, "{}"));
        } catch (JSONException e) {
            return new JSONObject();
        }
    }

    static boolean isConfigured(Context c) {
        JSONArray cals = load(c).optJSONArray("calendars");
        return cals != null && cals.length() > 0;
    }

    /** Validates and stores a config sent by the setup page. Throws with a readable message. */
    static void save(Context c, String body) throws IllegalArgumentException {
        JSONObject in;
        try {
            in = new JSONObject(body);
        } catch (JSONException e) {
            throw new IllegalArgumentException("not JSON");
        }
        JSONObject out = new JSONObject();
        try {
            JSONArray cals = new JSONArray(), inCals = in.optJSONArray("calendars");
            for (int i = 0; inCals != null && i < inCals.length(); i++) {
                JSONObject x = inCals.getJSONObject(i);
                String url = x.optString("url").trim();
                if (url.isEmpty()) continue;
                cals.put(new JSONObject()
                        .put("name", name(x.optString("name"), "Calendar " + (i + 1)))
                        .put("url", checkUrl(url))
                        .put("color", color(x.optString("color"))));
            }
            if (cals.length() > MAX_CALENDARS) throw new IllegalArgumentException("at most " + MAX_CALENDARS + " calendars");
            out.put("calendars", cals);

            String chores = in.optString("choresUrl").trim();
            out.put("choresUrl", chores.isEmpty() ? "" : checkUrl(chores));

            JSONArray kids = new JSONArray(), inKids = in.optJSONArray("kids");
            for (int i = 0; inKids != null && i < inKids.length(); i++) {
                JSONObject x = inKids.getJSONObject(i);
                String n = x.optString("name").trim();
                if (n.isEmpty()) continue;
                JSONArray aliases = new JSONArray(), inA = x.optJSONArray("aliases");
                for (int j = 0; inA != null && j < inA.length() && j < 5; j++) {
                    String a = inA.optString(j).trim();
                    if (!a.isEmpty()) aliases.put(name(a, a));
                }
                kids.put(new JSONObject().put("name", name(n, n)).put("color", color(x.optString("color")))
                        .put("aliases", aliases));
            }
            if (kids.length() > MAX_KIDS) throw new IllegalArgumentException("at most " + MAX_KIDS + " people for chores");
            out.put("kids", kids);

            JSONObject w = in.optJSONObject("weather");
            if (w != null && w.has("latitude") && w.has("longitude")) {
                double lat = w.getDouble("latitude"), lon = w.getDouble("longitude");
                if (lat < -90 || lat > 90 || lon < -180 || lon > 180) throw new IllegalArgumentException("bad location");
                out.put("weather", new JSONObject().put("place", name(w.optString("place"), "")).put("latitude", lat)
                        .put("longitude", lon));
            }
            out.put("units", "metric".equals(in.optString("units")) ? "metric" : "us");
        } catch (JSONException e) {
            throw new IllegalArgumentException("bad field: " + e.getMessage());
        }
        synchronized (LocalContent.class) {
            c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY, out.toString()).apply();
            LocalContent.configChanged(c);
        }
    }

    /** What the page sees: everything except the iCal addresses. */
    static JSONObject publicJson(Context c) throws JSONException {
        JSONObject cfg = load(c), out = new JSONObject();
        JSONArray cals = new JSONArray(), in = cfg.optJSONArray("calendars");
        for (int i = 0; in != null && i < in.length(); i++) {
            JSONObject x = in.getJSONObject(i);
            cals.put(new JSONObject().put("name", x.optString("name")).put("color", x.optString("color"))
                    .put("feedId", FeedCache.identity(x.optString("url"))));
        }
        out.put("calendars", cals);
        String chores = cfg.optString("choresUrl");
        out.put("hasChores", !chores.isEmpty());
        if (!chores.isEmpty()) out.put("choresFeedId", FeedCache.identity(chores));
        out.put("kids", cfg.optJSONArray("kids") != null ? cfg.getJSONArray("kids") : new JSONArray());
        if (cfg.has("weather")) out.put("weather", cfg.getJSONObject("weather"));
        out.put("units", cfg.optString("units", "us"));
        return out;
    }

    /** Resolve an active opaque feed identity, never a mutable calendar slot. */
    static String feedUrl(Context c, String key) {
        JSONObject cfg = load(c);
        String chores = cfg.optString("choresUrl");
        if (!chores.isEmpty() && FeedCache.identity(chores).equals(key)) return chores;
        JSONArray cals = cfg.optJSONArray("calendars");
        for (int i = 0; cals != null && i < cals.length(); i++) {
            JSONObject cal = cals.optJSONObject(i);
            String url = cal == null ? "" : cal.optString("url");
            if (!url.isEmpty() && FeedCache.identity(url).equals(key)) return url;
        }
        return null;
    }

    /** Includes chores so pruning calendar slots cannot remove its active cache. */
    static Set<String> feedUrls(Context c) {
        JSONObject cfg = load(c);
        Set<String> urls = new HashSet<>();
        JSONArray cals = cfg.optJSONArray("calendars");
        for (int i = 0; cals != null && i < cals.length(); i++) {
            JSONObject cal = cals.optJSONObject(i);
            if (cal != null && !cal.optString("url").isEmpty()) urls.add(cal.optString("url"));
        }
        String chores = cfg.optString("choresUrl");
        if (!chores.isEmpty()) urls.add(chores);
        return urls;
    }

    private static String name(String s, String fallback) {
        s = s.trim().replaceAll("[\\p{Cntrl}<>]", "");
        if (s.isEmpty()) s = fallback;
        return s.length() > 40 ? s.substring(0, 40) : s;
    }

    private static String color(String s) {
        return COLOR.matcher(s.trim()).matches() ? s.trim() : "#2f7bf5";
    }

    private static String checkUrl(String u) {
        if (u.startsWith("webcal://")) u = "https://" + u.substring("webcal://".length());
        if (!u.startsWith("https://") && !u.startsWith("http://")) {
            throw new IllegalArgumentException("calendar addresses start with https://");
        }
        if (u.length() > 2000) throw new IllegalArgumentException("address too long");
        return u;
    }
}
