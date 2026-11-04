#!/bin/bash
# T3c on macOS without a DNS change: while the frame uses this Mac's Internet Sharing Wi-Fi, send
# its AiMOR command connection (TCP 7806) to server.py on this Mac instead of the vendor server.
# Usage: macos-redirect.sh on | status | off
set -euo pipefail
anchor=com.apple/aimor-t3c
bridge=${BRIDGE:-bridge100}

pf() { sudo pfctl "$@" 2>&1 | grep -v -e ALTQ -e 'could result in flushing' -e '/etc/pf.conf' -e '^present in the main' -e '^$' || true; }

address() {
  ipconfig getifaddr "$bridge" 2>/dev/null ||
    { echo "$bridge has no address: turn on Internet Sharing to Wi-Fi first" >&2; exit 1; }
}

case "${1:-}" in
  on)
    ip=$(address); net=${ip%.*}.0/24
    sudo pfctl -s info 2>/dev/null | grep -q 'Status: Enabled' ||
      { echo "pf is not enabled; Internet Sharing normally enables it" >&2; exit 1; }
    echo "rdr pass on $bridge inet proto tcp from $net to any port 7806 -> $ip port 7806" | pf -a "$anchor" -f -
    # A connection opened before the rule still goes to the vendor; cut it so AiMOR reconnects here.
    pf -k "$net"
    pf -a "$anchor" -s nat
    echo "Next: /usr/bin/python3 scripts/aimor-network-adb/server.py --bind $ip --frame-ip <frame-ip> --seconds 600"
    ;;
  status)
    pf -a "$anchor" -s nat
    echo "--- TCP 7806 connections:"; pf -s state | grep ':7806' || true
    echo "--- clients on $bridge:"; arp -an -i "$bridge" | grep -v -e '\.1)' -e '\.255)' -e '(224\.' || true
    ;;
  off)
    pf -a "$anchor" -F all
    ;;
  *)
    echo "usage: $0 on | status | off" >&2; exit 2
    ;;
esac
