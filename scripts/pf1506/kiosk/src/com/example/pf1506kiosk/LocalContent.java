package com.example.pf1506kiosk;

import android.content.Context;
import android.net.Uri;
import android.util.Log;
import android.webkit.WebResourceResponse;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * Standalone mode: the WebView loads https://kiosk.invalid/, which never reaches the
 * network (".invalid" can't resolve). Every request to it is answered here:
 *
 *   /, /index.html, /backend.js, /ical.min.js   the page, from assets/web/
 *   /config.json    settings without the secret iCal addresses (Config.publicJson)
 *   /feed/<key>     one calendar, fetched by the app; the last good copy is kept on disk
 *                   and served with "X-Stale: 1" when the calendar can't be reached
 *
 * Called on WebView's background threads, so blocking network reads are fine here.
 */
final class LocalContent {
    static final String ORIGIN = "https://kiosk.invalid";
    private static final String TAG = "FrameKiosk";
    private static final int MAX_FEED_BYTES = 10 * 1024 * 1024;
    private static final Map<String, String> TYPES = new HashMap<>();
    static {
        TYPES.put("index.html", "text/html");
        TYPES.put("backend.js", "text/javascript");
        TYPES.put("ical.min.js", "text/javascript");
    }

    private static FeedCache feedCache;

    private static synchronized FeedCache cache(Context ctx) {
        if (feedCache == null) {
            feedCache = new FeedCache(ctx.getNoBackupFilesDir());
            feedCache.configure(Config.feedUrls(ctx));
        }
        return feedCache;
    }

    static synchronized void configChanged(Context ctx) {
        cache(ctx).configure(Config.feedUrls(ctx));
    }

    private final Context ctx;
    private volatile JSONObject setupInfo;

    LocalContent(Context ctx) {
        this.ctx = ctx.getApplicationContext();
        cache(this.ctx); // Purge obsolete/legacy caches even when no feeds are requested.
    }

    /** While the setup page is running, the frame shows its address and PIN. */
    void setSetupInfo(String address, String pin) {
        JSONObject o = null;
        if (address != null) {
            try {
                o = new JSONObject().put("address", address).put("pin", pin);
            } catch (JSONException ignored) { }
        }
        setupInfo = o;
    }

    WebResourceResponse handle(Uri uri, String method) {
        if (!"GET".equals(method)) return text(405, "only GET");
        String path = uri.getPath() == null ? "/" : uri.getPath();
        if (path.equals("/")) path = "/index.html";
        String name = path.substring(1);
        try {
            if (TYPES.containsKey(name)) {
                return respond(200, TYPES.get(name), ctx.getAssets().open("web/" + name), null);
            }
            if (name.equals("config.json")) {
                JSONObject cfg = Config.publicJson(ctx);
                if (setupInfo != null) cfg.put("setup", setupInfo);
                return bytes(200, "application/json", cfg.toString().getBytes(StandardCharsets.UTF_8), null);
            }
            if (name.startsWith("feed/")) return feed(name.substring(5));
        } catch (IOException | JSONException e) {
            Log.w(TAG, "local content " + path, e);
            return text(500, e.toString());
        }
        return text(404, "not found");
    }

    private WebResourceResponse feed(String key) {
        final String url;
        final FeedCache cache;
        final long token;
        synchronized (LocalContent.class) {
            cache = cache(ctx);
            url = Config.feedUrl(ctx, key);
            if (url == null) return text(404, "no such calendar");
            token = cache.begin(url);
        }
        try {
            byte[] body = download(url);
            synchronized (LocalContent.class) {
                if (!url.equals(Config.feedUrl(ctx, key)) || !cache.store(url, token, body))
                    return text(409, "calendar settings changed; reload");
            }
            return bytes(200, "text/calendar", body, null);
        } catch (IOException e) {
            // Connection exceptions may include the secret URL: never log/return them.
            Log.w(TAG, "calendar download or validation failed");
            synchronized (LocalContent.class) {
                if (!url.equals(Config.feedUrl(ctx, key))) return text(409, "calendar settings changed; reload");
                try {
                    byte[] body = cache.read(url, token);
                    if (body != null) {
                        Map<String, String> h = new HashMap<>();
                        h.put("X-Stale", "1");
                        return bytes(200, "text/calendar", body, h);
                    }
                } catch (IOException ignored) { }
            }
            return text(502, "can't load a valid copy of the calendar");
        }
    }

    private static byte[] download(String address) throws IOException {
        URL u = new URL(address);
        for (int hops = 0; hops < 5; hops++) {
            HttpURLConnection c = (HttpURLConnection) u.openConnection();
            c.setConnectTimeout(15_000);
            c.setReadTimeout(20_000);
            c.setInstanceFollowRedirects(false);
            c.setRequestProperty("User-Agent", "pf1506-kiosk/1");
            try {
                int code = c.getResponseCode();
                if (code >= 300 && code < 400 && c.getHeaderField("Location") != null) {
                    u = new URL(u, c.getHeaderField("Location"));
                    if (!"https".equals(u.getProtocol()) && !"http".equals(u.getProtocol())) throw new IOException("bad redirect");
                    continue;
                }
                if (code != 200) throw new IOException("calendar address answered HTTP " + code);
                try (InputStream in = c.getInputStream()) {
                    ByteArrayOutputStream out = new ByteArrayOutputStream();
                    byte[] buf = new byte[16384];
                    for (int n; (n = in.read(buf)) > 0; ) {
                        out.write(buf, 0, n);
                        if (out.size() > MAX_FEED_BYTES) throw new IOException("calendar is over 10 MB");
                    }
                    return out.toByteArray();
                }
            } finally {
                c.disconnect();
            }
        }
        throw new IOException("too many redirects");
    }

    private static WebResourceResponse respond(int code, String type, InputStream body, Map<String, String> extra) {
        Map<String, String> h = new HashMap<>();
        h.put("Cache-Control", "no-store");
        if (extra != null) h.putAll(extra);
        return new WebResourceResponse(type, "UTF-8", code, code == 200 ? "OK" : "Error", h, body);
    }

    private static WebResourceResponse bytes(int code, String type, byte[] body, Map<String, String> extra) {
        return respond(code, type, new ByteArrayInputStream(body), extra);
    }

    private static WebResourceResponse text(int code, String msg) {
        return bytes(code, "text/plain", msg.getBytes(StandardCharsets.UTF_8), null);
    }
}
