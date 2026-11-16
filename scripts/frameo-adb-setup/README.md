# frameo-adb-setup

Build an SD-card package that enables **owner ADB access** on a Frameo digital
photo frame, using the frame's own built-in SD-card maintenance task — then
verify the result from your computer.

The package adds *your* ADB public key to the frame's ADB authorization file,
enables ADB over TCP, and restarts the ADB daemon. No app is installed on the
frame, your private key never leaves your computer, and every change the setup
makes is snapshotted on the card so it can be undone exactly.

> **For frames you own.** This project exists so an owner can service their own
> hardware: enable debugging access, back up photos and settings, or install
> software of their choosing. It requires physical access to the frame and its
> SD-card slot. Do not use it on hardware you do not own or do not have
> permission to modify.

## How it works

Frameo frames ship a manufacturer maintenance task that watches for a
configuration file on a removable SD card (`Frameo_utilities/frameo_utilities.config`
containing `auto_run=action_update_version`) and then processes the APK placed
in that directory. Before installing anything, the task passes the APK's
filename to a privileged helper.

The SD package this tool builds contains:

| File | Purpose |
| --- | --- |
| `Frameo_utilities/frameo_utilities.config` | asks the frame to run its update task |
| `Frameo_utilities/x'…;.apk` | a metadata-only APK, named so that the update task launches the setup script instead of an install; it contains no code and is never installed |
| `adb_setup` | the setup script: validates and adds your public key, enables ADB over TCP (port 5555), restarts adbd, and verifies every change |
| `adbkey` | your ADB **public** key (the matching private key stays on your host) |

The metadata APK carries the frame app's package name (`net.frameo.frame`) and a
version code higher than the installed app — the two things the update task
checks. A `pm install` step follows; it is irrelevant to the setup: the setup
script has already run, and the placeholder APK cannot replace the installed
Frameo app.

## Requirements

- A Frameo frame **you own**, with an SD-card slot, and physical access to it
- A macOS or Linux host with Python 3.9+ (standard library only)
- Android SDK build-tools (`aapt2`, `apksigner`) — e.g. via Android Studio, or:
  `sdkmanager "build-tools;34.0.0" "platforms;android-34"`
- An ADB key pair. If you do not have one: `adb keygen ~/.android/adbkey`
  creates the private `adbkey` (keep it on your host) and `adbkey.pub`
- A FAT/exFAT SD card; a small one is plenty
- APK signing keystore: the builder uses `~/.android/debug.keystore` if
  present, or generates a throwaway key (any signature is fine; the APK is a
  metadata-only placeholder that never replaces the installed app)

## Build the package

From the `scripts/frameo-adb-setup/` directory:

```sh
python3 build.py --adb-pubkey ~/.android/adbkey.pub --out out
```

Or build and write a mounted card in one step (the card must be empty of
package files — no existing `Frameo_utilities`, markers, or prior attempt
directories; the builder refuses a dirty card rather than deleting anything):

```sh
python3 build.py --adb-pubkey ~/.android/adbkey.pub --sd-card /Volumes/FRAME_SD
```

The builder signs the metadata APK, assembles the package, then **verifies its
own output** (file inventory, SHA-256 hashes, ZIP contents, APK identity and
signature, key format) before handing it over. The result in `out/`:

| Path | Contents |
| --- | --- |
| `out/sd/` | the package files, expanded |
| `out/frameo-adb-setup-sd.zip` | the same files, zipped |
| `out/connect.sh` | host-side connection check helper |
| `out/restart_adbd.sh` | detached adbd restart helper, used when undoing the setup |
| `out/manifest.json` | build record: target, versions, hashes, tooling |

`./verify.sh out` re-checks any existing output at any time.

### Frames running newer Frameo releases

The default build assumes Frameo 1.30.19 (versionCode 69880), the release
verified on hardware. The frame's update task only accepts an APK with a
version code **higher than the installed app**, so on a newer frame raise the
setup version code:

