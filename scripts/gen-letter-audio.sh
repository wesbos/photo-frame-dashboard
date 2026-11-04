#!/bin/sh
# Generates the 26 French phonetic letter-sound clips used by homework.js's "letters" mode
# (Clara's slider-scrubbing phonics homework review) — public/audio/fr-letters/<letter>.mp3.
#
# These are PHONETIC sounds, not alphabet names: "beu" for B (not "bé"), "keu" for C (not
# "cé"), matching the French "méthode syllabique" taught in school for sounding out words
# letter by letter. Safe to re-run; overwrites existing clips.
set -e

OUT_DIR="$(cd "$(dirname "$0")/.." && pwd)/dashboard/public/audio/fr-letters"
mkdir -p "$OUT_DIR"

gen() {
  letter="$1"
  sound="$2"
  tmpaiff="$(mktemp -t "letter_$letter").aiff"
  say -v Amélie -r 130 -o "$tmpaiff" "$sound"
  ffmpeg -y -loglevel error -i "$tmpaiff" "$OUT_DIR/$letter.mp3"
  rm -f "$tmpaiff"
  echo "wrote $OUT_DIR/$letter.mp3 (\"$sound\")"
}

gen a a
gen b beu
gen c keu
gen d deu
gen e eu
gen f feu
gen g gueu
gen h heu
gen i i
gen j jeu
gen k keu
gen l leu
gen m meu
gen n neu
gen o o
gen p peu
gen q keu
gen r reu
gen s seu
gen t teu
gen u u
gen v veu
gen w oueu
gen x kseu
gen y "i grec"
gen z zeu
