#!/usr/bin/env python3
"""Stage Dromart MI86 SD-card files into a directory.

Writes only under --out. It does not mount, format, or eject a card. Point
--out at a folder, then copy that folder onto the FAT32 card as described in
docs/dromart-mi86.md. Passing a card mount as --out writes those files there
and leaves every other file on the card alone.

The APK filename is shell syntax. This program creates it. Do not paste that
name into a shell.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import os
import shutil
import subprocess
import struct
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE / "probe.sh"
ENABLE = HERE / "enable-adb.sh"
# Pins of the reviewed sources staged by this tool; hardware coverage is in the doc.
EXPECTED = {
    PROBE: "421ffd9c25a9ecb74a2fcf7cafbe31bcaff537d38bf73fcadf2f8d8927913c62",
    ENABLE: "c29e93a0718cf62d1b543500f3d75b487ada31755707158decd8ada4698dfff5",
}
CONFIG = "auto_run=action_update_version\n"
APK_NAME = (
    "x';sh${IFS}$(find${IFS}${ANDROID_DATA%data}storage${IFS}-maxdepth${IFS}2"
    "${IFS}-name${IFS}p_frameo_jb);#.apk"
)
MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="net.frameo.frame"
    android:versionCode="{version_code}"
    android:versionName="mi86-sd-{version_code}">
    <uses-sdk android:minSdkVersion="23" android:targetSdkVersion="23" />
    <application android:label="MI86 SD utility" android:hasCode="false"
        android:allowBackup="false" />
</manifest>
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def check_sources() -> None:
    for path, expected in EXPECTED.items():
        if not path.is_file():
            raise SystemExit(f"missing {path}")
        actual = sha256(path)
        if actual != expected:
            raise SystemExit(f"{path.name} hash {actual} != {expected}")


def find_sdk() -> Path:
    candidates = []
    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(key)
        if value:
            candidates.append(Path(value))
    candidates.append(Path.home() / "Library/Android/sdk")
    candidates.append(Path.home() / "Android/Sdk")
    for candidate in candidates:
        if (candidate / "build-tools").is_dir():
            return candidate
    raise SystemExit(
        "Android SDK not found. Set ANDROID_HOME to a SDK with build-tools and platforms."
    )


def version_key(name: str) -> tuple:
    parts = []
    for piece in name.split("."):
        number = ""
        for char in piece:
            if char.isdigit():
                number += char
            else:
                break
        parts.append(int(number) if number else -1)
    return tuple(parts)


def find_tools(sdk: Path) -> tuple[Path, Path, Path, Path]:
    build_tools = sorted(
        (p for p in (sdk / "build-tools").iterdir() if p.is_dir()),
        key=lambda path: version_key(path.name),
    )
    aapt2 = apksigner = None
    for directory in reversed(build_tools):
        if aapt2 is None and (directory / "aapt2").is_file():
            aapt2 = directory / "aapt2"
        if apksigner is None and (directory / "apksigner").is_file():
            apksigner = directory / "apksigner"
        if aapt2 and apksigner:
            break
    platforms = sorted(
        (p for p in (sdk / "platforms").glob("android-*") if (p / "android.jar").is_file()),
        key=lambda path: version_key(path.name.removeprefix("android-")),
    )
    if aapt2 is None or apksigner is None or not platforms:
        raise SystemExit(f"SDK at {sdk} is missing aapt2, apksigner, or android.jar")
    zipalign = aapt2.with_name("zipalign")
    if not zipalign.is_file():
        raise SystemExit(f"missing {zipalign}")
    return aapt2, zipalign, apksigner, platforms[-1] / "android.jar"


def find_keytool() -> Path:
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        keytool = Path(java_home) / "bin" / "keytool"
        if keytool.is_file():
            return keytool
    found = shutil.which("keytool")
    if found:
        return Path(found)
    raise SystemExit("keytool not found. Set JAVA_HOME or install a JDK.")


def run(args: list[Path | str], env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(arg) for arg in args],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )


def check_public_key(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"public key not found: {path}")
    if path.name == "adbkey":
        raise SystemExit(f"{path} looks like a private key. Pass adbkey.pub.")
    text = path.read_text(encoding="utf-8", errors="replace")
    if "PRIVATE" in text:
        raise SystemExit(f"{path} contains a private key. Pass the .pub file only.")
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        raise SystemExit(f"{path} must be one public-key line, found {len(lines)}")
    blob = lines[0].split()[0]
    try:
        raw = base64.b64decode(blob, validate=True)
    except (ValueError, binascii.Error):
        raise SystemExit(f"{path} is not canonical ADB public-key base64") from None
    if (len(blob) != 700 or len(raw) != 524
            or base64.b64encode(raw).decode("ascii") != blob
            or struct.unpack_from("<I", raw, 0)[0] != 64
            or struct.unpack_from("<I", raw, 520)[0] not in (3, 65537)):
        raise SystemExit(f"{path} is not a supported ADB RSA public key")


def build_apk(destination: Path, version_code: int) -> None:
    sdk = find_sdk()
    aapt2, zipalign, apksigner, android_jar = find_tools(sdk)
    keytool = find_keytool()
    with tempfile.TemporaryDirectory(prefix="mi86-apk-") as temp_name:
        temp = Path(temp_name)
        manifest = temp / "AndroidManifest.xml"
        manifest.write_text(MANIFEST.format(version_code=version_code), encoding="utf-8")
        unsigned = temp / "unsigned.apk"
        aligned = temp / "aligned.apk"
        keystore = temp / "probe-signing.p12"
        run([aapt2, "link", "-o", unsigned, "--manifest", manifest, "-I", android_jar])
        run([zipalign, "-f", "4", unsigned, aligned])
        run(
            [
                keytool,
                "-genkeypair",
                "-noprompt",
                "-keystore",
                keystore,
                "-storetype",
                "PKCS12",
                "-storepass",
                "local-probe-only",
                "-alias",
                "probe",
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                "3650",
                "-dname",
                "CN=MI86 SD utility",
            ]
        )
        run(
            [
                apksigner,
                "sign",
                "--ks",
                keystore,
                "--ks-key-alias",
                "probe",
                "--ks-pass",
                "pass:local-probe-only",
                "--v1-signing-enabled",
                "true",
                "--v2-signing-enabled",
                "true",
                "--v4-signing-enabled",
                "false",
                "--out",
                destination,
                aligned,
            ]
        )
        verified = run(
            [
                apksigner,
                "verify",
                "--verbose",
                "--min-sdk-version",
                "23",
                "--max-sdk-version",
                "23",
                destination,
            ]
        ).stdout
        badging = run([aapt2, "dump", "badging", destination]).stdout
    if f"versionCode='{version_code}'" not in badging or "name='net.frameo.frame'" not in badging:
        raise SystemExit("APK identity check failed")
    if "minSdkVersion:'23'" not in badging and "sdkVersion:'23'" not in badging:
        raise SystemExit("APK minimum API check failed")
    if "Verified using v1 scheme (JAR signing): true" not in verified:
        raise SystemExit("APK is missing the Android 6 v1 signature")


def _regular_or_absent(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise SystemExit(f"refusing non-regular destination: {path}")


def _directory_or_absent(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise SystemExit(f"refusing non-directory destination: {path}")


def stage(out: Path, mode: str, version_code: int, public_key: Path | None, replace: bool) -> None:
    check_sources()
    out = out.expanduser().absolute()
    # Reject symlink traversal, including dangling links. Use the real path explicitly
    # if a legitimate parent is a symlink (for example /private/tmp on macOS).
    for parent in (out, *out.parents):
        if parent.is_symlink():
            raise SystemExit(f"symlink in output path: {parent}; choose its real path")
    _directory_or_absent(out)
    utilities = out / "Frameo_utilities"
    key_dir = out / "mi86-adb-v2"
    script_path = out / "p_frameo_jb"
    config_path = utilities / "frameo_utilities.config"
    apk_path = utilities / APK_NAME
    key_path = key_dir / "adbkey.pub"
    for directory in (utilities, key_dir):
        _directory_or_absent(directory)
    for path in (script_path, config_path, apk_path, key_path):
        _regular_or_absent(path)
    if not replace and any(path.exists() for path in (script_path, utilities, key_dir)):
        raise SystemExit(f"{out} already has card files; explicit --replace is required")
    if utilities.exists():
        unknown = [p.name for p in utilities.iterdir()
                   if p.name not in ("frameo_utilities.config", APK_NAME)]
        if unknown:
            raise SystemExit("Frameo_utilities has unrelated/AppleDouble files; preserve them elsewhere before staging")
    source = PROBE if mode == "probe" else ENABLE
    key_bytes = None
    if mode == "adb":
        if public_key is None:
            raise SystemExit("--mode adb requires --pubkey")
        check_public_key(public_key)
        key_bytes = public_key.read_bytes()
    script_bytes = source.read_bytes()
    if hashlib.sha256(script_bytes).hexdigest() != EXPECTED[source]:
        raise SystemExit("source changed during staging")
    out.mkdir(parents=True, exist_ok=True)
    # Finish the build and all input checks before changing any existing card payload.
    # The configuration is the trigger: disarm it before publishing, and publish it LAST.
    # On publication failure leave it absent; never re-arm a partly updated payload.
    with tempfile.TemporaryDirectory(prefix=".mi86-stage-", dir=out) as temp_name:
        temp = Path(temp_name)
        staged_script = temp / "p_frameo_jb"
        staged_script.write_bytes(script_bytes)
        staged_apk = temp / APK_NAME
        build_apk(staged_apk, version_code)
        staged_config = temp / "frameo_utilities.config"
        staged_config.write_text(CONFIG, encoding="utf-8")
        staged_key = temp / "adbkey.pub"
        if key_bytes is not None:
            staged_key.write_bytes(key_bytes)
            check_public_key(staged_key)
        expected = {staged_script.name: script_bytes, staged_apk.name: staged_apk.read_bytes(),
                    staged_config.name: CONFIG.encode("utf-8")}
        if key_bytes is not None:
            expected[staged_key.name] = key_bytes

        def publish(src: Path, dest: Path) -> None:
            with src.open("rb") as payload:
                os.fsync(payload.fileno())
            _regular_or_absent(dest)
            os.replace(src, dest)
            if dest.read_bytes() != expected[dest.name]:
                raise SystemExit(f"readback mismatch: {dest}")

        # Recheck destinations after a potentially slow SDK build.
        for directory in (out, utilities, key_dir):
            _directory_or_absent(directory)
        for path in (script_path, config_path, apk_path, key_path):
            _regular_or_absent(path)
        utilities.mkdir(exist_ok=True)
        try:
            config_path.unlink(missing_ok=True)
            publish(staged_script, script_path)
            publish(staged_apk, apk_path)
            if key_bytes is not None:
                key_dir.mkdir(exist_ok=True)
                publish(staged_key, key_path)
            # Reject an unexpected APK that appeared during the build/publication.
            if {p.name for p in utilities.iterdir()} != {APK_NAME}:
                raise SystemExit("unexpected utility file appeared; trigger remains disarmed")
            publish(staged_config, config_path)
        except BaseException:
            # This also covers a failed configuration readback and KeyboardInterrupt.
            # Unlink the entry itself; never follow a symlink in an error path.
            try:
                config_path.unlink(missing_ok=True)
            except OSError:
                print("ERROR: could not disarm trigger; do not insert this card", file=sys.stderr)
            raise
    print(f"mode: {mode}")
    print(f"out: {out}")
    print(f"p_frameo_jb: {script_path.stat().st_size} bytes {sha256(script_path)}")
    print(f"config: {sha256(config_path)}")
    print(f"apk: {apk_path.stat().st_size} bytes versionCode {version_code}")
    print("apk filename created by this program; do not paste it into a shell")
    if mode == "adb":
        print("public key copied to mi86-adb-v2/adbkey.pub; existing recovery snapshots preserved")
    print("card not ejected; publish the config last when copying to the FAT32 root")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="directory to stage into")
    parser.add_argument("--mode", choices=("probe", "adb"), required=True)
    parser.add_argument(
        "--version-code",
        type=int,
        default=80322,
        help="must be higher than the Frameo versionCode on the frame (default 80322)",
    )
    parser.add_argument("--pubkey", type=Path, help="adbkey.pub for --mode adb")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace known script, config, utility APK and public key; preserve recovery snapshots",
    )
    args = parser.parse_args()
    if args.version_code <= 0:
        raise SystemExit("--version-code must be positive")
    stage(args.out, args.mode, args.version_code, args.pubkey, args.replace)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.stderr.write(error.stderr or error.stdout or str(error))
        sys.stderr.write("\n")
        raise SystemExit(1) from error
