package com.example.pf1506kiosk;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayDeque;
import java.util.HashSet;
import java.util.Set;

/** Private URL-identity cache. No URL is stored in a filename or a log message. */
final class FeedCache {
    private final File directory;
    private Set<String> active = new HashSet<>();
    private long generation;

    FeedCache(File directory) { this.directory = directory; }

    static String identity(String url) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(url.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder();
            for (byte b : digest) hex.append(String.format(java.util.Locale.US, "%02x", b & 255));
            return "feed-v2-" + hex + ".ics";
        } catch (NoSuchAlgorithmException e) { throw new AssertionError(e); }
    }

    synchronized void configure(Set<String> urls) {
        Set<String> next = new HashSet<>();
        for (String url : urls) next.add(identity(url));
        active = next;
        generation++; // Invalidates old in-flight requests, including remove/re-add.
        File[] files = directory.listFiles();
        if (files == null) return;
        for (File f : files) {
            String n = f.getName();
            // Legacy slots cannot be attributed safely. Keep only active identity caches.
            if ((n.matches("feed-(?:[0-9]+|chores)\\.ics(?:\\.tmp)?")
                    || n.matches("feed-v2-[0-9a-f]{64}\\.ics") || n.matches("feed-download-.*\\.tmp"))
                    && !active.contains(n)) f.delete();
        }
    }

    synchronized long begin(String url) { return active.contains(identity(url)) ? generation : -1; }
    private boolean current(String url, long token) {
        return token >= 0 && token == generation && active.contains(identity(url));
    }

    synchronized boolean store(String url, long token, byte[] body) throws IOException {
        if (!current(url, token)) return false;
        validate(body); // Never replace the last good copy with an HTTP 200 error page.
        File tmp = File.createTempFile("feed-download-", ".tmp", directory);
        try {
            Files.write(tmp.toPath(), body);
            Files.move(tmp.toPath(), new File(directory, identity(url)).toPath(),
                    StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } finally { tmp.delete(); }
        return true;
    }

    synchronized byte[] read(String url, long token) throws IOException {
        if (!current(url, token)) return null;
        File file = new File(directory, identity(url));
        if (!file.isFile()) return null;
        byte[] body = Files.readAllBytes(file.toPath());
        validate(body);
        return body;
    }

    /** Envelope/component validation, not a complete RFC 5545 event validator. */
    static void validate(byte[] body) throws IOException {
        if (body.length == 0 || body.length > 10 * 1024 * 1024) throw new IOException("invalid calendar size");
        String text = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(body)).toString();
        text = text.replaceFirst("^\\uFEFF", "").replace("\r\n", "\n").replaceAll("\n[ \\t]", "");
        String[] lines = text.trim().split("\n");
        if (!lines[0].equalsIgnoreCase("BEGIN:VCALENDAR") || !lines[lines.length - 1].equalsIgnoreCase("END:VCALENDAR"))
            throw new IOException("not an iCalendar");
        ArrayDeque<String> components = new ArrayDeque<>();
        boolean version = false, closed = false;
        for (String line : lines) {
            if (closed) throw new IOException("multiple calendars");
            if (line.isEmpty() || !line.matches("[A-Za-z0-9-]+[;:].*")) throw new IOException("invalid calendar line");
            // RFC 5545 tokens are case-insensitive; retain the original value/body bytes.
            String token = line.toUpperCase(java.util.Locale.ROOT);
            if (token.startsWith("BEGIN:")) components.push(token.substring(6));
            else if (token.startsWith("END:")) {
                if (components.isEmpty() || !components.pop().equals(token.substring(4)))
                    throw new IOException("unbalanced calendar");
                closed = components.isEmpty();
            } else if (components.isEmpty()) throw new IOException("property outside calendar");
            else if (token.equals("VERSION:2.0") && components.size() == 1) version = true;
        }
        if (!components.isEmpty() || !version) throw new IOException("incomplete calendar");
    }
}
