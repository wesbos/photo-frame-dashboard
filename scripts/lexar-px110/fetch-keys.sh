#!/bin/bash
# Fetch the published signing keys the Lexar Pexar PX-110 tools use, and refuse any file whose SHA-256 differs.
#
#   fetch-keys.sh              download the keys that are missing from KEY_DIR, then check every one
#   fetch-keys.sh --check      download nothing: check the files already in KEY_DIR
#   fetch-keys.sh --from DIR   take the files from DIR instead of the network (copies you got elsewhere,
#                              under the name below or the upstream name); the same hash check applies
#
# KEY_DIR comes from unit.conf or PX110_KEY_DIR; the default is keys/ beside this script, which git ignores.
#
# What these are: MediaTek's sample ("default") signing keys and the AOSP verified-boot test key. The frame's
# maker shipped firmware that trusts them. They are fetched from public GitHub repositories that happen to
# carry MediaTek's sample keys, pinned to one commit each. Those repositories are NOT an official source and
# may disappear; the SHA-256 below is what makes a copy from anywhere else safe to use (--from).
# Each file is downloaded to a temporary name, hashed, and only then moved into place. Nothing is run, and
# nothing is sent anywhere except the plain HTTPS requests for these files.
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
CONF=${PX110_CONF:-$HERE/unit.conf}
conf() {   # conf NAME [default]: environment PX110_NAME, else the line NAME=value in unit.conf, else the default
  local n="PX110_$1" v
  v=${!n:-}
  if [ -z "$v" ] && [ -f "$CONF" ]; then
    v=$(sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$CONF" | tail -1 | sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/")
  fi
  printf '%s' "${v:-${2:-}}"
}
KEYDIR=$(conf KEY_DIR keys)
case "$KEYDIR" in "~/"*) KEYDIR=$HOME/${KEYDIR#\~/} ;; /*) ;; *) KEYDIR=$HERE/$KEYDIR ;; esac

OWP=https://raw.githubusercontent.com/OpenWatchProject/android_device_mediatek/123c88624325d417ceb072f86b40d168fa478a7e/common
MLT=https://raw.githubusercontent.com/TheGammaSqueeze/mtk-lk-tools/1eff1b6051fd0312a43faa73f3e955a254de622d/keys

# name in KEY_DIR | where it is published | SHA-256 of the file | what it signs on this frame
KEYS="
testkey_rsa2048.pem|$OWP/oem_prvk.pem|f1d5765a2bdfb92fb08aee021107c7ac1a7a3f590dafd853771c85375ef0fbd7|vbmeta, vbmeta_system (the AOSP test key; build.py)
recovery_prvk.pem|$OWP/recovery_prvk.pem|1442098aea914fa8a312ca92e11bb574e8e802e92279eb422fc8d8aea56c4508|recovery (recbuild.py)
boot_prvk.pem|$OWP/boot_prvk.pem|4db337d4ce0368f6223491ee19c89fc3e1a240693c8bb1d5d9920fdb7fdb0b05|boot (bootbuild.py)
system_prvk.pem|$OWP/system_prvk.pem|886a0068187dd48e9c98aba6437eddf6476782e94d463567cf69a88a1fc1f3de|the stock vbmeta_system (not needed by the tools; certverify.py names it)
vendor_prvk.pem|$OWP/vendor_prvk.pem|ec626c0ddea749079f4297bfde33ad777b202d5ecf455b4c7808ecb934da1c24|the stock vbmeta_vendor (not needed by the tools)
root_prvk.pem|$MLT/root_prvk.pem|1a29171880f54e99cd29e32ed643fe8031480cef7146fba931b76b6dfab4ec4e|cert1 of logo (logosign.py)
img_prvk.pem|$MLT/img_prvk.pem|757e727ea1a52f6b66d101a3b0b003600df9ea0f4b9ef06646ce1958a21692a2|cert2 of logo (logosign.py)
"

MODE=fetch; FROM=""
case "${1:-}" in
  "") ;;
  --check) MODE=check ;;
  --from) MODE=from; FROM=${2:-}; [ -d "$FROM" ] || { echo "STOP: --from needs a folder"; exit 2; } ;;
  *) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac

sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
mkdir -p "$KEYDIR" || { echo "STOP: cannot make $KEYDIR"; exit 1; }
chmod 700 "$KEYDIR" 2>/dev/null
bad=0
echo "Keys folder: $KEYDIR"
while IFS='|' read -r name url want what; do
  [ -n "$name" ] || continue
  dest=$KEYDIR/$name
  if [ -e "$dest" ]; then
    got=$(sha "$dest")
    if [ "$got" = "$want" ]; then echo "ok       $name  (already there, hash matches)"
    else echo "REFUSED  $name: the file in KEY_DIR has sha256 $got, not the pinned $want. It is left as it is; move it away and run again."; bad=1; fi
    continue
  fi
  if [ "$MODE" = check ]; then echo "missing  $name"; bad=1; continue; fi
  tmp=$KEYDIR/.fetch.$$.$name
  rm -f "$tmp"
  if [ "$MODE" = from ]; then
    src=$FROM/$name; [ -f "$src" ] || src=$FROM/${url##*/}
    [ -f "$src" ] || { echo "missing  $name: not in $FROM (as $name or ${url##*/})"; bad=1; continue; }
    cp "$src" "$tmp" || { echo "FAILED   $name: could not copy"; bad=1; continue; }
  else
    curl --proto '=https' --tlsv1.2 -fsSL --max-time 60 -o "$tmp" "$url" ||
      { rm -f "$tmp"; echo "FAILED   $name: download failed ($url)"; bad=1; continue; }
  fi
  got=$(sha "$tmp")
  if [ "$got" != "$want" ]; then
    rm -f "$tmp"
    echo "REFUSED  $name: what arrived has sha256 $got, not the pinned $want. Nothing was kept."
    bad=1; continue
  fi
  chmod 600 "$tmp" && mv -n "$tmp" "$dest" && [ ! -e "$tmp" ] || { rm -f "$tmp"; echo "FAILED   $name: could not put it in place"; bad=1; continue; }
  echo "fetched  $name  sha256 $want  ($what)"
done <<EOF
$KEYS
EOF

if [ $bad = 0 ]; then echo "RESULT: all seven keys are in place and have their pinned hashes."
else echo "RESULT: NOT complete (see above). The tools refuse to sign with a key that is missing or different."; fi
exit $bad
