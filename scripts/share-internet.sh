#!/bin/sh
# Run the locally verified gnirehtet release. No firmware/root changes.
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
relay_dir="$repo_dir/diagnostics/tools/gnirehtet/gnirehtet-java"
java_bin=/opt/homebrew/opt/openjdk/bin/java
if [ ! -f "$relay_dir/gnirehtet.jar" ] || [ ! -x "$java_bin" ]; then
  echo 'Local gnirehtet release or Java is missing; see docs/usb-internet-sharing.md.' >&2
  exit 1
fi
case "${1:-run}" in
  run|start|stop|tunnel) action=${1:-run} ;;
  *) echo 'Usage: scripts/share-internet.sh [run|start|stop|tunnel]' >&2; exit 2 ;;
esac
cd "$relay_dir"
exec "$java_bin" -jar gnirehtet.jar "$action"
