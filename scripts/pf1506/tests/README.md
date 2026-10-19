# Host regression tests

Run `bash run-host-tests.sh` from this directory with Python 3, Node.js, JDK 17+, bash and `sha256sum` on PATH.
No downloads, devices, network access, Android properties or real firewall commands are used.

The Android shell tests put inert command doubles first on PATH, model rule ordering, persisted TCP listeners,
configuration races and command failures, and put the lock in a temporary directory. They do not establish actual
Android init ordering, property permissions, socket closure or packet filtering on hardware.

Backup tests execute a scratch copy with the chunk constants scaled from 32 MiB to 16 bytes. A fake ADB streams
small deterministic partitions, appends status text, returns independent hashes and injects a mismatch. The tests
check numerical assembly order, deletion of chunks, retained-image manifest hashes and stopping on mismatch.

The Node VM uses small DOM fixtures for Today event/day/pop-up identity, asynchronous load races and visible
wrong-PIN/lockout status. It does not replace a real WebView layout or Android setup-server test.

The backend test models a persisted configuration save whose HTTP reply fails before any page-reload callback.
It exercises digest identities for URL-only replacements, offline fallback, reorder/removal, chores and old
in-flight responses, plus coalesced selected/current-week requests. Its small ICAL double supplies single events;
it does not test calendar parsing or recurrence. The UI test also starts from empty state and resolves a navigated
week before the initial/current-week requests, checking that Today only receives separately requested week zero.

The Java test compiles the production `FeedCache` with Java 8 API compatibility and exercises identity, offline
replacement, reordering, removal, stale in-flight requests, chores preservation, invalid responses and concurrent
refreshes. It also checks lower/mixed-case structural tokens, byte-preserved values and malformed-body rejection.
It does not replace an Android APK build, integration test or complete RFC 5545 validation.
