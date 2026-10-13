#!/system/bin/sh
# Brings up the Home HQ wall dashboard. Runs as root, detached, so the vendor's
# BackgroundManagerService (which refuses non-whitelisted background services) is not
# involved. Absolute paths throughout: su's PATH starts with /sbin, whose stripped
# busybox has no httpd applet.
BB=/system/bin/busybox
ROOT=/data/local/tmp/homehq
LOG=/data/local/tmp/homehq-start.log

log() { echo "$(/system/bin/date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; chmod 666 "$LOG" 2>/dev/null; }

# At boot, give Wi-Fi, the window manager and the launcher time to settle.
[ "$1" = "--now" ] || $BB sleep 20

if $BB ps -o args 2>/dev/null | $BB grep -q "[h]ttpd -p 8080"; then
  log "httpd already running"
else
  $BB httpd -p 8080 -h "$ROOT" -c "$ROOT/httpd.conf" && log "httpd started" || log "httpd FAILED"
fi

$BB sleep 2
/system/bin/am start -a android.intent.action.VIEW \
  -d http://localhost:8080 org.mozilla.firefox >/dev/null 2>&1 && log "browser started" || log "browser FAILED"

# Firefox cold start plus first paint runs ~25s here; the tap lands on the dashboard's
# full-screen gate, which exists so this cannot hit a card and open something.
$BB sleep 35
/system/bin/input tap 640 400 && log "fullscreen tap sent" || log "tap FAILED"
log "done"
