package com.example.pf1506kiosk;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;

/** Host-only regression checks; no Android classes or network. */
public final class FeedCacheTest {
    static final String A = "https://calendar.invalid/private-a";
    static final String B = "https://calendar.invalid/private-b";
    static final String CHORES = "https://calendar.invalid/private-chores";
    static final byte[] GOOD = calendar("old");
    static byte[] calendar(String summary) {
        return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:example\r\nSUMMARY:" + summary
                + "\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n").getBytes(StandardCharsets.UTF_8);
    }
    static Set<String> urls(String... values) { return new HashSet<>(Arrays.asList(values)); }
    static void check(boolean condition, String message) { if (!condition) throw new AssertionError(message); }
    static void equal(byte[] a, byte[] b, String message) { check(Arrays.equals(a, b), message); }
    public static void main(String[] args) throws Exception {
        File dir = Files.createTempDirectory("pf1506-cache-test-").toFile();
        try {
            FeedCache cache = new FeedCache(dir);
            Files.write(new File(dir, "feed-0.ics").toPath(), GOOD);
            Files.write(new File(dir, "feed-chores.ics").toPath(), GOOD);
            Files.write(new File(dir, "unrelated.txt").toPath(), GOOD);
            cache.configure(urls(A, CHORES));
            check(!new File(dir, "feed-0.ics").exists(), "legacy slot removed");
            check(!new File(dir, "feed-chores.ics").exists(), "unattributable legacy chores removed");
            check(new File(dir, "unrelated.txt").exists(), "unrelated file retained");
            long old = cache.begin(A);
            check(cache.store(A, old, GOOD), "store configured feed");
            check(cache.store(CHORES, cache.begin(CHORES), calendar("chores")), "store chores");
            equal(cache.read(A, old), GOOD, "same-feed offline copy");
            check(!FeedCache.identity(A).contains("private-a"), "secret absent from filename");
            cache.configure(urls(B, CHORES));
            check(cache.read(B, cache.begin(B)) == null, "replacement offline never inherits old events");
            check(!new File(dir, FeedCache.identity(A)).exists(), "removed feed cache pruned");
            check(!cache.store(A, old, GOOD), "old in-flight request cannot recreate removed cache");
            check(!new File(dir, FeedCache.identity(A)).exists(), "old cache remains absent");
            equal(cache.read(CHORES, cache.begin(CHORES)), calendar("chores"), "active chores retained");
            cache.configure(urls(A, B, CHORES));
            long token = cache.begin(A);
            cache.store(A, token, GOOD);
            cache.configure(urls(CHORES, B, A));
            equal(cache.read(A, cache.begin(A)), GOOD, "reorder retains correct identity");
            check(!cache.store(A, token, calendar("outdated")), "removed/readded or reconfigured generation rejected");
            for (byte[] bad : new byte[][] { "<html>login</html>".getBytes(StandardCharsets.UTF_8),
                    "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nEND:VCALENDAR".getBytes(StandardCharsets.UTF_8),
                    "BEGIN:VCALENDAR\nVERSION:2.0\ninvalid\nEND:VCALENDAR".getBytes(StandardCharsets.UTF_8),
                    new byte[] {(byte) 0xFF} }) {
                try { cache.store(A, cache.begin(A), bad); throw new AssertionError("invalid data accepted"); }
                catch (IOException expected) { }
                equal(cache.read(A, cache.begin(A)), GOOD, "invalid download preserves good copy");
            }
            for (String valid : new String[] {
                    "begin:vcalendar\r\nversion:2.0\r\nbegin:vevent\r\nsummary:Keep This Case\r\nend:vevent\r\nend:vcalendar\r\n",
                    "bEgIn:Vcalendar\r\nVeRsIoN:2.0\r\nBEGIN:Vevent\r\nSuMmArY:Keep This Case\r\neNd:vEVENT\r\nEND:vCALENDAR\r\n" }) {
                byte[] body = valid.getBytes(StandardCharsets.UTF_8);
                check(cache.store(A, cache.begin(A), body), "mixed/lowercase calendar accepted");
                equal(cache.read(A, cache.begin(A)), body, "property values and body case preserved");
            }
            byte[] retained = cache.read(A, cache.begin(A));
            for (String bad : new String[] {
                    "begin:vcalendar\nversion:2.0\nbegin:vevent\nend:vcalendar",
                    "begin:vcalendar\nversion:2.0\nbroken line\nend:vcalendar",
                    "begin:vcalendar\nversion:2.0\nend:vcalendar\nbegin:vcalendar\nversion:2.0\nend:vcalendar",
                    "begin:vcalendar\nversion:3.0\nend:vcalendar" }) {
                try { cache.store(A, cache.begin(A), bad.getBytes(StandardCharsets.UTF_8));
                    throw new AssertionError("malformed mixed/lowercase body accepted"); }
                catch (IOException expected) { }
                equal(cache.read(A, cache.begin(A)), retained, "malformed response preserves valid mixed-case copy");
            }
            System.out.println("PASS: lowercase/mixed-case structural tokens, unchanged values, malformed-content rejection");
            CountDownLatch start = new CountDownLatch(1);
            AtomicReference<Throwable> failure = new AtomicReference<>();
            Thread[] workers = new Thread[6];
            long current = cache.begin(A);
            for (int i = 0; i < workers.length; i++) {
                final byte[] body = calendar("refresh-" + i);
                workers[i] = new Thread(() -> {
                    try { start.await(); check(cache.store(A, current, body), "concurrent refresh"); }
                    catch (Throwable e) { failure.compareAndSet(null, e); }
                });
                workers[i].start();
            }
            start.countDown();
            for (Thread t : workers) t.join();
            if (failure.get() != null) throw new AssertionError(failure.get());
            FeedCache.validate(cache.read(A, current));
            check(Arrays.stream(dir.list()).noneMatch(n -> n.endsWith(".tmp")), "no temporary-file collisions or leftovers");
            System.out.println("PASS: identity, replacement/offline, reorder, removal/in-flight, chores, validation, concurrent refreshes");
        } finally {
            for (File file : dir.listFiles()) file.delete();
            dir.delete();
        }
    }
}
