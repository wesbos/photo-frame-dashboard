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

# Optional best-effort filtering. Boot/network-service timing can leave exposure windows;
# this is not a prerequisite for Wi-Fi, and a privileged app can replace these rules.
if [ "$FIREWALL" = 1 ] && [ ! -e /data/local/frame-nofirewall ]; then
    if [ -r /system/bin/frame-firewall.sh ]; then
        . /system/bin/frame-firewall.sh
        if frame_firewall; then
            frame_firewall_monitor &
        else
            log -t frame-wifidefer "FIREWALL not applied; Wi-Fi startup continues, use router isolation"
        fi
    else
        log -t frame-wifidefer "FIREWALL helper missing; no protection applied"
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
