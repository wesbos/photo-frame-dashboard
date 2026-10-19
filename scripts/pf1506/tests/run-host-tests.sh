#!/usr/bin/env bash
# Host-only tests: all Android/ADB/firewall operations use private command doubles.
# Requires Python 3, Node.js, JDK 17+, bash and sha256sum. No downloads or devices.
set -euo pipefail
cd "$(dirname "$0")"
python3 test_adb_wifi.py -v
python3 test_backup.py -v
node test_ui.cjs
node test_backend.cjs
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
javac --release 8 -Xlint:-options -d "$work" ../kiosk/src/com/example/pf1506kiosk/FeedCache.java FeedCacheTest.java
java -cp "$work" com.example.pf1506kiosk.FeedCacheTest
