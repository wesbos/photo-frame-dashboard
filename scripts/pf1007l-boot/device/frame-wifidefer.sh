#!/system/bin/sh
# Wi-Fi and network setup after boot, from /data/local/frame-boot.conf.
# - WIFI_DEFER: when the AIC8800 powered up at ~30 s, in the busiest part of boot, the frame browned
#   out or froze on most boots. frame-boot-hook.sh bind-mounts an empty file over the driver so
#   Android's own load fails; this removes the mount after boot completes and starts Wi-Fi.
# - KIOSK: Android keeps the "Always" Home choice in package-restrictions.xml and drops it if a power
#   cut corrupts that file. If the Home chooser is showing, start the kiosk.
# - ADB_ALLOW: network ADB is root with no authentication; allow TCP 5555 only from that network.
# - IGNORE_IPV6_RA: drop IPv6 router advertisements, if they list a DNS server the frame can't reach.
# - DHCP rejoin: see below.
# /data/local/frame-nowifi keeps Wi-Fi off for debugging.
CONF=/data/local/frame-boot.conf
[ -r $CONF ] && . $CONF
t=0
until [ "$(getprop sys.boot_completed)" = 1 ] || [ $t -ge 120 ]; do
    sleep 1
    t=$((t + 1))
done
sleep 3

if [ -n "$KIOSK" ] && dumpsys window | grep mCurrentFocus | grep -q ResolverActivity; then
    am start -n "$KIOSK" > /dev/null
    log -t frame-wifidefer "Home chooser was showing (default Home app lost); started $KIOSK"
fi

if [ -n "$ADB_ALLOW" ]; then
    ADB_DROP="INPUT -p tcp --dport 5555 -j DROP"
    ADB_LAN="INPUT -p tcp --dport 5555 -s $ADB_ALLOW -j ACCEPT"
    iptables -C $ADB_DROP 2> /dev/null || iptables -I $ADB_DROP
    iptables -C $ADB_LAN 2> /dev/null || iptables -I $ADB_LAN
    ip6tables -C $ADB_DROP 2> /dev/null || ip6tables -I $ADB_DROP
fi
if [ "$IGNORE_IPV6_RA" = 1 ]; then
    RA="INPUT -i wlan0 -p icmpv6 --icmpv6-type router-advertisement -j DROP"
    ip6tables -C $RA 2> /dev/null || ip6tables -I $RA
fi

