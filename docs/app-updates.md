# Factory application update behavior

Offline review of the verified factory Skylight APK, version 9.29.3 (9325). No backend requests or device changes were made for this analysis. **Providing usable network access during onboarding can automatically trigger Skylight and watchdog APK updates before activation.** Merely opening native settings or leaving the Wi-Fi screen does not itself establish internet access or guarantee an update. An Android firmware/OS update is a separate question, not established by the reviewed app code.

## Confirmed activation flow

`ActivationViewModel.v2()` checks `WifiFacade.isConnectedToNetwork()`. If disconnected, it returns to Wi-Fi. If connected and the persisted `HAS_CHECKED_FOR_UPDATES` flag is false, it invokes `ActivationRepo.statusReportAndInstallApks()` and displays update progress before moving onward to code entry. If already checked, it moves onward directly. This update check is not gated on having successfully activated the calendar.

The connection predicate accepts the app's checking-internet, has-internet, and no-internet connected states. Thus it may attempt the check as soon as it regards a network as connected; successful downloads still require reaching the server. The activation view model catches a failed update-check operation and proceeds to the next screen.

The repository sets the checked flag **before** making the status request. It reports the current app version, OS build, manufacturer and device identification/signing information. The response model contains separate next-application and next-watchdog metadata, including APK download locations and hashes. The implementation downloads supplied APKs into app-private files, passes their hashes to its file-writing helper, and invokes `PackageManager.installApk()`. No separate user approval dialog is requested by this reviewed application flow.

The package installer uses Android `PackageInstaller` sessions, writes the APK contents and commits the session. This is package installation, not an Android system-partition updater. Its immediate success return means the session was submitted without an exception; it does not await final installation success. The APK manifest declares `INSTALL_PACKAGES` and `REQUEST_INSTALL_PACKAGES`, consistent with its privileged installation role.

The persisted flag is not a general promise that no future update can occur: the separate watchdog component exists, and its full autonomous behavior has not been analyzed here. The main APK's `WatchdogRepo.reportStatus()` can request a watchdog status report; for watchdog versions below 9 it instead resets that service. Backend rollout decisions and currently offered versions remain unknown.

## Android OTA limits

A bounded scan of this APK's decompiled sources found no main-app calls to `RecoverySystem` or `UpdateEngine`, no `update.zip`/`payload.bin` installer, and no Rockchip updater invocation. The reviewed status-response schema describes APK updates, not an OS OTA payload. Showing an OS version in settings or reporting it to the server does not by itself implement firmware updating.

The extracted vendor init files likewise did not reveal a scheduled OTA-download action in the reviewed paths. Recovery contains OTA certificate infrastructure, but having recovery-update support does not establish an automatic update policy. Other system packages, a separately installed watchdog, or future APK versions could implement additional behavior. Therefore the evidence supports **automatic app/watchdog APK updates during connected onboarding**, while **automatic Android firmware updates remain unverified**. Do not describe network access as guaranteed to repair or replace the Wi-Fi firmware.

## Local evidence and confidence

Paths below are relative to ignored `diagnostics/app-analysis/`:

- `sources/Ub/m.java`: activation navigation gate, update invocation, progress/error handling.
- `sources/odesk/johnlife/skylight/data/wifi/WifiFacade.java` and `sources/qd/AbstractC3909a.java`: connected-state predicate and state names.
- `sources/J9/C3096a.java`: activation repository, checked flag and method identity.
- `activation-repo-bad.java`: focused JADX output with `--show-bad-code`; confirms status/download/install calls and initial flag assignment. Coroutine reconstruction contains malformed branches, so exact download/null/error control flow should not be treated as fully reconstructed source.
- `sources/com/skylight/source/network/features/activation/models/StatusReportResponse.java`: separate application/watchdog update metadata.
- `sources/Yd/C4719a.java`: PackageInstaller implementation.
- `sources/odesk/johnlife/skylight/data/startup/WatchdogRepo.java`: watchdog status-request behavior.
- `resources/AndroidManifest.xml`: installation permissions.

High confidence: pre-activation automatic APK-check invocation, package-install mechanism, and distinction from OS OTA. Moderate confidence: detailed coroutine download branching because decompilation is incomplete. Unknown: current backend policy, watchdog autonomy, other updater packages, and whether a specific available update would alter Wi-Fi behavior. Embedded endpoints, identifiers and constants are intentionally not reproduced here.

## Can an official APK be fetched separately?

The reviewed app-update metadata route is **form-encoded `POST status_reports`**, relative to the configured environment API base, with fields `application_version_code`, `os_build_version`, `manufacturer`, `serial_number`, and `apk_signing_key_md5`. The response can supply `meta.next_application_version.apk_url` and `md5_hash`, separately from equivalent watchdog metadata. Downloading the returned APK uses streaming HTTP GET at that dynamic URL.

This metadata request is not a read-only GET. It is separate from the explicit activation operation (`POST frames/bind` with an activation code), but the client alone cannot establish all server-side reporting or registration effects. The authentication interceptor adds HTTP Basic credentials only when its stored username/password providers are nonblank and the target domain matches; otherwise it sends the request without that header. This allows the client to attempt its pre-activation request, but does not prove which requests the server currently accepts.

A legacy `GET watchdog_apk?versionCode=…` route exists for watchdog metadata. No corresponding standalone GET for Skylight application metadata, and no static public official display-APK download link, was found in this local review. The dynamically returned application URL is a potential official download source, but obtaining it would require a separately authorized status-report request or an already available official URL. No such request was made here. Before a manually obtained APK is installed, its package identity, signing certificate and version should be compared with the verified stock APK; a matching filename or supplied MD5 alone does not establish signing compatibility. This is a possible package-update path, not evidence it fixes the Wi-Fi driver.

Additional local references: `ActivationApi.java`, `ActivationNetworkSourceImpl.java`, `StatusReportResponse` serializer classes under `sources/com/skylight/source/network/features/activation/`; `sources/com/skylight/source/network/interceptors/AuthenticationInterceptor.java`; `sources/com/skylight/source/network/legacy/apis/StartUpService.java`.

## Live official update check (2026-09-14)

After the owner confirmed successful activation of Skylight USB Test and requested a newer version, a single status-report POST was sent to the reviewed official endpoint using the installed original app version/signing certificate and actual device metadata. No account credentials were accessed or sent. The service returned HTTP 403 / Cloudflare 1010 (browser signature denied), with no APK metadata. The request was not retried. Private request/response captures are in ignored diagnostics/update-check. No newer APK was downloaded or installed.

A public official-source search found no standalone display-APK or board-specific firmware download. Current official General Settings documentation distinguishes Software Version and Firmware Version but does not document a manual firmware-check button: https://skylight.zendesk.com/hc/en-us/articles/36835387462555-General-Settings . The security-support statement includes model 150-CAL, but supplies no applicable firmware image or Wi-Fi fix: https://skylight.zendesk.com/hc/en-us/articles/26194955094299-Product-Security-and-Telecommunications-Infrastructure-PSTI-Skylight-Calendar .

The existing evidence points below the calendar app: native Android and factory-test Wi-Fi scans fail too, with driver scan aborts around 1.1 seconds. Driver/radio firmware, board configuration and physical radio failure remain candidates; hardware failure is not proven. An app update is unlikely to fix this by itself. A compatible system/vendor update could matter if the defect is software, but no such update has been obtained or verified.
