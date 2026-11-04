#!/system/bin/sh
# Sourced by frame-wifidefer.sh. Optional best-effort filtering, not a root security boundary.
# New chains are built off-path. Failed activation removes only our new hooks; old rules stay.
# Cleanup checks that a chain is unreferenced before flushing. IPv6 is blocked except loopback.
FIREWALL_ALLOW=${FIREWALL_ALLOW:-}
FIREWALL_DNS=${FIREWALL_DNS:-}
ADB_ALLOW=${ADB_ALLOW:-}
FW_SEQ=0
FW_IN4= FW_OUT4= FW_IN6= FW_OUT6=
FW_EXPECT_IN4= FW_EXPECT_OUT4= FW_EXPECT_IN6= FW_EXPECT_OUT6=

fw_log() { log -t frame-wifidefer "FIREWALL: $*"; }
fw_ipv4() {
    local value=$1 octet
    case "$value" in ''|*[!0-9.]*) return 1 ;; esac
    local IFS=.
    set -- $value
    [ "$#" = 4 ] && [ "$value" = "$1.$2.$3.$4" ] || return 1
    for octet in "$@"; do
        case "$octet" in ''|0[0-9]*|????*) return 1 ;; esac
        [ "$octet" -le 255 ] || return 1
    done
}
fw_network() {
    local value=$1 bits
    case "$value" in
        */*) bits=${value#*/}; fw_ipv4 "${value%/*}" || return 1
            case "$bits" in ''|*[!0-9]*|0[0-9]*|???*) return 1 ;; esac
            [ "$bits" -le 32 ] ;;
        *) fw_ipv4 "$value" ;;
    esac
}
fw_config() {
    local entry port count=0
    # Restrict characters before word splitting so wildcard/hostname input cannot expand or resolve.
    case "$FIREWALL_ALLOW" in ''|*[!0-9.:\ ]*) return 1 ;; esac
    case "$FIREWALL_DNS" in ''|*[!0-9.\ ]*) return 1 ;; esac
    for entry in $FIREWALL_ALLOW; do
        fw_ipv4 "${entry%:*}" || return 1
        port=${entry##*:}
        case "$port" in ''|*[!0-9]*|0*|??????*) return 1 ;; esac
        [ "$port" -ge 1 ] && [ "$port" -le 65535 ] || return 1
        count=$((count + 1))
    done
    [ "$count" -gt 0 ] || return 1
    count=0
    for entry in $FIREWALL_DNS; do fw_ipv4 "$entry" || return 1; count=$((count + 1)); done
    [ "$count" -gt 0 ] || return 1
    [ -z "$ADB_ALLOW" ] || fw_network "$ADB_ALLOW"
}
fw_add() {
    local tool=$1 chain=$2
    shift 2
    "$tool" -A "$chain" "$@" && "$tool" -C "$chain" "$@"
}
fw_build4() {
    local input=$1 output=$2 entry
    fw_add iptables "$input" -i lo -j ACCEPT &&
    fw_add iptables "$output" -o lo -j ACCEPT || return 1
    # Put the ADB decision ahead of conntrack, including sessions established before these rules.
    if [ -n "$ADB_ALLOW" ]; then
        fw_add iptables "$input" -s "$ADB_ALLOW" -p tcp --dport 5555 -j ACCEPT &&
        fw_add iptables "$output" -d "$ADB_ALLOW" -p tcp --sport 5555 -m state --state ESTABLISHED -j ACCEPT || return 1
    fi
    fw_add iptables "$input" -p tcp --dport 5555 -j DROP &&
    fw_add iptables "$input" -p udp --sport 67 --dport 68 -j ACCEPT &&
    fw_add iptables "$input" -m state --state ESTABLISHED,RELATED -j ACCEPT &&
    fw_add iptables "$output" -p udp --sport 68 --dport 67 -j ACCEPT || return 1
    for entry in $FIREWALL_DNS; do
        fw_add iptables "$output" -d "$entry" -p udp --dport 53 -j ACCEPT &&
        fw_add iptables "$output" -d "$entry" -p tcp --dport 53 -j ACCEPT || return 1
    done
    fw_add iptables "$output" -p udp --dport 123 -j ACCEPT || return 1
    for entry in $FIREWALL_ALLOW; do
        fw_add iptables "$output" -d "${entry%:*}" -p tcp --dport "${entry##*:}" -j ACCEPT || return 1
    done
    # No general outbound ESTABLISHED rule: pre-existing connections to disallowed hosts stop too.
    fw_add iptables "$input" -j DROP && fw_add iptables "$output" -j DROP
}
fw_build6() {
    local input=$1 output=$2
    fw_add ip6tables "$input" -i lo -j ACCEPT &&
    fw_add ip6tables "$output" -o lo -j ACCEPT &&
    fw_add ip6tables "$input" -j DROP &&
    fw_add ip6tables "$output" -j DROP
}
fw_first_hook() {
    local tool=$1 builtin=$2 chain=$3 rules line
    rules=$("$tool" -S "$builtin") || return 1
    while IFS= read -r line; do
        case "$line" in -A\ *) [ "$line" = "-A $builtin -j $chain" ]; return ;; esac
    done <<END_RULES
