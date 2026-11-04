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
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE / "probe.sh"
ENABLE = HERE / "enable-adb.sh"
# Pins of the reviewed sources staged by this tool; hardware coverage is in the doc.
EXPECTED = {
    PROBE: "421ffd9c25a9ecb74a2fcf7cafbe31bcaff537d38bf73fcadf2f8d8927913c62",
    ENABLE: "559c4107f2a0e08e918eda2cbdbab03dca6b7cc6587fc4db7bdccab45e4d73db",
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
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise SystemExit(f"{path} must be one public-key line, found {len(lines)}")
    blob = lines[0].split()[0]
    if len(blob) != 700 or not blob.startswith("QAAAA") or not blob.endswith("="):
        raise SystemExit(
            f"{path} is not an ADB public key (expected a 700-character QAAAA…= blob)"
        )


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


def stage(out: Path, mode: str, version_code: int, public_key: Path | None, replace: bool) -> None:
    check_sources()
    utilities = out / "Frameo_utilities"
    utilities.mkdir(parents=True, exist_ok=True)
    apk_files = [path for path in utilities.glob("*.apk") if not path.name.startswith("._")]
    script_path = out / "p_frameo_jb"
    if not replace and (script_path.exists() or apk_files):
        raise SystemExit(
            f"{out} already has card files. Pass --replace to overwrite p_frameo_jb, "
            "the config, and the utility APK."
        )
    for extra in utilities.glob("._*.apk"):
        raise SystemExit(
            f"remove AppleDouble file {extra.name} from Frameo_utilities before staging"
        )
    source = PROBE if mode == "probe" else ENABLE
    if mode == "adb":
        if public_key is None:
            raise SystemExit("--mode adb requires --pubkey")
        check_public_key(public_key)
    shutil.copyfile(source, script_path)
    (utilities / "frameo_utilities.config").write_text(CONFIG, encoding="utf-8")
    for old_apk in apk_files:
        old_apk.unlink()
    apk_path = utilities / APK_NAME
    build_apk(apk_path, version_code)
    if mode == "adb":
        key_dir = out / "mi86-adb-v2"
        key_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(public_key, key_dir / "adbkey.pub")
    apk_left = [
        path.name
        for path in utilities.iterdir()
        if path.is_file() and path.name.endswith(".apk")
    ]
    if apk_left != [APK_NAME]:
        raise SystemExit(f"Frameo_utilities must contain one APK, found {apk_left}")
    print(f"mode: {mode}")
    print(f"out: {out}")
    print(f"p_frameo_jb: {script_path.stat().st_size} bytes {sha256(script_path)}")
    print(f"config: {sha256(utilities / 'frameo_utilities.config')}")
    print(f"apk: {apk_path.stat().st_size} bytes versionCode {version_code}")
    print("apk filename created by this program; do not paste it into a shell")
    if mode == "adb":
        print("public key copied to mi86-adb-v2/adbkey.pub")
    print("card not ejected; copy these files to the FAT32 root if --out was not the card")


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
        help="overwrite an existing p_frameo_jb, config, and utility APK in --out",
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