```sh
# if you know the installed versionCode:
python3 build.py --adb-pubkey ~/.android/adbkey.pub --out out --installed-version-code 70000
# or simply pick a comfortably high code:
python3 build.py --adb-pubkey ~/.android/adbkey.pub --out out --version-code 99999999
```

## Deploy

1. Copy the contents of `out/sd/` (or unzip `out/frameo-adb-setup-sd.zip`) to
   the **root** of a FAT/exFAT card.
   - `Frameo_utilities` must contain **exactly one** `.apk`
   - on macOS, clean hidden AppleDouble files first
     (`dot_clean -m /Volumes/FRAME_SD`, or delete every `._*` file) — a hidden
     `._….apk` counts as a second APK and the frame will refuse the card
2. With the frame running normally — do **not** force-stop the Frameo app —
   insert the card. (Booting with the card already inserted is less reliable
   than inserting while the app is running.)
3. Wait a minute or two. The frame processes the card, runs the setup script
   once, and writes its results back to the card.

### Reading the result

Put the card back in your computer and check:

| File | Meaning |
| --- | --- |
| `done` | the setup completed and self-verified |
| `result.txt` | top-level run log: names the failing check on errors and whether rollback was verified |
| `started` | a previous attempt already began; the same card will not run again (one-shot design) |
| `adb_keys.before`, `adb_keys.before.state` | snapshot of the frame's prior ADB authorization, for undo |
| `attempt.*` | per-run snapshots: prior key bytes, owner/mode, SELinux context, ADB port properties, adbd state |

The setup is deliberately one-shot: it removes the auto-run configuration
*before* touching the frame, so a failed run cannot silently repeat, and a
successful run cannot run twice — whether the run succeeds or fails.

## Verify access from your computer

Find the frame's IP address in the Frameo app (Settings → network information),
then:

```sh
ADB_PRIVATE_KEY=~/.android/adbkey ./out/connect.sh <frame-ip>
```

`connect.sh` starts a dedicated, isolated ADB server that uses only your key,
connects to the frame over TCP, and runs `id` and `su 0 id`. A successful run
ends with:

```
uid=0(root) gid=0(root) groups=0(root) …
```

That confirms ADB access with root available: any `su 0 <command>` now works
over ADB. The helper never runs `kill-server` and leaves unrelated ADB servers
alone.

From here you can back up photos and app data, install software of your
choosing, or adjust the frame's configuration — your frame, your call.

## Undoing the setup

Every change is reversible using the snapshots the setup left on the card.
With ADB access still working (`result.txt` says `done`):

```sh
adb connect <frame-ip>:5555
# values below come from the card's attempt.* snapshot:
#   adb_keys.raw (prior key bytes), metadata (uid gid mode), selinux (context)
adb push <card>/attempt.NNNNN/adb_keys.raw /data/local/tmp/adb_keys.raw
cat > /tmp/restore.sh <<'EOF'
#!/system/bin/sh
set -e
cp /data/local/tmp/adb_keys.raw /data/misc/adb/adb_keys
chown 1000:2000 /data/misc/adb/adb_keys
chmod 640 /data/misc/adb/adb_keys
chcon u:object_r:adb_keys_file:s0 /data/misc/adb/adb_keys
setprop service.adb.tcp.port ''
setprop persist.adb.tcp.port ''
EOF
adb push /tmp/restore.sh /data/local/tmp/restore.sh
adb shell su 0 sh /data/local/tmp/restore.sh
adb push out/restart_adbd.sh /data/local/tmp/restart_adbd.sh
adb shell su 0 sh /data/local/tmp/restart_adbd.sh /data/local/tmp/restart.status
adb shell su 0 cat /data/local/tmp/restart.status   # poll until: complete
```

Notes:

- Substitute the exact values recorded on the card: `attempt.*/metadata`
  stores them space-separated as `uid gid mode` (use `uid:gid` for `chown`),
  `attempt.*/selinux` holds the SELinux context, and
  `attempt.*/service.adb.tcp.port` / `attempt.*/persist.adb.tcp.port` hold the
  original port properties (they may not have been empty).
