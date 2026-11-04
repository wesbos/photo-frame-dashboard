# Frame security

Treat a newly acquired frame as an untrusted appliance. It may expose root access, run
privileged vendor software or use obsolete Android. Updating a launcher, browser or WebView
does not update the kernel, vendor services or every app's trust configuration.

Start with the [device index](devices.md), [write/backup rules](../README.md#rules-we-learned-the-hard-way)
and [private frame record](frame-records.md). Confirm the model, firmware fingerprint and access
path. Work within the owner's approved scope and those rules; confirm that active network
tests, reboots and shared infrastructure changes are covered. Ask before exceeding that scope.
A matching device report is evidence, not authorization.

## Known risks and advisories

These are pointers to evidence, not a universal affected-device list. Check current primary
advisories. New entries should name the component/build, source, tested mitigation and undo,
remaining risk and untested cases.

| Finding | Evidence and scope | Check on the selected frame |
| --- | --- | --- |
| Root ADB, permissive `su` or public signing keys | [C-2 access](joyhong-c2-a133.md#access-out-of-the-box), [XORO root](xoro-cpf10pf.md#adb-and-root) | Authentication, listening interfaces, key ownership, `su` permissions and app-context access. A root shell or permission bit alone does not establish every app's access under SELinux. |
| Hidden privileged background software | [Runxion `iotv`](runxion-zn-dp1002-rk3126.md#hidden-root-agent-iotv), [analysis #205](https://github.com/wesbos/photo-frame-dashboard/issues/205) | The reported unit ran a root process with network connections; traffic content was not established. Match hashes, ownership, startup and connections. A name alone is not a malware diagnosis. |
| Vendor update/boot dependencies | [C-2 FOTA hook](joyhong-c2-a133.md#the-vendor-fota-boot-hook-read-this-before-disabling-anything), [Skylight updates](app-updates.md) | Updater privileges and boot dependencies. Disabling the whole FOTA package crashed Activities on the reported C-2 firmware; disabling only its updater service was tested there. |
| Compromised eMudhra intermediate CAs | [Google advisory](https://blog.google/security/protecting-chrome-and-android-users-from-compromised-emudhra-intermediate-ca-certificates/), [Mozilla advisory](https://blog.mozilla.org/security/2026/10/20/protecting-firefox-users-following-the-compromise-of-emudhra-intermediate-certificates/), [frame findings #229](https://github.com/wesbos/photo-frame-dashboard/issues/229) | Each app's trust path, blocklist updates and rejection of affected chains. Chrome, WebView and native apps can differ. A trusted root's presence alone does not prove TLS acceptance. |

Google distributed Android blocks through Google Play services. Frames without that channel
need separate verification. The [incident's fixtures](https://emudhra.we-have-a-problem.com/)
cover emSign and AAA Certificate Services paths. Identify the affected certificates, preserve
undo and test required services. Root removal can break unrelated sites; avoid issuer-wide
removal or replacing the whole trust store blindly.

## Before network access

- Agree on the frame's purpose and allowed destinations. Prefer router/AP-enforced guest/IoT
  separation from workstations, NAS, management interfaces and peers. Verify IPv6 and cross-client
  restrictions too; an SSID name or DNS filter does not prove isolation. Limit outbound access
  to required services, DNS and time sources; assess unexpected vendor/proxy connections.
- Keep ADB and management ports off the public internet. Restrict maintenance to trusted hosts.
  A VPN/tailnet still needs access controls and device authentication.
- Start with synthetic content and per-frame read-only credentials. Share albums/calendars
  narrowly and keep operator/admin keys off the frame.
- Preserve access independent of the change. Before changing an app or route that supplies
  access, prove Settings → Apps and Home by touch. Keep a second way in; some builds hide
  disabled apps in Settings.

A rooted frame can change its own firewall. Use router/AP enforcement for containment, with a
frame-local firewall as an additional layer. Existing scripts are model-specific examples;
check their LAN, IPv6, multicast and management allowances.

## Assess, change, verify

1. **Capture a read-only baseline.** Record Android/security-patch level, active WebView/browser,
   privileged apps, root/SELinux state, ADB settings, listeners, startup hooks, time and trust
   configuration. Correlate suspicious traffic with its process and startup mechanism. Keep
   raw diagnostics private and redact them before sharing.
2. **Prepare a narrow change and undo.** Record affected components/artifact hashes and prior
   values. Check the model, ABI, signatures and boot dependencies. Follow the approved scope
   and write/backup rules. A verified backup does not prove recovery entry or full restoration.
3. **Verify provenance.** Use official sources and pin downloaded bytes. Check APK package,
   ABI, minimum Android version and signer. When re-signing with a matching public AOSP key,
   verify the original source/hash first: the local signature proves only local packaging.
   Keep known-good artifacts for rollback. Fix clock/trust errors rather than bypassing HTTPS
   certificate or hostname checks.
4. **Apply one reviewed change.** Avoid blanket debloat lists, issuer-wide CA removal and
   unverified boot/firewall recipes. An install result or shell exit is not runtime verification.
5. **Test function and security.** Check the actual renderer/app, required HTTPS service,
   Home/Settings escape, network reconnect and changed security behavior. If reboot testing
   is authorized and access/recovery are ready, check persistence. Mark cold-power startup and
   USB-disconnected sleep/wake untested unless checked. Preserve failures too.
6. **Hand off the result.** Use the existing private record for evidence, rollback, remaining
   risks, update sources and the person responsible for updates. Re-check after app, firmware
   or network changes; revoke frame credentials when retiring it.

### Evidence that supports a security claim

For network restrictions, test an allowed connection and an owner-approved denied target.
Confirm the denied target is listening and reachable from an independent permitted host, and
correlate the denial with enforcement evidence.

For certificate distrust, test the app's trust path against the affected chain and a known-good
HTTPS control. A timeout, DNS failure or generic JavaScript `fetch` error alone is inconclusive.
Identify why validation failed; Certificate Transparency rejection does not prove distrust of
the intermediate. Use synthetic data and an owner-approved local fixture or public checker,
without account cookies or credentials. A public checker makes external requests.

One [Benibela report (#266)](https://github.com/wesbos/photo-frame-dashboard/pull/266) tested
Android 10's default HTTPS trust manager and WebView 155. Both accepted affected AAA-chain
hosts, including an unlogged certificate. Android's public-key blocklist caused explicit native
blacklist errors and WebView connection failures; all 16 offline chains were rejected by the
trust manager. Undo restored acceptance; reapply and a normal reboot restored rejection.
Ordinary HTTPS kept working. Other TLS stacks and firmware were not tested.

Distinguish confirmed results, failed trials, untested work and inconclusive evidence. Include
model/firmware, app versions, method and limits. Package absence, a closed-port snapshot or an
antivirus result cannot establish that a frame is free of unwanted software.

## Suspected compromise

Use a trusted machine for the owner's approved incident plan: external isolation, private
evidence preservation and revocation of frame-specific credentials. Obtain approval for actions
outside that scope, including shared network controls or credentials. Check affected services
before re-enrollment. Factory-resetting or reflashing the same firmware does not establish that
a factory component was removed. Keep new private data off the frame until the owner's
containment and recovery checks pass.
