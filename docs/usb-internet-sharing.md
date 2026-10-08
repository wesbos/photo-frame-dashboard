# Working internet access through the Mac

Verified on this unit2026-09-14. Gnirehtet2.5.1 provides reverse tethering through the existing ADB USB cable. The Android client installed successfully, its VPN tunnel connected, and a native HTTP probe running on the calendar received HTTP/1.1 204 No Content from connectivitycheck.gstatic.com through the Mac. This establishes actual external TCP/HTTP access, beyond a connected icon or USB enumeration. Built-in Wi-Fi is still faulty.

The [official project](https://github.com/Genymobile/gnirehtet) supports macOS and Android5+, without root. It forwards IPv4 TCP/UDP; ICMP ping and IPv6 are not suitable validation tests. The Java relay was used with an existing local OpenJDK. Homebrew installation encountered an unrelated untrusted-tap dependency check; no tap trust was changed. Instead the official Java release zip was downloaded and checked against the published SHA-256:

816748078fa6a304600a294a13338a06ac778bcc0e57b62d88328c7968ad2d3a

Source archive: https://github.com/Genymobile/gnirehtet/releases/download/v2.5.1/gnirehtet-java-v2.5.1.zip

Private tools are under diagnostics/tools/gnirehtet/gnirehtet-java. The Mac relay listens only on127.0.0.1:31416. Android routes through its gnirehtet VPN and an ADB reverse socket. No Mac Internet Sharing setting, root privilege, or firmware flash was needed. The app and small diagnostic probe are installed in ordinary writable Android storage.

## Use

The relay is currently running in the investigation session. Do not start a second relay on the same port.

For a future fresh session, from this repository:

```sh
scripts/share-internet.sh run
```

Leave that terminal running. Approve Android's VPN dialog if requested. Ctrl+C stops the relay/client. To disconnect the Android client while an existing relay remains running:

```sh
scripts/share-internet.sh stop
```

To reconnect after USB unplug/replug while the existing relay is still running:

```sh
scripts/share-internet.sh start
```

If the client is already active but its ADB reverse mapping was lost:

```sh
scripts/share-internet.sh tunnel
```

The calendar depends on the Mac's internet, the running relay, and the USB connection. This restores network access, not the physical Wi-Fi radio. Skylight requests a Wi-Fi-specific network in its onboarding code, so usable internet alone does not prove that onboarding accepts this route; that app behavior remains to be tested.

Raw relay traffic metadata, Android dumps and HTTP validation are kept in ignored diagnostics/. The first netcat probes closed without returning HTTP data; a separate native socket probe held the connection open and verified the204 response. Those empty netcat results were not treated as connectivity failure.
