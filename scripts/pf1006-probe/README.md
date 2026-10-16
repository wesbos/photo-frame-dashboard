# Experimental PF1006 SD probe

**SD boot has not been tested on this unit.**
It tests whether a reviewed SD boot image can read consistent bytes from internal storage.
It does not enable ADB or provide a frame flash or restore procedure.
See the [unit report](../../docs/humblestead-pf1006.md) for the model and firmware evidence.

Review the exact build before card preparation or a frame test.
Follow the [repository rules for device changes](../../README.md#rules-we-learned-the-hard-way).
This guide does not supply the owner's approval for those actions.

## What it does

The **bootloader** is U-Boot, the startup program loaded from the SD card.
Its first stage is called SPL.
The **script**, `pf1006-probe.scr`, contains commands from `probe.cmd.in`.
A **build** contains the compiled bootloader, its matching script and verification records.
Use them together; do not substitute a PF1007L bootloader or use the name `a33.scr`.

The probe selects `mmc 1` as the candidate internal storage.
Its OCR register read must identify MMC, not SD.
It reads sectors 0 through 8191 twice into buffers that contain different filler bytes.
It compares the reads byte for byte and calculates both SHA-256 hashes.

It saves a **capture** on SD FAT partition `mmc 0:1`:
`pf1006-probe-status.txt` and the 4 MiB binary `pf1006-probe.bin`.
It reloads the binary to verify its length and content before writing final status.
This storage **prefix** is not a complete backup.
Optional EXT_CSD register reads record revision and capacity fields, without exporting unique identifiers.
The script has no internal-storage write, partition offset or patch step.

The probe then remains idle until power is disconnected.
It does not start Android or try another boot source.
The outer boot command also stops on script loading or execution failure.

## Hardware limits

The build blocks non-SD block writes and erases and restricts persistent EXT_CSD changes.
Startup still initializes memory and controllers and changes volatile MMC timing, bus width and user-area selection.
An incompatible board can fail during these operations.
The model name and firmware string do not validate these settings.

The inherited A33 profile uses the AXP221/AXP223 power-management driver.
SPL applies the following settings. **They are not measurements from PF1006.**

| PMIC output | Inherited setting |
| --- | --- |
| DCDC1 | 3,000 mV; enables the DCDC1 switch output |
| DCDC2 | 1,100 mV |
| DCDC3 | 1,200 mV |
| DCDC5 | 1,500 mV |
| ALDO1 and ALDO3 | 3,000 mV each |
| ALDO2 | 2,500 mV |
| DCDC4, DLDO1–4 and ELDO1–3 | Disabled; configured value is zero |

If PMIC identification or initialization fails, the guard stops before the regulator setters.
It stops on the first setter error, without undoing earlier settings.
A recognized PMIC does not prove that these voltages suit the board.
Memory retains the 456 MHz clock and ZQ value 15291.
Successful initialization requests a 1,008 MHz CPU clock.
No PF1006-specific voltage changes have been added.

The build requires **at least 256 MiB of detected RAM** because U-Boot loads at `0x4a000000`.
SPL stops below this minimum before loading U-Boot.
The outer boot command checks memory again before loading the script.
Read buffers use `0x42000000` and `0x42400000`; status uses `0x43000000`; the script uses `0x43100000`.

## Building the probe

Run commands from the repository root.
Obtain the pinned U-Boot source:

```sh
git clone --depth 1 --branch v2025.10 https://github.com/u-boot/u-boot.git diagnostics/uboot-pf1006-source
git -C diagnostics/uboot-pf1006-source checkout --detach e50b1e8715011def8aff1588081a2649a2c6cd47
```

`build.sh` refuses a different source HEAD and excludes uncommitted U-Boot source changes.
It archives the pinned commit in a fresh directory, then applies the guard patch and profile.
It checks all requested settings before and after compilation.

Sunxi requires `USE_PREBOOT=y`.
The profile makes `PREBOOT` empty and verifies that `PREBOOT_DEFINED` is off.
Kernel handoff, PSCI, network, USB and persistent environment support are excluded.

### Linux recipe

This recipe was not executed during the validation recorded below.
Prerequisites are GNU Make, host GCC, ARM cross GCC/binutils, Git, GNU sed/coreutils,
tar, bison, flex, SWIG, OpenSSL development headers and pkg-config.
Python also needs development headers, `venv` and setuptools.

Use Python 3.9–3.11 with setuptools in the virtual environment.
The requirements file pins pyelftools and its SHA-256 hashes.

```sh
python3 -m venv diagnostics/pf1006-build-venv
diagnostics/pf1006-build-venv/bin/python -I -c 'import setuptools; print(setuptools.__version__)'
diagnostics/pf1006-build-venv/bin/python -m pip install --require-hashes -r scripts/pf1006-probe/build-requirements.txt
MAKE=make CROSS_COMPILE=arm-linux-gnueabihf- \
  PYTHON="$PWD/diagnostics/pf1006-build-venv/bin/python" \
  scripts/pf1006-probe/build.sh diagnostics/uboot-pf1006-source
```

For SWIG 4.5, supply this setting to the build command:

```sh
HOSTCFLAGS='-DPyInt_AsLong=PyLong_AsLong -DPyString_FromString=PyUnicode_FromString'
```

These aliases replace two removed Python compatibility names in the pinned pylibfdt interface.
They affect host tools only.

### Verified Apple silicon recipe

The original macOS 26.6.2 build used ARM GCC 16.2.0, binutils 2.47.20260726,
GNU Make 4.4.1, Apple clang 21.0.0, SWIG 4.5.1, Python 3.9.6 and setuptools 58.0.4.

With Homebrew and Xcode Command Line Tools available, install the dependencies:

```sh
brew install arm-none-eabi-gcc arm-none-eabi-binutils make bison swig openssl@3 dtc pkgconf coreutils gnu-sed
```

Homebrew supplies GNU Make as `gmake`.
The upstream merge script requires GNU `sed -i` and `cp -T`.
This host required the macOS 26.5 SDK; SDK 27 caused a host linker/architecture mismatch.
If SDK 26.5 is unavailable, resolve the SDK choice before building.

```sh
/Library/Developer/CommandLineTools/usr/bin/python3 -m venv diagnostics/pf1006-build-venv
diagnostics/pf1006-build-venv/bin/python -I -c 'import setuptools; print(setuptools.__version__)'
diagnostics/pf1006-build-venv/bin/python -m pip install --require-hashes -r scripts/pf1006-probe/build-requirements.txt

PF1006_BREW_PREFIX="$(brew --prefix)"
export PATH="$PF1006_BREW_PREFIX/opt/gnu-sed/libexec/gnubin:$PF1006_BREW_PREFIX/opt/coreutils/libexec/gnubin:$PF1006_BREW_PREFIX/opt/bison/bin:$PF1006_BREW_PREFIX/bin:$PATH"
export SDKROOT=/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk
export PKG_CONFIG_PATH="$PF1006_BREW_PREFIX/opt/openssl@3/lib/pkgconfig"
export HOSTCFLAGS="-DPyInt_AsLong=PyLong_AsLong -DPyString_FromString=PyUnicode_FromString -I$PF1006_BREW_PREFIX/opt/openssl@3/include"
export HOSTLDFLAGS="-Wl,-undefined,dynamic_lookup -L$PF1006_BREW_PREFIX/opt/openssl@3/lib"
MAKE=gmake CROSS_COMPILE=arm-none-eabi- HOSTCC=clang HOSTCXX=clang++ \
  PYTHON="$PWD/diagnostics/pf1006-build-venv/bin/python" \
  scripts/pf1006-probe/build.sh diagnostics/uboot-pf1006-source
```

These host flags support SWIG 4.5, macOS Python linking and Homebrew OpenSSL.
They do not change ARM firmware flags.
The helper passes compiler and Python overrides directly to Make.

### Build output and recorded validation

Each invocation creates a fresh **run ID** under `diagnostics/pf1006-probe/`.
An optional second argument changes the output root.
After success, `build.json` records the commit, tool versions, host flags and eight artifact hashes.
`SHA256SUMS` covers the same files: bootloader, rendered script, packaged script, run ID,
profile, resolved configuration, guard patch and source template.
Keep them with their source and build directories.
Fresh run IDs and timestamps change the hashes between builds.
Building does not write an SD card.

On 2026-10-16 UTC, the original build produced a 325,400-byte image with ARM 32-bit entry `0x4a000000`.
It passed the card helper's artifact checks, including script CRCs and the independent SPL checksum.
These results apply to that original revision.

On 2026-10-16, the revised native build completed.
All 56 Python tests passed: 31 card-helper tests and 25 verifier tests.
Both C block-API test variants passed.

## macOS card helper

The helper defaults to a **read-only plan** and never selects a disk automatically.
It requires a build directory, whole-disk identifier and exact card capacity in bytes.
It accepts only external, removable, physical USB media with 512-byte sectors and a capacity of 4–256 GB.
This restriction describes the helper, not all possible card readers.

On 2026-10-16, the original and revised builds were prepared in separate runs on the same card.
It was a SanDisk Ultra PLUS SDXC UHS-I 64 GB card with 63,864,569,856 bytes and 512-byte sectors.
Both runs used MBR/FAT32 with the partition at 16 MiB.
The revised build passed current-source, artifact and approved image hash checks.
Its saved preparation state and 4 MiB post-format backup passed verification.
The helper completion log confirms bootloader/script readback and successful eject.
After eject, verification checked the saved build, state, backup and completion log.
Neither run included frame access or an SD boot test.

### Plan and prepare

Use a spare card whose contents can be erased.
Each time the card is inserted, find its current disk identifier and exact capacity:

```sh
diskutil list external physical
diskutil info diskN
```

Replace `BUILD_DIR`, `diskN` and `EXACT_BYTES` with the build path and observed values.
Run the plan:

```sh
python3 -I scripts/pf1006-probe/card-macos.py BUILD_DIR diskN EXACT_BYTES
```

The helper checks the pinned commit, manifest, hashes, reviewed snapshots, configuration and run ID.
It validates script content/CRCs, the SPL header and checksum, image size, guard markers and unique script name.
It refuses `a33.scr` in the build or on the prepared card.
These checks reject mixed artifacts; binary markers do not prove hardware compatibility.

After approval for the selected card, run preparation:

```sh
sudo python3 -I scripts/pf1006-probe/card-macos.py BUILD_DIR diskN EXACT_BYTES --action prepare
```

The confirmation is `ERASE diskN`, with the actual disk identifier.
Preparation rechecks identity and erases the card as MBR/FAT32 with a 16 MiB gap.
It saves and verifies the **post-format** first 4 MiB.
It writes the bootloader at byte 8192 and copies the unique probe script.
The bootloader must end before 1 MiB.
It verifies readback and ejects the card.
Private identity and backup records stay under ignored `diagnostics/pf1006-probe/cards/RUN_ID/`.
Interrupted preparation is retained for diagnosis, not automatically retried.

**Use each prepared build for one physical frame boot only.**
Preparation refuses run ID reuse. A new attempt requires a fresh build and newly prepared card.
A run ID identifies a build, not individual power cycles.
If a repeated attempt cannot write status, an earlier success could remain undetected on the card.

### Move the card and test the frame

After review and owner approval, choose an observation interval for the exact build.
Five minutes is a conservative first-test interval, not a measured completion deadline.
Record the interval with the result.
Display output is unverified. A dark screen does not prove success.

1. Wait for the card helper to confirm a successful eject.
2. Remove the SD card from the Mac's card reader.
3. Disconnect the frame's power cable.
4. Insert the SD card into the frame's SD slot.
5. Reconnect the frame's power cable once.
6. Observe the frame for the selected interval.
7. Disconnect the frame's power cable.
8. Remove the SD card from the frame.
9. Insert the SD card into the Mac's card reader.
10. Collect the result with the procedure below.

If the result is absent or incomplete, keep it for diagnosis.
Do not bypass a failed check or apply a firmware patch.

### Collect

Recheck the card's current disk identifier and exact capacity.
Use the original build directory for the attempt.
Run collection without `sudo`:

```sh
python3 -I scripts/pf1006-probe/card-macos.py BUILD_DIR diskN EXACT_BYTES --action collect
```

Collection checks saved identity, the original build, the script and the complete capture.
It mounts read-only if needed; an existing macOS read/write mount can cause OS metadata writes.
Validated files go to ignored `backups/pf1006-probe/RUN_ID/`; existing destinations are refused.
The helper verifies the saved copy and ejects the card.
Keep raw captures and card identity records private.

### Remove the bootloader

Keep the original build directory and private card records until removal is complete.
Collection and removal accept that original build even if the checkout's source files have changed.
Run removal with the card's current disk identifier and exact capacity:

```sh
sudo python3 -I scripts/pf1006-probe/card-macos.py BUILD_DIR diskN EXACT_BYTES --action remove
```

The confirmation is `REMOVE BOOTLOADER diskN`, with the actual disk identifier.
Removal checks the saved identity and post-format backup hash.
It reads the current boot area twice and requires the expected installed bytes.
It restores that area from the backup and verifies the result.
It leaves card files intact.
**It does not recover the card contents erased during preparation.**

Removal also handles interruption after a complete bootloader write, before the final preparation-state save.
The current prefix must exactly match the expected installed image.
A partial or changed prefix is refused.

## Host verification

The build replaces `@RUN_ID@` with a fresh 32-character lowercase hexadecimal token.
Use the expected run ID from the build record, not the card's output:

```sh
python3 -I scripts/pf1006-probe/verify.py /path/to/capture --run-id BUILD_TOKEN
```

The verifier only reads files.
It requires complete success status, the expected run ID and matching hashes from both storage reads.
It also requires successful SD readback and an exactly 4 MiB binary file.
It rejects truncation, corruption, inconsistent metadata and 64 KiB runs of `0xCC` filler.
It reports eGON boot0, Android boot and FDT signature candidates.
It does not extract or change their contents.
A signature can be a false positive; it does not establish a partition map.

To compare two separately verified captures:

```sh
python3 -I scripts/pf1006-probe/verify.py /path/to/new --run-id NEW_TOKEN \
  --compare /path/to/prior --compare-run-id PRIOR_TOKEN
```

Equal hashes prove equal file content, not separate frame boots.
Record each capture's test history separately.
The first 4 MiB might not contain the Android boot partition.
Do not design a persistent change from this prefix alone.

## Offline tests

These tests require Python 3.9 or later and use only its standard library:

```sh
python3 -I scripts/pf1006-probe/test_verify.py
python3 -I scripts/pf1006-probe/test_card_macos.py
```

Tests cover corrupted captures, stale status, capacity decoding, comparison, disk guards, tampering and prepare/collect/remove behavior.
They use synthetic builds, temporary files and a fake `diskutil` interface.
They do not open disk devices or execute U-Boot on hardware.

Run the compiled C guard tests against the pinned U-Boot source:

```sh
python3 -I scripts/a33-sdboot/test-pf1006-readonly.py diagnostics/uboot-pf1006-source
```

These tests use the host C compiler and cover both block-API variants.