- The restart status file goes through `scheduled` → `stopping` → `complete`
  over a few seconds; re-read it until it says `complete` (a `failed: …`
  value names the step that did not work).
- If `adb_keys.before.state` says `absent`, the frame originally had no
  authorization file: remove `/data/misc/adb/adb_keys` instead of copying one.
  If it says `empty`, restore a zero-byte file.
- Empty property values stay inside the device-side script on purpose — host
  shells can drop empty arguments.
- `restart_adbd.sh` restarts only adbd, detached from your connection, so a
  dropped ADB session cannot interrupt it or stop the Android framework.

If ADB access is *not* available after a failed run, remove the card and read
`result.txt`: the setup rolls back and stays disarmed on failure, and the log
states whether rollback was verified. The changes this package can make are
limited to the ADB authorization file, the two ADB port properties, and an
adbd restart.

## Troubleshooting

- **No `started` marker, no `result.txt`** — the frame's update task never ran
  (or the card was not writable). Confirm the card is FAT/exFAT; that `Frameo_utilities/frameo_utilities.config`
  sits at the card root with exactly `auto_run=action_update_version`; that
  exactly one `.apk` is in `Frameo_utilities` (watch for macOS `._*.apk`
  files); and that the Frameo app was running when you inserted the card.
- **`Multiple APK files found` in the frame's logs** — a second `.apk`
  (usually a hidden AppleDouble file) is present; clean the card and retry.
- **Card processed but nothing happened** — the frame's app is probably newer
  than the default assumes, so the version-code gate rejected the APK; rebuild
  with a higher `--version-code` (see above) on a fresh card.
- **Setup ran but reported an error** — `result.txt` names the failing check
  and whether rollback succeeded; keep the card and its `attempt.*` snapshots.

## Supported frames and versions

| Frame | Firmware | Frameo app | Status |
| --- | --- | --- | --- |
| Frameo 159K (RK3326) | Android 8.1 | 1.30.19 (versionCode 69880) | verified on hardware |

Other Frameo releases that retain the same manufacturer update task are
expected to work with an adjusted `--version-code`. Reports — success or
failure — for specific models are welcome as issues.

## Safety design

- **One-shot** — `started`/`done` markers plus removal of the auto-run config
  mean the card cannot run twice, in either order of success or failure.
- **Owner key only** — the package carries your public key; the private key
  never leaves your host, and the only access enabled is ADB over TCP on port
  5555, which authenticates solely with a matching key pair.
- **Fail-closed** — every step is verified (key structure, file metadata,
  property values, adbd state); any mismatch triggers rollback to the
  snapshotted baseline, and the log says whether rollback was verified.
- **Snapshots** — each run records prior key bytes, owner/mode, SELinux
  context, port properties, and service state on the card for exact undo.
- **Host-side verification** — the builder verifies its complete output before
  the card is ever written, and `verify.sh` re-checks any output later.
- **Narrow scope** — the setup touches only the ADB authorization file, two
  ADB port properties, and the adbd service; nothing else on the frame changes.

## Repository layout

```
build.py                         build the SD package (see --help)
package_verify.py, verify.sh     verify a built package
templates/AndroidManifest.xml    metadata APK manifest template
templates/adb_setup              the on-frame setup script
templates/connect.sh             host-side connection check helper
templates/restart_adbd.sh        detached adbd restart helper for rollback
```

## Development

Smoke-test any change with a full build-and-verify round (no device
needed), run from `scripts/frameo-adb-setup/`:

```sh
python3 build.py --adb-pubkey ~/.android/adbkey.pub --out out && ./verify.sh out
shellcheck templates/adb_setup templates/restart_adbd.sh templates/connect.sh
```

The round-trip exercises the complete package: APK assembly and signing, the
SD layout, ZIP contents, manifest hashes, and the verifier's independent
checks.
