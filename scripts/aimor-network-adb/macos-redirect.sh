#!/bin/bash
# Redirect only the selected frame's AiMOR connection on macOS Internet Sharing.
# Usage: BRIDGE=bridge100 macos-redirect.sh on <frame-ip> | status | off
set -euo pipefail
anchor=com.apple/aimor-t3c
bridge=${BRIDGE:-bridge100}

fail() { echo "ERROR: $*" >&2; exit 1; }
# Keep pfctl's output and exit status, including authentication and cleanup errors.
pf() { sudo pfctl "$@"; }

[[ "$bridge" =~ ^bridge[0-9]+$ ]] || fail 'BRIDGE must be an Internet Sharing bridge, such as bridge100'

address() {
  local info addresses count
  info=$(ifconfig "$bridge") || fail "cannot read $bridge"
  addresses=$(printf '%s\n' "$info" | awk '$1 == "inet" {print $2 " " $4}')
  count=$(printf '%s\n' "$addresses" | awk 'NF {n++} END {print n+0}')
  [ "$count" = 1 ] || fail "$bridge must have exactly one IPv4 address; select the sharing bridge explicitly"
  # ifconfig works on sharing bridges where ipconfig getifaddr returns nothing (#254).
  read -r ip mask <<< "$addresses"
}

validate_peer() {
  # Parse addresses as data, never as shell arithmetic or a pf rule. Python 3 is also
  # required by the T3c listener. The selected frame must be on this bridge's subnet.
  python3 - "$ip" "$mask" "$frame" <<'PY'
import ipaddress
import sys
try:
    host = ipaddress.IPv4Address(sys.argv[1])
    raw_mask = sys.argv[2]
    if not raw_mask.startswith('0x') or len(raw_mask) != 10:
        raise ValueError('unexpected ifconfig netmask')
    mask = ipaddress.IPv4Address(int(raw_mask, 16))
    net = ipaddress.IPv4Network(f'{host}/{mask}', strict=False)
    peer = ipaddress.IPv4Address(sys.argv[3])
    for address in (host, peer):
        if address.is_loopback or address.is_multicast or address.is_unspecified or address.is_reserved:
            raise ValueError('expected a unicast interface address')
    if peer == host or peer not in net or peer in (net.network_address, net.broadcast_address):
        raise ValueError('frame must be a different host on the selected bridge subnet')
except (ValueError, IndexError) as error:
    sys.exit(f'Invalid frame/bridge address: {error}')
PY
}

case "${1:-}" in
  on)
    [ "$#" = 2 ] || fail 'usage: macos-redirect.sh on <frame-ip>'
    frame=$2
    address
    validate_peer
    info=$(pf -s info) || fail 'cannot read pf status'
    printf '%s\n' "$info" | grep -q 'Status: Enabled' || fail 'pf is not enabled; turn on Internet Sharing first'
    root_rules=$(pf -s nat) || fail 'cannot inspect root redirect anchors'
    printf '%s\n' "$root_rules" | grep -Fq 'rdr-anchor "com.apple/*"' || fail 'the com.apple/* redirect anchor is absent; do not replace the system ruleset'
    existing=$(pf -a "$anchor" -s nat) || fail 'cannot inspect the dedicated anchor'
    [ -z "$existing" ] || fail "$anchor already contains rules; inspect with status and explicitly run off before replacing them"
    rule="rdr pass on $bridge inet proto tcp from $frame to any port 7806 -> $ip port 7806"
    printf '%s\n' "$rule" | pf -n -a "$anchor" -f - || fail 'pf rejected the rule; nothing installed'
    if ! printf '%s\n' "$rule" | pf -a "$anchor" -f -; then
      pf -a "$anchor" -F nat || echo "Cleanup failed; inspect $anchor manually" >&2
      fail 'redirect installation failed'
    fi
    # Only this frame's states are removed (all its connections, not only TCP 7806).
    # Other Internet Sharing clients are unaffected.
    if ! pf -k "$frame" || ! pf -a "$anchor" -s nat; then
      pf -a "$anchor" -F nat || echo "Cleanup failed; inspect $anchor manually" >&2
      fail 'state reset or verification failed; cleanup attempted'
    fi
    echo "Redirect active for $frame only. Its existing connections were reset."
    echo "Next: python3 scripts/aimor-network-adb/server.py --bind $ip --frame-ip $frame --seconds 600"
    echo 'After the session: scripts/aimor-network-adb/macos-redirect.sh off'
    ;;
  status)
    [ "$#" = 1 ] || fail 'usage: macos-redirect.sh status'
    pf -a "$anchor" -s nat
    echo "Clients on $bridge (verify the frame's address before on):"
    arp -an -i "$bridge"
    ;;
  off)
    [ "$#" = 1 ] || fail 'usage: macos-redirect.sh off'
    pf -a "$anchor" -F nat
    remaining=$(pf -a "$anchor" -s nat) || fail 'cannot verify cleanup'
    [ -z "$remaining" ] || fail 'redirect rules remain after cleanup'
    echo "Removed redirect rules from $anchor only."
    ;;
  *) fail 'usage: macos-redirect.sh on <frame-ip> | status | off' ;;
esac
