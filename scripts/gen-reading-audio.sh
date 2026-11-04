#!/bin/sh
# Generate one French reading-practice audio clip via macOS `say`, for the kid views' reading
# practice (js/reading.js). Usage: gen-reading-audio.sh "<word>" <slug>
#
# Watch for accent-slug collisions: a naive slugify of accented words can collide (e.g.
# "là"/"la", "où"/"ou", "sûr"/"sur" — the accent is lost in the slug). Check the CLIPS map in
# js/reading.js for an existing entry with that slug before generating; append "-v2" to
# disambiguate if a collision is unavoidable.
set -e

WORD="$1"
SLUG="$2"
if [ -z "$WORD" ] || [ -z "$SLUG" ]; then
  echo "usage: $0 \"<word>\" <slug>" >&2
  exit 1
fi

OUT_DIR="$(cd "$(dirname "$0")/.." && pwd)/dashboard/public/audio/fr"
mkdir -p "$OUT_DIR"

TMP_AIFF="$(mktemp -t gen-reading-audio).aiff"
say -v Amélie -r 150 -o "$TMP_AIFF" "$WORD"
ffmpeg -y -loglevel error -i "$TMP_AIFF" "$OUT_DIR/$SLUG.mp3"
rm -f "$TMP_AIFF"

echo "wrote $OUT_DIR/$SLUG.mp3"
