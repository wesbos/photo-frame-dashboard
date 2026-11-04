# PF1007L / January 20260113: full dashboard setup notes (macOS) — operational gotchas

One PF1007L on `YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113` (Allwinner A33,
Android 6.0.1, larger 30,777,344-sector eMMC), set up from an Apple-silicon Mac. ADB was reached
through the microSD `license.properties` factory-menu route, which is already documented in
[pf1007l-20260113-marker-file-report.md](pf1007l-20260113-marker-file-report.md) and reproduced
here without changes — this report does **not** re-document that route or the backup procedure.

It records a few operational gotchas met while doing the full post-root setup (verified partition
backup → WebView 44→106 swap → Let's Encrypt CA roots → kiosk as Home → vendor-app disable →
live weather). Observations are kept separate from guesses, as the repo asks.

## 1. Live weather via Open-Meteo needs the Let's Encrypt roots

To show real weather in the dashboard, the bundled page fetched `https://api.open-meteo.com`.
Open-Meteo's certificate chains to **ISRG Root X1 / X2 (Let's Encrypt)**, which Android 6's 2015
trust store does not contain, so WebView 106 rejected the request with
`net_error -202` (`ERR_CERT_AUTHORITY_INVALID`) and the kiosk's `onReceivedSslError` logged
`Certificate error 3 on a subresource; blocked`.

Adding `6187b673.0` (ISRG Root X1) and `8794b4e3.0` (ISRG Root X2) to
`/system/etc/security/cacerts/` (the same roots the BIUFRAME guide installs) fixed it. This is a
concrete second use case for those roots beyond external images: **any Open-Meteo / Let's Encrypt
API needs them on these Android 6 frames.**

- `openssl verify` of the served `api.open-meteo.com` chain against those two roots passes on the host.
- The cert files use the usual Android format: PEM body + `openssl x509 -text` dump, filename from
  `openssl x509 -subject_hash_old`, mode `0644`, owner `root:root`.

**Gotcha — the new roots were not honored by a running WebView.** After copying the roots in,
restarting the kiosk with `am force-stop` + relaunch still produced `-202`. The roots were only
honored after a full power cycle **and** a genuinely fresh app process (an `adb install -r`, which
kills the process). We could **not** isolate whether the power cycle itself was required or whether
a truly fresh WebView process alone would have sufficed, because `am force-stop` did not reliably
produce a fresh process on this unit (see §3). Either way: if external HTTPS still fails right after
adding roots, power-cycle the frame before concluding the certs are wrong.

## 2. Firefox and the WebView-106 kiosk cannot both run on a 1 GB frame

With Firefox 143 left running from earlier testing (~380 MB across its processes on this 1 GB unit,
`MemTotal` ≈ 1,026,980 kB) and the kiosk then launched, loading WebView 106's ~64 MB
`libwebviewchromium.so` pushed the device into a hard low-memory state: load average ~32, the kiosk
process stuck in uninterruptible sleep (`D` state), and `am force-stop` / `logcat` themselves could
not complete. A software reboot could not recover it (see §3); a physical power cycle did.

With Firefox closed/uninstalled, the same kiosk ran fine (~400–530 MB free, load ~1). Suggestion:
**close or `pm uninstall org.mozilla.firefox` before running the WebView-106 kiosk on 1 GB units**,
and keep it only as a fallback that is not left running.

## 3. Software reboot appeared to be ignored on this unit

Both `adb reboot` and `adb shell su 0 setprop sys.powerctl reboot` left the device running —
`/proc/uptime` kept climbing across both, and the kiosk/launcher state did not reset. Only unplugging
and replugging USB power (the frame has no battery) rebooted it, confirmed by a reset `uptime`.

This **contradicts** the second-unit report in
[pf1007l-20260113-marker-file-report.md](pf1007l-20260113-marker-file-report.md), where `adb reboot`
worked (root USB ADB back in ~25 s). So this is a per-unit or per-state difference, **cause not
established** — one confound is that the `adb reboot` call was killed by the host after ~8 s, though
the fire-and-forget `setprop sys.powerctl reboot` also did not take. Practical takeaway: to apply a
`/system` change or new CA roots on this firmware, be ready to **physically power-cycle**.

## 4. Setting the kiosk as Home, then removing other home apps, reset the default

Home HQ was made the default Home app (Android 6 route: `--ez home true`, then the chooser, then
**Always**). Later disabling AiMOR (`pm disable com.efercro.os.aimor`) and uninstalling Firefox
changed the set of Home candidates, which **reset the preferred-Home preference** and brought the
chooser back on the next Home event. Re-selecting Home HQ + Always after the vendor cleanup made it
stick. Suggestion: **set the kiosk as Home *after* disabling/removing other launchers and the vendor
app**, or re-confirm it afterward.

## Minor notes

- `toybox` on this build lacks `sha256sum` and `head -c`; `/sbin/busybox sha256sum` works for
  on-device hashing.
- `adb`, `dumpsys package`, and `logcat -d` are all slow on this A33 and frequently take tens of
  seconds; bounding each call helps when scripting.

## Tested on

One unit, macOS (Apple silicon), 2026-11-03. Firmware
`YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113`, AiMOR 6.0.78, eMMC 30,777,344 sectors,
boot template-range SHA-256 `d71c313d…` (matches the published January stock). No serial, MAC,
Frame ID, Wi-Fi details or dumps are included.
