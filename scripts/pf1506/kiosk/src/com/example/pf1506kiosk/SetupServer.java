package com.example.pf1506kiosk;

import android.content.Context;
import android.util.Log;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Collections;
import java.util.Locale;

/**
 * A small settings page on the home network, so calendars can be added from a phone
 * instead of typed on the frame. http://<frame>:8080/
 *
 * It runs for WINDOW_MS after the app starts (so, after every power-on), for as long as
 * the frame has no calendars, and for WINDOW_MS after each save. It needs the 6-digit PIN shown on the frame's screen; five wrong
 * PINs stop it until the next start. It is plain HTTP on the LAN: the calendar addresses
 * you paste cross your Wi-Fi unencrypted, like any LAN admin page.
 *
 *   GET  /             the form (assets/web/setup.html)
 *   GET  /api/config   current settings, including the addresses     (header X-Pin)
 *   POST /api/config   save settings, JSON as described in Config     (header X-Pin)
 */
final class SetupServer extends Thread {
    interface Listener {
        void onSetupChanged(String address, String pin);  // address null = stopped
        void onConfigSaved();
    }

    static final int PORT = 8080;
    static final long WINDOW_MS = 15 * 60_000;
    private static final String TAG = "FrameKiosk";
    private static final int MAX_BODY = 64 * 1024;
    private static final int MAX_FAILURES = 5;

    private final Context ctx;
    private final Listener listener;
    private final String pin;
    private volatile long stopAt;
    private volatile ServerSocket socket;
    private int failures;

    SetupServer(Context ctx, Listener listener) {
        super("setup-server");
        this.ctx = ctx.getApplicationContext();
        this.listener = listener;
        this.pin = String.format(Locale.US, "%06d", new SecureRandom().nextInt(1_000_000));
        this.stopAt = System.currentTimeMillis() + WINDOW_MS;
        setDaemon(true);
    }

    void shutdown() {
        ServerSocket s = socket;
        if (s != null) try { s.close(); } catch (IOException ignored) { }
    }

    @Override public void run() {
        try (ServerSocket s = new ServerSocket(PORT)) {
            socket = s;
            s.setSoTimeout(5_000);
            String ip = lanAddress();
            listener.onSetupChanged(ip == null ? "http://<frame's IP>:" + PORT : "http://" + ip + ":" + PORT, pin);
            Log.i(TAG, "setup page on port " + PORT);
            while (!isInterrupted() && failures < MAX_FAILURES
                    && (System.currentTimeMillis() < stopAt || !Config.isConfigured(ctx))) {
                try (Socket c = s.accept()) {
                    c.setSoTimeout(10_000);
                    serve(c);
                } catch (java.net.SocketTimeoutException ignored) {
                    // re-check the window
                } catch (IOException | RuntimeException e) {
                    if (s.isClosed()) break;
                    Log.w(TAG, "setup request: " + e);
                }
            }
        } catch (IOException e) {
            Log.w(TAG, "setup page not started: " + e);
        } finally {
            listener.onSetupChanged(null, null);
            Log.i(TAG, "setup page stopped");
        }
    }

    private void serve(Socket c) throws IOException {
        InputStream in = new BufferedInputStream(c.getInputStream());
        String request = line(in);
        if (request == null) return;
        String[] parts = request.split(" ");
        if (parts.length < 2) { reply(c, 400, "text/plain", "bad request"); return; }
        String method = parts[0], path = parts[1];
        int length = 0;
        String givenPin = null;
        for (String h; (h = line(in)) != null && !h.isEmpty(); ) {
            int i = h.indexOf(':');
            if (i < 0) continue;
            String k = h.substring(0, i).trim().toLowerCase(Locale.US), v = h.substring(i + 1).trim();
            if (k.equals("content-length")) length = Integer.parseInt(v);
            if (k.equals("x-pin")) givenPin = v;
        }
        if (method.equals("GET") && (path.equals("/") || path.equals("/index.html"))) {
            try (InputStream page = ctx.getAssets().open("web/setup.html")) {
                reply(c, 200, "text/html; charset=utf-8", read(page, 256 * 1024));
            }
            return;
        }
        if (!path.equals("/api/config")) { reply(c, 404, "text/plain", "not found"); return; }
        if (givenPin == null || !java.security.MessageDigest.isEqual(
                givenPin.getBytes(StandardCharsets.UTF_8), pin.getBytes(StandardCharsets.UTF_8))) {
            failures++;
            reply(c, 403, "text/plain", "wrong PIN (" + (MAX_FAILURES - failures) + " tries left before the page closes)");
            return;
        }
        failures = 0;
        if (method.equals("GET")) {
            reply(c, 200, "application/json", Config.load(ctx).toString());
        } else if (method.equals("POST")) {
            if (length <= 0 || length > MAX_BODY) { reply(c, 413, "text/plain", "too large"); return; }
            byte[] body = new byte[length];
            for (int off = 0, n; off < length; off += n) {
                n = in.read(body, off, length - off);
                if (n < 0) throw new IOException("short body");
            }
            try {
                Config.save(ctx, new String(body, StandardCharsets.UTF_8));
            } catch (IllegalArgumentException e) {
                reply(c, 400, "text/plain", e.getMessage());
                return;
            }
            stopAt = Math.max(stopAt, System.currentTimeMillis() + WINDOW_MS);
            reply(c, 200, "application/json", Config.load(ctx).toString());
            listener.onConfigSaved();
        } else {
            reply(c, 405, "text/plain", "method not allowed");
        }
    }

    private static String line(InputStream in) throws IOException {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        for (int ch; (ch = in.read()) >= 0; ) {
            if (ch == '\n') return b.toString("UTF-8").replace("\r", "");
            if (b.size() > 8192) throw new IOException("line too long");
            b.write(ch);
        }
        return b.size() > 0 ? b.toString("UTF-8") : null;
    }

    private static String read(InputStream in, int max) throws IOException {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        for (int n; (n = in.read(buf)) > 0 && b.size() < max; ) b.write(buf, 0, n);
        return b.toString("UTF-8");
    }

    private static void reply(Socket c, int code, String type, String body) throws IOException {
        byte[] b = body.getBytes(StandardCharsets.UTF_8);
        String head = "HTTP/1.1 " + code + (code == 200 ? " OK" : " Error") + "\r\n"
                + "Content-Type: " + type + "\r\nContent-Length: " + b.length + "\r\n"
                + "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
                + "Content-Security-Policy: default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                + "connect-src 'self' https://geocoding-api.open-meteo.com\r\n"
                + "Connection: close\r\n\r\n";
        OutputStream out = c.getOutputStream();
        out.write(head.getBytes(StandardCharsets.US_ASCII));
        out.write(b);
        out.flush();
    }

    /** The frame's IPv4 address on Wi-Fi/Ethernet, for the address shown on screen. */
    static String lanAddress() {
        try {
            for (NetworkInterface ni : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!ni.isUp() || ni.isLoopback()) continue;
                for (InetAddress a : Collections.list(ni.getInetAddresses())) {
                    if (a instanceof Inet4Address && a.isSiteLocalAddress()) return a.getHostAddress();
                }
            }
        } catch (IOException ignored) { }
        return null;
    }
}
