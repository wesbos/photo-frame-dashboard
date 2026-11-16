# Lexar Pexar PX-110 tools

The tools behind [docs/lexar-pexar-px-110.md](../../docs/lexar-pexar-px-110.md). They build the images
that page describes, check them, and repair the frame. Read that page first, all of it. The steps are in
its "Reproduce it" section.

**One firmware only: `PF1106_V2.06_20250527`.** The stock image hashes for it are fixed in
`tools/px110conf.py`. A backup that does not match is refused. So is a `super` whose `product` sits
anywhere but 4096-byte blocks 32512 onward, 109,813,760 bytes long, because the recovery script and the
repair script write to that place.

Nothing here is safe in every case. A wrong write to flash can leave the frame dead. Each tool that writes
shows its plan and goes only on the typed word `yes`.

## What is not here

- No keys. `fetch-keys.sh` downloads them and checks each SHA-256.
- No firmware, no backup, no vendor file. You bring your own backup of your own frame.
- No kiosk APK. `build.py` takes the path of yours.
- No WebView APK and no logo picture.
- mtkclient itself. Only our changes to it, as a patch.

## What you need installed

Worked on macOS 27 (Apple silicon). Versions we used are in brackets. Other versions may give different
bytes for the `boot` wrapper; the checks still apply.

| For | Needs |
| --- | --- |
| Everything | `python3` (3.14), standard library only. `openssl` (LibreSSL 3.3.6). `shasum`, `gzip`, `bash`, `zsh` |
| `build.py`, `run_tests.sh` | e2fsprogs: `debugfs`, `e2fsck`, `dumpe2fs` (1.47.4) |
| `bootbuild.py`, `test_bootwrap.py`, `initscan.py` | `clang` (Apple clang 21) and `arm-none-eabi-ld`, `-strip`, `-objdump` (GNU binutils 2.47) |
| `run_tests.sh` tests 8 and 11 | Android SDK build-tools (`aapt2`, `apksigner`) and a Java runtime. Optional |
| `logosign.py make` | macOS `sips`. `logo-from-splash.py` does not need it |
| `frame-doctor.sh` | `adb`, and mtkclient with our patch. macOS only: it lists USB devices with `ioreg` |
| `fetch-keys.sh` | `curl` |

`recbuild.py` and `bootbuild.py` repack a gzip ramdisk. They stop if your Python's zlib does not reproduce
the stock one byte for byte (ours: zlib 1.2.12).

## Settings: one file

Copy `unit.conf.example` to `unit.conf` and fill it in. Git ignores `unit.conf`, `keys/` and `build/`.
The environment wins over the file: `PX110_BACKUP_DIR=...` overrides `BACKUP_DIR`.

```sh
cp unit.conf.example unit.conf
python3 -I tools/px110conf.py show      # what the tools see
```

Your serial goes in `unit.conf` (or `ANDROID_SERIAL`) and nowhere else. No tool has one built in.

## The files

| File | What it does | Writes to the frame? |
| --- | --- | --- |
| `fetch-keys.sh` | Downloads seven published keys from pinned commits. Refuses a file with the wrong SHA-256. `--check` and `--from DIR` work offline | No |
| `tools/px110conf.py` | Reads `unit.conf`. Holds the stock hashes and the `product` position. `check_stock`, `check_product_layout` | No |
| `tools/build.py` | Builds `product.img`, `vbmeta_system.img`, `vbmeta.img` from your backup, `src/photoframe.rc` and your kiosk APK. Removes the vendor updater from `product` | No |
| `tools/verify.py` | Independent checker for that set: key in `lk`, signatures, chain, hash tree, FEC, file listing. Shares no code with the builder | No |
| `tools/run_tests.sh` | Eleven tests on the built set, then writes `build/out/SHA256SUMS` only if none failed | No |
| `tools/avblib.py`, `hashtree.py`, `lp.py`, `diffsum.py` | AVB signing, hash tree and FEC, dynamic-partition table reader, byte diff | No |
| `tools/recbuild.py` | Builds `recovery-rescue.img`: stock recovery plus `src/recovery/rescue.sh` | No |
| `tools/recverify.py` | Independent checker for a recovery image | No |
| `src/recovery/rescue.sh` | Runs **inside recovery on the frame**. Restores five regions from `cache`, climbs the ladder. [STORE-FORMAT.md](STORE-FORMAT.md) is its contract | **Yes**, on the frame, on its own note only |
| `tools/bootbuild.py` | Builds `boot-wrap-recovery.img`: stock `boot` with `src/bootwrap/bootwrap.c` as the first program | No |
| `tools/bootverify.py` | Independent checker for a `boot` image | No |
| `src/bootwrap/bootwrap.c` | Runs **first at every start on the frame**. Arms the recovery note if `para` is empty, then starts the stock `init` | **Yes**: the first 2048 bytes of `para`, only over all zeros |
| `src/bootwrap/initscan.py` | Shows from the stock `init`'s own code that the ten changed bytes are used in one place | No |
| `tools/logosign.py`, `logo-from-splash.py`, `logocodec.py` | Build and sign a `logo` image from a 2000×1200 picture | No |
| `tools/logoverify.py`, `certverify.py` | Independent checkers for the MediaTek two-certificate signature | No |
| `tools/frame-doctor.sh` | Says what state the frame is in. Restores `logo`, `recovery`, `boot`, `vbmeta`, `vbmeta_system`, `product` through the loader port. Stores the known-good set in `cache` | **Yes**, after `yes` |
| `mtkclient-px110.patch` | Our four changes to mtkclient, for commit `118a000a` | No |
| `tools/test_*.py`, `test_frame_doctor.sh` | Tests. No frame needed, none touched | No |

