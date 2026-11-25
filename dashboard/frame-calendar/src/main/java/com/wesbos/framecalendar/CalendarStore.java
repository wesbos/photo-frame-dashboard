package com.wesbos.framecalendar;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

final class CalendarStore {
    static final String[] KEYS = {"personal", "family", "tripit", "holidays"};
    static final String[] NAMES = {"Martin", "Catherine", "TripIt", "UK holidays"};
    static final int[] COLORS = {0xff89b4fa, 0xfff5c2e7, 0xffa6adc8, 0xffa6e3a1};
    private final Context context;
    private final SharedPreferences prefs;
    private String accessToken;

    static final class Result {
        final List<Event> events = new ArrayList<>();
        final List<String> notices = new ArrayList<>();
    }

    CalendarStore(Context context, SharedPreferences prefs) {
        this.context = context;
        this.prefs = prefs;
    }

    Result loadCached(LocalDate from, LocalDate to, ZoneId zone) {
        Result result = new Result();
        for (int source = 0; source < KEYS.length; source++) {
            String url = prefs.getString(KEYS[source], "").trim();
            if (url.isEmpty() || url.startsWith("ha:")) continue;
            File cache = new File(context.getFilesDir(), "calendar-" + source + "-" + hash(url));
            if (!cache.exists()) continue;
            try (InputStream in = new FileInputStream(cache)) {
                result.events.addAll(parse(read(in), url, from, to, zone, source));
            } catch (IOException | JSONException | IllegalArgumentException e) {
                Log.w("FrameCalendar", "Saved calendar source " + source + " could not be read");
            }
        }
        return result;
    }

    Result load(LocalDate from, LocalDate to, ZoneId zone) {
        Result result = new Result();
        accessToken = null;
        for (int source = 0; source < KEYS.length; source++) {
            String url = prefs.getString(KEYS[source], "").trim();
            if (url.isEmpty()) {
                result.notices.add(NAMES[source] + ": connect in Settings");
                continue;
            }
            File cache = new File(context.getFilesDir(), "calendar-" + source + "-" + hash(url));
            try {
                String body = url.startsWith("ha:") ? homeAssistant(url.substring(3), from, to)
                        : request(url, null, null);
                List<Event> events = parse(body, url, from, to, zone, source);
                try (FileOutputStream out = new FileOutputStream(cache)) {
                    out.write(body.getBytes(StandardCharsets.UTF_8));
                }
                result.events.addAll(events);
            } catch (IOException | JSONException | IllegalArgumentException e) {
                // Network errors can include private URLs, so never log exception messages.
                Log.w("FrameCalendar", "Calendar source " + source + " failed: " + e.getClass().getSimpleName());
                if (cache.exists() && !url.startsWith("ha:")) {
                    try (InputStream in = new FileInputStream(cache)) {
                        result.events.addAll(parse(read(in), url, from, to, zone, source));
                        result.notices.add(NAMES[source] + ": offline, showing saved data");
                    } catch (IOException | JSONException | IllegalArgumentException invalidCache) {
                        result.notices.add(NAMES[source] + ": unavailable; check Settings");
                        Log.w("FrameCalendar", "Saved calendar source " + source + " could not be read");
                    }
                } else {
                    result.notices.add(NAMES[source] + ": unavailable; check connection and Settings");
                }
            }
        }
        return result;
    }

    private List<Event> parse(String body, String url, LocalDate from, LocalDate to,
            ZoneId zone, int source) throws IOException, JSONException {
        if (!url.startsWith("ha:")) return IcsReader.read(body, from, to, zone, source);
        List<Event> result = new ArrayList<>();
        JSONArray values = new JSONArray(body);
        for (int i = 0; i < values.length(); i++) {
            JSONObject item = values.getJSONObject(i);
            String a = item.getJSONObject("start").optString("dateTime");
            boolean allDay = a.isEmpty();
            ZonedDateTime start = allDay ? LocalDate.parse(item.getJSONObject("start").getString("date")).atStartOfDay(zone)
                    : ZonedDateTime.parse(a);
            ZonedDateTime end = allDay ? LocalDate.parse(item.getJSONObject("end").getString("date")).atStartOfDay(zone)
                    : ZonedDateTime.parse(item.getJSONObject("end").getString("dateTime"));
            result.add(new Event(item.optString("summary", "(Untitled)"), item.optString("location"),
                    item.optString("description"), start, end, allDay, source));
        }
        return result;
    }

    private String homeAssistant(String entity, LocalDate from, LocalDate to) throws IOException, JSONException {
        if (!entity.matches("calendar\\.[a-z0-9_]+")) throw new IOException("Invalid calendar entity");
        URL panel = new URL(prefs.getString("ha_url", ""));
        String server = panel.getProtocol() + "://" + panel.getAuthority();
        if (accessToken == null) {
            JSONObject auth = new JSONObject(prefs.getString("ha_auth", "{}"));
            String form = "grant_type=refresh_token&refresh_token=" + encode(auth.getString("refresh_token"))
                    + "&client_id=" + encode(auth.getString("clientId"));
            accessToken = new JSONObject(request(server + "/auth/token", form, null)).getString("access_token");
        }
        return request(server + "/api/calendars/" + entity + "?start=" + encode(from + "T00:00:00")
                + "&end=" + encode(to + "T00:00:00"), null, accessToken);
    }

    private static String encode(String value) throws IOException {
        return URLEncoder.encode(value, "UTF-8");
    }

    private static String hash(String value) {
        try {
            byte[] bytes = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder();
            for (byte b : bytes) out.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
            return out.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    static String request(String address, String form, String token) throws IOException {
        URL url = new URL(address);
        if (!url.getProtocol().equals("https") && !url.getProtocol().equals("http")) {
            throw new IOException("Unsupported URL scheme");
        }
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(20000);
        connection.setInstanceFollowRedirects(false);
        try {
            if (token != null) connection.setRequestProperty("Authorization", "Bearer " + token);
            if (form != null) {
                connection.setRequestMethod("POST");
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
                try (java.io.OutputStream out = connection.getOutputStream()) {
                    out.write(form.getBytes(StandardCharsets.UTF_8));
                }
            }
            int status = connection.getResponseCode();
            if (status != 200) throw new IOException("Calendar HTTP status " + status);
            try (InputStream in = connection.getInputStream()) { return read(in); }
        } finally {
            connection.disconnect();
        }
    }

    static String read(InputStream in) throws IOException {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] bytes = new byte[8192];
        int count;
        while ((count = in.read(bytes)) != -1) {
            if (buffer.size() + count > 8 * 1024 * 1024) throw new IOException("Feed exceeds 8 MiB");
            buffer.write(bytes, 0, count);
        }
        return buffer.toString("UTF-8");
    }
}
