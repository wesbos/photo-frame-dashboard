#!/usr/bin/env bash
# Build experimental files on the host. Do not access a frame or disk device.
set -Eeuo pipefail

fail() {
  printf 'STOP: %s\n' "$*" >&2
  exit 1
}

usage() {
  echo "Usage: $0 PINNED_UBOOT_SOURCE [OUTPUT_ROOT]" >&2
  echo "Overrides: MAKE, CROSS_COMPILE, HOSTCC, HOSTCXX, HOSTCFLAGS, HOSTLDFLAGS, PYTHON, JOBS" >&2
  exit 2
}
[[ $# -ge 1 && $# -le 2 ]] || usage
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
SOURCE_DIR="$(cd -- "$1" && pwd)"
UBOOT_COMMIT=e50b1e8715011def8aff1588081a2649a2c6cd47
MAKE="${MAKE:-make}"
PYTHON="${PYTHON:-python3}"
export CROSS_COMPILE="${CROSS_COMPILE:-arm-linux-gnueabihf-}"
export HOSTCC="${HOSTCC:-cc}"
export HOSTCXX="${HOSTCXX:-c++}"

for tool in git tar "$MAKE" "$PYTHON" "${CROSS_COMPILE}gcc"; do
  command -v "$tool" >/dev/null || fail "Install the required tool: $tool"
done
"$PYTHON" -I -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else "Use Python 3.9 or later.")'
# U-Boot's merge script uses sed -i and cp -T. Select GNU tools on macOS.
for tool in sed cp; do
  if ! tool_version="$("$tool" --version 2>/dev/null)" || [[ "$tool_version" != *GNU* ]]; then
    fail "Put GNU $tool on PATH before the system version."
  fi
done
[[ "$(git -C "$SOURCE_DIR" rev-parse HEAD)" == "$UBOOT_COMMIT" ]] || \
  fail "Check out the required U-Boot commit: $UBOOT_COMMIT"
# Use the pinned commit. Exclude local source changes and previous build files.
RUN_ID="$("$PYTHON" -I -c 'import secrets; print(secrets.token_hex(16))')"
JOBS="${JOBS:-$("$PYTHON" -I -c 'import os; print(min(8, os.cpu_count() or 1))')}"
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || fail "Set JOBS to a positive integer."
OUTPUT_ROOT="${2:-$REPO_DIR/diagnostics/pf1006-probe}"
mkdir -p -- "$OUTPUT_ROOT"
OUTPUT_ROOT="$(cd -- "$OUTPUT_ROOT" && pwd)"
OUTPUT_DIR="$OUTPUT_ROOT/$RUN_ID"
mkdir -- "$OUTPUT_DIR"
trap 'printf "Build failed. Keep these partial files: %s\n" "$OUTPUT_DIR" >&2' ERR
BUILD_SOURCE="$OUTPUT_DIR/source"
BUILD_DIR="$OUTPUT_DIR/build"
mkdir -- "$BUILD_SOURCE" "$BUILD_DIR"
# Command-line values override U-Boot's host compiler and Python defaults.
make_args=(-C "$BUILD_SOURCE" "O=$BUILD_DIR" "CROSS_COMPILE=$CROSS_COMPILE"
           "HOSTCC=$HOSTCC" "HOSTCXX=$HOSTCXX" "PYTHON3=$PYTHON")
if [[ -n "${HOSTCFLAGS+x}" ]]; then make_args+=("HOSTCFLAGS=$HOSTCFLAGS"); fi
if [[ -n "${HOSTLDFLAGS+x}" ]]; then make_args+=("HOSTLDFLAGS=$HOSTLDFLAGS"); fi
printf '%s\n' "$RUN_ID" > "$OUTPUT_DIR/run-id.txt"
cp -- "$SCRIPT_DIR/pf1006.config" "$OUTPUT_DIR/pf1006.config"
cp -- "$SCRIPT_DIR/probe.cmd.in" "$OUTPUT_DIR/probe.cmd.in"
cp -- "$SCRIPT_DIR/../a33-sdboot/pf1006-readonly.patch" "$OUTPUT_DIR/pf1006-readonly.patch"
git -C "$SOURCE_DIR" archive "$UBOOT_COMMIT" | tar -xf - -C "$BUILD_SOURCE"
# Give this source its own Git directory. Keep git apply inside this directory.
git -C "$BUILD_SOURCE" init -q
git -C "$BUILD_SOURCE" apply --check "$OUTPUT_DIR/pf1006-readonly.patch"
git -C "$BUILD_SOURCE" apply "$OUTPUT_DIR/pf1006-readonly.patch"
git -C "$BUILD_SOURCE" apply --reverse --check "$OUTPUT_DIR/pf1006-readonly.patch"

"$PYTHON" -I - "$OUTPUT_DIR" "$RUN_ID" <<'PY'
from pathlib import Path
import re
import sys

output_dir = Path(sys.argv[1])
run_id = sys.argv[2].encode("ascii")
template = (output_dir / "probe.cmd.in").read_bytes()
if set(re.findall(rb"@[A-Z_]+@", template)) != {b"@RUN_ID@"}:
    raise SystemExit("Use only the @RUN_ID@ placeholder in the probe source.")
rendered = template.replace(b"@RUN_ID@", run_id)
# Reserve space for the image header within the 64 KiB load limit.
if len(rendered) + 128 >= 0x10000:
    raise SystemExit("Probe source exceeds the 64 KiB load limit.")
(output_dir / "pf1006-probe.cmd").write_bytes(rendered)
PY

"$MAKE" "${make_args[@]}" Sinlinx_SinA33_defconfig
"$BUILD_SOURCE/scripts/kconfig/merge_config.sh" -m -O "$BUILD_DIR" "$BUILD_DIR/.config" "$OUTPUT_DIR/pf1006.config"
"$MAKE" "${make_args[@]}" olddefconfig

check_config() {
  "$PYTHON" -I - "$OUTPUT_DIR/pf1006.config" "$BUILD_DIR/.config" "$BUILD_SOURCE" <<'PY'
from pathlib import Path
import re
import sys

profile, resolved, source = map(Path, sys.argv[1:])

def read_config(path):
    options = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        enabled = re.fullmatch(r"(CONFIG_\w+)=(.*)", line)
        disabled = re.fullmatch(r"# (CONFIG_\w+) is not set", line)
        if enabled:
            key, value = enabled.groups()
        elif disabled:
            key, value = disabled[1], "n"
        elif not line or line.startswith("#"):
            continue
        else:
            raise SystemExit(f"Invalid configuration line in {path.name}: {line}")
        if key in options:
            raise SystemExit(f"Duplicate option in {path.name}: {key}")
        options[key] = value
    return options

actual = read_config(resolved)
known = set()
for path in source.rglob("*Kconfig*"):
    if path.is_file() and ".git" not in path.parts:
        known.update(re.findall(r"^\s*(?:menuconfig|config)\s+([A-Z0-9_]+)\s*$",
                                path.read_text(encoding="utf-8", errors="replace"), re.M))
for key, required in read_config(profile).items():
    if key.removeprefix("CONFIG_") not in known:
        raise SystemExit(f"Unknown profile symbol: {key}")
    value = actual.get(key, "n")
    if value != required:
        raise SystemExit(f"Configuration mismatch: {key} must be {required}; got {value}")
for key, value in actual.items():
    if re.fullmatch(r"CONFIG_(?:SPL_|TPL_)?ENV_IS_IN_\w+", key) and value == "y":
        raise SystemExit(f"Disable the persistent environment: {key}")
if actual.get("CONFIG_TEXT_BASE") != "0x4a000000":
    raise SystemExit("Load address changed. Review the RAM guards before use.")
print("Configuration checks passed.")
PY
}
check_config
"$MAKE" "${make_args[@]}" -j "$JOBS"
check_config

cp -- "$BUILD_DIR/u-boot-sunxi-with-spl.bin" "$OUTPUT_DIR/u-boot-sunxi-with-spl.bin"
cp -- "$BUILD_DIR/.config" "$OUTPUT_DIR/u-boot.config"
"$BUILD_DIR/tools/mkimage" -A arm -T script -C none -n "PF1006 experimental read-only probe" \
  -d "$OUTPUT_DIR/pf1006-probe.cmd" "$OUTPUT_DIR/pf1006-probe.scr"
"$BUILD_DIR/tools/mkimage" -l "$OUTPUT_DIR/pf1006-probe.scr"

# Write build.json last to mark completion. Hashes identify these exact files.
# They do not prove hardware compatibility.
"$PYTHON" -I - "$OUTPUT_DIR" "$RUN_ID" "$UBOOT_COMMIT" "$MAKE" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import platform
import shlex
import subprocess
import sys

output_dir = Path(sys.argv[1])
run_id, pin, make_cmd = sys.argv[2:]

def version(command):
    lines = subprocess.check_output(command + ["--version"], text=True).splitlines()
    if not lines:
        raise SystemExit(f"No version output from {command[0]}")
    return lines[0]

names = ["u-boot-sunxi-with-spl.bin", "pf1006-probe.cmd", "pf1006-probe.scr",
         "run-id.txt", "pf1006.config", "u-boot.config", "pf1006-readonly.patch",
         "probe.cmd.in"]
artifacts = {}
for name in names:
    data = (output_dir / name).read_bytes()
    if not data:
        raise SystemExit(f"Empty build artifact: {name}")
    artifacts[name] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
if artifacts["pf1006-probe.scr"]["size"] > 0x10000:
    raise SystemExit("Compiled probe exceeds the 64 KiB load limit.")
checksums = "".join(f"{info['sha256']}  {name}\n" for name, info in sorted(artifacts.items()))
(output_dir / "SHA256SUMS").write_text(checksums, encoding="ascii")
manifest = {"format": 1, "experimental": True, "hardware_tested": False,
            "run_id": run_id, "u_boot_commit": pin,
            "min_ram_bytes": 0x10000000, "text_base": "0x4a000000",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "cross_compile": os.environ["CROSS_COMPILE"],
            "compiler_version": version([os.environ["CROSS_COMPILE"] + "gcc"]),
            "binutils_version": version([os.environ["CROSS_COMPILE"] + "ld"]),
            "make_version": version([make_cmd]),
            "hostcc": os.environ["HOSTCC"],
            "hostcc_version": version(shlex.split(os.environ["HOSTCC"])),
            "hostcflags_override": os.environ.get("HOSTCFLAGS"),
            "hostldflags_override": os.environ.get("HOSTLDFLAGS"),
            "platform": platform.platform(), "python_version": sys.version,
            "python_executable": sys.executable,
            "artifacts": artifacts}
temporary = output_dir / "build.json.tmp"
temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
temporary.replace(output_dir / "build.json")
PY
trap - ERR
printf 'Experimental artifacts built; hardware remains untested.\nRun ID: %s\nOutput: %s\n' "$RUN_ID" "$OUTPUT_DIR"