Comments inside `src/recovery/*`, `src/photoframe.rc` and `src/bootwrap/bootwrap.c` still say `patch/...`
for paths. That was this folder's name where it was written. The files are left byte for byte as they
went into the images on the frame, so that a rebuild gives the same bytes.

## Guards on every write

`frame-doctor.sh` is the only tool here that writes from the computer. For each write it:

1. refuses the never-write list first: `preloader lk lk2 seccfg tee1 tee2 frp md_udc nvdata nvram proinfo persist rpmb`;
2. refuses anything not on its allow-list of six;
3. checks the image file's size and its SHA-256 against the recorded one. No recorded hash, no write;
4. checks over adb that `super` starts where the `product` offset assumes (when adb is up);
5. shows the plan and waits for the typed word `yes`. `--dry-run` shows the plan and stops;
6. ends every loader-port job with the watchdog restart;
7. reads every written partition back from the frame and compares.

`rescue.sh` has its own rules, listed in [STORE-FORMAT.md](STORE-FORMAT.md): five regions with fixed
offsets, copies checked three ways before a write, read back after, its own note only.

## Tests

```sh
python3 -I tools/test_recovery.py          # 173 checks
python3 -I tools/test_bootwrap.py          # 52 tests, about two minutes
bash tools/test_frame_doctor.sh            # 91 checks
python3 -I tools/test_logosign.py --build  # 22 checks; makes build/out-logo first
python3 -I tools/test_logo_from_splash.py  # 47 checks
python3 -I tools/test_logocodec.py         # 9 checks
zsh tools/run_tests.sh                     # 11 tests on the product set
```

They need your backup, the keys and the built images. Without a backup or keys each one prints `SKIP`
with the reason and exits 0. Nothing private is shipped to stand in for them.

## What a rebuild gave us

With the stock backup, the pinned keys and the tool versions above:

| Image | SHA-256 |
| --- | --- |
| `recovery-rescue.img` | `780f0a87096639994194075fe4ef85b4d126fcfe384176daab70c0d249a10225` |
| `recovery-stock-resigned.img` (must equal stock) | `14950f348b4722a99b7695f2fee1a25e23f3d450f5f180743ff9ee9b02a2943f` |
| `bootwrap.elf` | `13274847648f2fbee91b04bd718bc29f2c0a2b19eeee898a94e075bfef9f8500` |
| `boot-wrap-recovery.img` | `2ed44261404a8893b7a901a62ec0e8bacf92ca63afe29a76fbb063833fa4a25c` |
| `boot-stock-resigned.img` (must equal stock) | `d232adc9af4f5dfe12c6c8bc6548519ef2dc113693e1cc7ad9665b7041718172` |
| `vbmeta.img` | `428fae125ff658ab7fdbb9ff18ab61f564e4eb61d799d1261e35fe5a12ba4dbb` |

`product.img` and `vbmeta_system.img` depend on your kiosk APK, so yours will differ from ours. Logo
signatures use a random salt, so a logo image differs on every build. A different compiler can change
`bootwrap.elf` and with it the two wrapper images. That is not a fault. `bootverify.py` is the check.

## Licence

This folder follows the repository's licence, except `mtkclient-px110.patch`. That file changes
[mtkclient](https://github.com/bkerler/mtkclient), which is GPL-3.0, and is offered under the same
licence. Its header names the commit it applies to.