# FIREWALL: allow-list both ways. Out: DHCP, DNS to FIREWALL_DNS, NTP, and TCP to each
# FIREWALL_ALLOW host:port; everything else is refused, the rest of the LAN included, so the
# vendor app or any other app can't reach the internet even by a hard-coded IP. In: replies only
# (and ADB_ALLOW). netd flushes INPUT and OUTPUT when it starts, so this runs after boot_completed,
# before Wi-Fi starts, and a loop puts the rules back if they disappear (netd restart).
# /data/local/frame-nofirewall skips it (then reboot).
frame_firewall() {
    if [ -z "$FIREWALL_ALLOW" ] || [ -z "$FIREWALL_DNS" ]; then
        log -t frame-wifidefer "FIREWALL: FIREWALL_ALLOW and FIREWALL_DNS must both be set; firewall NOT applied"
        return 1
    fi
    if grep -qw state /proc/net/ip_tables_matches; then
        EST="-m state --state ESTABLISHED,RELATED"
    elif grep -qw conntrack /proc/net/ip_tables_matches; then
        EST="-m conntrack --ctstate ESTABLISHED,RELATED"
    else
        log -t frame-wifidefer "FIREWALL: no state or conntrack match in this kernel; firewall NOT applied"
        return 1
    fi
    REFUSE=DROP
    grep -qw REJECT /proc/net/ip_tables_targets && REFUSE=REJECT
    for T in iptables ip6tables; do
        $T -N FRAME_IN 2> /dev/null
        $T -N FRAME_OUT 2> /dev/null
        $T -F FRAME_IN
        $T -F FRAME_OUT
        $T -A FRAME_IN -i lo -j ACCEPT
        $T -A FRAME_OUT -o lo -j ACCEPT
        $T -A FRAME_IN $EST -j ACCEPT
        $T -A FRAME_OUT $EST -j ACCEPT
    done
    iptables -A FRAME_OUT -p udp --sport 68 --dport 67 -j ACCEPT
    iptables -A FRAME_IN -p udp --sport 67 --dport 68 -j ACCEPT
    for ip in $FIREWALL_DNS; do
        iptables -A FRAME_OUT -d "$ip" -p udp --dport 53 -j ACCEPT
        iptables -A FRAME_OUT -d "$ip" -p tcp --dport 53 -j ACCEPT
    done
    iptables -A FRAME_OUT -p udp --dport 123 -j ACCEPT
    for hp in $FIREWALL_ALLOW; do
        iptables -A FRAME_OUT -d "${hp%:*}" -p tcp --dport "${hp##*:}" -j ACCEPT
    done
    [ -n "$ADB_ALLOW" ] && iptables -A FRAME_IN -s "$ADB_ALLOW" -p tcp --dport 5555 -j ACCEPT
    ip6tables -A FRAME_IN -p icmpv6 -j ACCEPT
    ip6tables -A FRAME_OUT -p icmpv6 -j ACCEPT
    for T in iptables ip6tables; do
        $T -A FRAME_IN -j DROP
        $T -A FRAME_OUT -j $REFUSE 2> /dev/null || $T -A FRAME_OUT -j DROP
        $T -C INPUT -j FRAME_IN 2> /dev/null || $T -I INPUT -j FRAME_IN
        $T -C OUTPUT -j FRAME_OUT 2> /dev/null || $T -I OUTPUT -j FRAME_OUT
    done
}
if [ "$FIREWALL" = 1 ] && [ ! -e /data/local/frame-nofirewall ]; then
    if frame_firewall; then
        log -t frame-wifidefer "FIREWALL applied: out to $FIREWALL_ALLOW, DNS $FIREWALL_DNS, NTP, DHCP"
        while sleep 60; do
            [ -e /data/local/frame-nofirewall ] && break # undo without reboot: touch it, then delete the jumps
            iptables -C OUTPUT -j FRAME_OUT 2> /dev/null && ip6tables -C OUTPUT -j FRAME_OUT 2> /dev/null && continue
            frame_firewall && log -t frame-wifidefer "FIREWALL rules were gone (netd restart?); applied again"
        done &
    fi
fi

if [ -e /data/local/frame-nowifi ]; then
    log -t frame-wifidefer "frame-nowifi set; leaving Wi-Fi off"
    exit 0
fi
if [ "$WIFI_DEFER" = 1 ] && [ -n "$WIFI_DRIVER" ] && grep -q " $WIFI_DRIVER " /proc/mounts; then
    umount "$WIFI_DRIVER"
    svc wifi disable
    sleep 1
    svc wifi enable
    log -t frame-wifidefer "Wi-Fi started at uptime $(cut -d' ' -f1 /proc/uptime)s"
fi

# DHCP rejoin: on about 1 boot in 10 the access point sent a group-key update right after the
# 4-way handshake, and the driver then dropped broadcast frames, so the first DHCP offer never
# arrived (Android waits ~36 s for its DHCP timeout). A normal lease takes well under 1 s, so if
# associated without an address for 2 s, drop and rejoin (about 4 s; "wpa_cli reassociate" was
# slower because its first attempt failed). Gives up after 90 s.
W="wpa_cli -p /data/misc/wifi/sockets -i wlan0"
t=0
stuck=0
down=0
while [ $t -lt 90 ]; do
    ip -4 addr show wlan0 2> /dev/null | grep -q inet && exit 0
    case "$($W status 2> /dev/null)" in
    *wpa_state=COMPLETED*)
        stuck=$((stuck + 1))
        down=0
        ;;
    *)
        stuck=0
        down=$((down + 1))
        ;;
    esac
    if [ $stuck -ge 2 ]; then
        log -t frame-wifidefer "associated but no DHCP lease for 2 s; rejoining"
        $W disconnect > /dev/null
        sleep 0.3
        $W reconnect > /dev/null
        stuck=0
    fi
    if [ $down -ge 15 ]; then
        $W reconnect > /dev/null
        down=0
    fi
    sleep 1
    t=$((t + 1))
done
log -t frame-wifidefer "no IPv4 address 90 s after boot"