$rules
END_RULES
    return 1
}
fw_check_chain() {
    local tool=$1 builtin=$2 chain=$3 expected=$4 actual
    [ -n "$chain" ] || return 1
    fw_first_hook "$tool" "$builtin" "$chain" || return 1
    actual=$("$tool" -S "$chain") || return 1
    [ "$actual" = "$expected" ]
}
frame_firewall_healthy() {
    fw_check_chain iptables INPUT "$FW_IN4" "$FW_EXPECT_IN4" &&
    fw_check_chain iptables OUTPUT "$FW_OUT4" "$FW_EXPECT_OUT4" &&
    fw_check_chain ip6tables INPUT "$FW_IN6" "$FW_EXPECT_IN6" &&
    fw_check_chain ip6tables OUTPUT "$FW_OUT6" "$FW_EXPECT_OUT6"
}
fw_remove_hook() {
    local tool=$1 builtin=$2 chain=$3 rules line found=0
    rules=$("$tool" -S "$builtin") || return 1
    while IFS= read -r line; do
        [ "$line" = "-A $builtin -j $chain" ] && found=$((found + 1))
    done <<END_RULES
$rules
END_RULES
    # We insert one hook per chain. Refuse unexpected duplicates rather than an unbounded deletion.
    [ "$found" -le 1 ] || return 1
    [ "$found" = 0 ] || "$tool" -D "$builtin" -j "$chain"
}
fw_delete_unused() {
    local tool=$1 chain=$2 rules
    [ -n "$chain" ] || return 0
    rules=$("$tool" -S) || return 1
    # Refuse to flush if any reference remains, including ones created by other processes.
    # This check and the flush are separate operations; privileged concurrent changes can race.
    case "$rules" in *" -j $chain"*|*" -g $chain"*) return 1 ;; esac
    "$tool" -F "$chain" && "$tool" -X "$chain"
}
fw_cleanup() {
    local tool=$1 input=$2 output=$3 failed=0
    if [ -n "$input" ]; then
        fw_remove_hook "$tool" INPUT "$input" || failed=1
        fw_delete_unused "$tool" "$input" || failed=1
    fi
    if [ -n "$output" ]; then
        fw_remove_hook "$tool" OUTPUT "$output" || failed=1
        fw_delete_unused "$tool" "$output" || failed=1
    fi
    return "$failed"
}
frame_firewall() {
    local in4= out4= in6= out6= candidate previous4in previous4out previous6in previous6out
    local expect4in expect4out expect6in expect6out after4in after4out after6in after6out failed=0
    fw_config || { fw_log 'invalid configuration; need literal IPv4 hosts/ports and DNS addresses'; return 1; }
    # Listing both families is mandatory. A missing IPv6 binary/table is not assumed to mean IPv6 is off.
    previous4in=$(iptables -S INPUT) && previous4out=$(iptables -S OUTPUT) &&
    previous6in=$(ip6tables -S INPUT) && previous6out=$(ip6tables -S OUTPUT) || {
        fw_log 'cannot inspect both IPv4 and IPv6; previous rules unchanged'; return 1;
    }
    FW_SEQ=$((FW_SEQ + 1))
    candidate="FWF_$$_$FW_SEQ"
    # Record ownership only after -N succeeds; never delete a pre-existing colliding chain.
    if iptables -N "${candidate}I"; then in4="${candidate}I"; else failed=1; fi
    if [ "$failed" = 0 ]; then
        if iptables -N "${candidate}O"; then out4="${candidate}O"; else failed=1; fi
    fi
    if [ "$failed" = 0 ]; then
        if ip6tables -N "${candidate}I"; then in6="${candidate}I"; else failed=1; fi
    fi
    if [ "$failed" = 0 ]; then
        if ip6tables -N "${candidate}O"; then out6="${candidate}O"; else failed=1; fi
    fi
    if [ "$failed" = 0 ]; then
        fw_build4 "$in4" "$out4" && fw_build6 "$in6" "$out6" &&
        expect4in=$(iptables -S "$in4") && expect4out=$(iptables -S "$out4") &&
        expect6in=$(ip6tables -S "$in6") && expect6out=$(ip6tables -S "$out6") || failed=1
    fi
    if [ "$failed" = 0 ]; then
        iptables -I INPUT 1 -j "$in4" && iptables -I OUTPUT 1 -j "$out4" &&
        ip6tables -I INPUT 1 -j "$in6" && ip6tables -I OUTPUT 1 -j "$out6" &&
        fw_check_chain iptables INPUT "$in4" "$expect4in" &&
        fw_check_chain iptables OUTPUT "$out4" "$expect4out" &&
        fw_check_chain ip6tables INPUT "$in6" "$expect6in" &&
        fw_check_chain ip6tables OUTPUT "$out6" "$expect6out" || failed=1
    fi
    if [ "$failed" != 0 ]; then
        fw_cleanup iptables "$in4" "$out4" || fw_log 'IPv4 rollback incomplete; use USB ADB and reboot'
        fw_cleanup ip6tables "$in6" "$out6" || fw_log 'IPv6 rollback incomplete; use USB ADB and reboot'
        if ! { after4in=$(iptables -S INPUT) && after4out=$(iptables -S OUTPUT) &&
               after6in=$(ip6tables -S INPUT) && after6out=$(ip6tables -S OUTPUT) &&
               [ "$after4in" = "$previous4in" ] && [ "$after4out" = "$previous4out" ] &&
               [ "$after6in" = "$previous6in" ] && [ "$after6out" = "$previous6out" ]; }; then
            fw_log 'rules changed during rollback; network protection is unverified, use USB ADB'
        fi
        fw_log 'installation failed; no protection claim; previous chains were not flushed'
        return 1
    fi
    # New rules are verified before old hooks are removed. Cleanup failure leaves stricter new
    # chains first; report stale objects without throwing away the successfully installed policy.
    fw_cleanup iptables "$FW_IN4" "$FW_OUT4" || fw_log 'old IPv4 cleanup incomplete; new rules remain first'
    fw_cleanup ip6tables "$FW_IN6" "$FW_OUT6" || fw_log 'old IPv6 cleanup incomplete; new rules remain first'
    FW_IN4=$in4 FW_OUT4=$out4 FW_IN6=$in6 FW_OUT6=$out6
    FW_EXPECT_IN4=$expect4in FW_EXPECT_OUT4=$expect4out FW_EXPECT_IN6=$expect6in FW_EXPECT_OUT6=$expect6out
    frame_firewall_healthy || { fw_log 'rules changed during activation; protection unverified'; return 1; }
    fw_log 'applied: configured IPv4 TCP/DNS, DHCP/NTP; all non-loopback IPv6 blocked'
    return 0
}
frame_firewall_monitor() {
    while sleep 60; do
        [ -e /data/local/frame-nofirewall ] && return
        if ! frame_firewall_healthy; then
            fw_log 'rules missing, changed or bypassed; attempting repair (traffic may have passed)'
            frame_firewall || fw_log 'repair failed; use USB ADB or router isolation'
        fi
    done
}
