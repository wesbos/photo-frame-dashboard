#!/system/bin/sh
# enable-adb.sh — SD card payload for the SSA 15X1 (RK3326, Android 8.1)
# Runs as root via Frameo's AManufacturerUtilities command injection.
# Writes the host's ADB public key and enables persistent TCP ADB on port 5555.
#
# Usage: this file is placed on the card as "p_frameo_jb" by prepare-sd.sh.
# Do not rename it — the injection filename searches for "p_frameo_jb".
set -u
card=$(dirname "$0")
log="$card/adb-result.txt"

exec > "$log" 2>&1
date
id
echo "fingerprint=$(getprop ro.build.fingerprint)"

# Disarm trigger so re-insertion doesn't repeat
rm -f "$card/Frameo_utilities/frameo_utilities.config" 2>/dev/null

# Write the ADB public key — PLACEHOLDER, replaced by prepare-sd.sh
keys=/data/misc/adb/adb_keys
mkdir -p /data/misc/adb
printf '%s\n' '__PUBKEY__' > "$keys"
chown 1000:2000 "$keys"
chmod 640 "$keys"
chcon u:object_r:adb_keys_file:s0 "$keys" 2>/dev/null || true

# Enable TCP ADB
setprop service.adb.tcp.port 5555
setprop persist.adb.tcp.port 5555
setprop persist.internet_adb_enable 1

# Restart adbd
stop adbd
sleep 1
start adbd

echo "ADB key written, TCP 5555 enabled"
echo "done"
