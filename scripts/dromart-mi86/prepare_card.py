#!/usr/bin/env python3
"""Stage Dromart MI86 SD-card files into a directory.

Publishes only under --out, using private temporary build directories. It does not
mount, format, or eject a card. Point
--out at a folder, then copy that folder onto the FAT32 card as described in
docs/dromart-mi86.md. Passing a card mount as --out writes those files there
and leaves every other file on the card alone.

The APK filename is shell syntax. This program creates it. Do not paste that
name into a shell.

Existing managed leaf entries require --replace (including dangling symlinks).
Linked managed directories are always refused. Build failures preserve --out;
publication failures disarm its config. Insertion needs separate approval: even
the probe's vendor trigger writes adb_keys and restarts ADB.
"""

from __future__ import annotations

import argparse
import base64
import binascii
from contextlib import ExitStack
import hashlib
import os
import secrets
import shutil
import stat
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


DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def preflight(out: Path, replace: bool) -> None:
    """Read-only early refusal, repeated with anchored descriptors before publication."""
    for parent in (out, *out.parents):
        if parent.is_symlink():
            raise SystemExit(f"symlink in output path: {parent}; choose its real path")
    directories = [out, out / "Frameo_utilities", out / "mi86-adb-v2"]
    for path in directories:
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise SystemExit(f"managed directory must be a real directory, not a symlink: {path}")
    leaves = [out / "p_frameo_jb", directories[1] / "frameo_utilities.config",
              directories[1] / APK_NAME, directories[2] / "adbkey.pub"]
    if directories[1].exists():
        if any(path.name not in {"frameo_utilities.config", APK_NAME}
               for path in directories[1].iterdir()):
            raise SystemExit("Frameo_utilities has unrelated/AppleDouble files; preserve them elsewhere before staging")
    for path in leaves:
        if path.name.startswith("._"):
            raise SystemExit(f"remove AppleDouble file {path.name} before staging")
        if path.is_symlink() or path.exists():
            if not replace:
                raise SystemExit(f"card destination already exists: {path}; use --replace explicitly")
            if not path.is_symlink() and not path.is_file():
                raise SystemExit(f"card destination is not a regular file: {path}")


def leaf_check(directory: int, name: str, replace: bool) -> None:
    try:
        entry = os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not replace:
        raise SystemExit(f"card destination already exists: {name}; use --replace explicitly")
    if not (stat.S_ISREG(entry.st_mode) or stat.S_ISLNK(entry.st_mode)):
        raise SystemExit(f"card destination is not a regular file: {name}")


def read_leaf(directory: int, name: str) -> bytes:
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise RuntimeError(f"not a regular card file: {name}")
        return stream.read()


def publish(directory: int, name: str, contents: bytes, replace: bool) -> None:
    """Publish a complete file; os.replace replaces a symlink entry, never its target."""
    temporary = ".mi86-" + secrets.token_hex(16) + ".pending"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        if read_leaf(directory, temporary) != contents:
            raise RuntimeError(f"staged card readback differs: {name}")
        leaf_check(directory, name, replace)
        os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        if read_leaf(directory, name) != contents:
            raise RuntimeError(f"published card readback differs: {name}")
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


def stage(out: Path, mode: str, version_code: int, public_key: Path | None, replace: bool) -> None:
    check_sources()
    out = out.expanduser().absolute()
    preflight(out, replace)
    source = PROBE if mode == "probe" else ENABLE
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != EXPECTED[source]:
        raise SystemExit("payload source changed; no card files written")
    key = None
    # Build/sign/validate privately. A failed build cannot arm or partially replace --out.
    with tempfile.TemporaryDirectory(prefix="mi86-card-build-") as temporary:
        bundle = Path(temporary)
        if mode == "adb":
            if public_key is None:
                raise SystemExit("--mode adb requires --pubkey")
            if public_key.name == "adbkey":
                raise SystemExit("Pass adbkey.pub, not adbkey")
            key = public_key.read_bytes()
            snapshot = bundle / "adbkey.pub"
            snapshot.write_bytes(key)
            check_public_key(snapshot)
        apk_path = bundle / "utility.apk"
        build_apk(apk_path, version_code)
        apk = apk_path.read_bytes()
        if not apk:
            raise SystemExit("built APK is empty")
    preflight(out, replace)
    with ExitStack() as stack:
        def open_directory(name: str | Path, parent: int | None = None) -> int:
            descriptor = os.open(name, DIRECTORY_FLAGS, dir_fd=parent)
            stack.callback(os.close, descriptor)
            return descriptor

        # Anchor every component without following links, including a parent that
        # could have changed since preflight. Descriptors also anchor error cleanup.
        root = open_directory(out.anchor)
        for component in out.parts[1:]:
            try:
                os.mkdir(component, dir_fd=root)
            except FileExistsError:
                pass
            root = open_directory(component, root)

        def child(name: str) -> int:
            try:
                os.mkdir(name, dir_fd=root)
            except FileExistsError:
                pass
            return open_directory(name, root)

        utilities = child("Frameo_utilities")
        key_dir = child("mi86-adb-v2") if key is not None else None
        if key_dir is None:
            try:
                key_dir = open_directory("mi86-adb-v2", root)
            except FileNotFoundError:
                pass
        if any(name not in {"frameo_utilities.config", APK_NAME}
               for name in os.listdir(utilities)):
            raise SystemExit("unexpected utility file appeared; preserve it elsewhere before staging")
        leaf_check(utilities, APK_NAME, replace)
        leaf_check(root, "p_frameo_jb", replace)
        leaf_check(utilities, "frameo_utilities.config", replace)
        if key_dir is not None:
            leaf_check(key_dir, "adbkey.pub", replace)
        config = "frameo_utilities.config"
        # Abort without changing other files if the old trigger cannot be disarmed.
        try:
            os.unlink(config, dir_fd=utilities)
        except FileNotFoundError:
            pass
        try:
            os.stat(config, dir_fd=utilities, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise RuntimeError("trigger still exists; card publication aborted")
        try:
            publish(root, "p_frameo_jb", payload, replace)
            publish(utilities, APK_NAME, apk, replace)
            if key is not None:
                publish(key_dir, "adbkey.pub", key, replace)
            if set(os.listdir(utilities)) != {APK_NAME}:
                raise RuntimeError("unexpected utility file appeared; trigger remains disarmed")
            # Recheck the complete bundle immediately before arming it.
            if read_leaf(root, "p_frameo_jb") != payload or read_leaf(utilities, APK_NAME) != apk:
                raise RuntimeError("card bundle changed before arming")
            if key is not None and read_leaf(key_dir, "adbkey.pub") != key:
                raise RuntimeError("card public key changed before arming")
            publish(utilities, config, CONFIG.encode(), False)
        except BaseException:
            try:
                os.unlink(config, dir_fd=utilities)
            except FileNotFoundError:
                pass
            except OSError as error:
                raise RuntimeError("FAILED TO DISARM CARD; do not insert it in a frame") from error
            raise
    print(f"mode: {mode}")
    print(f"out: {out}")
    print(f"p_frameo_jb: {len(payload)} bytes {hashlib.sha256(payload).hexdigest()}")
    print(f"config: {hashlib.sha256(CONFIG.encode()).hexdigest()}")
    print(f"apk: {len(apk)} bytes versionCode {version_code}")
    print("apk filename created by this program; do not paste it into a shell")
    if mode == "adb":
        print("public key copied to mi86-adb-v2/adbkey.pub")
    print("card not ejected; to prepare the FAT32 card, rerun with its real mount point as --out")
    print("Existing managed files (including symlinks) require --replace; linked directories are refused.")
    print("Obtain owner approval before EVERY insertion: the vendor trigger changes adb_keys and restarts ADB, even in probe mode.")


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
        help="replace existing payload/config/APK/key entries without following leaf symlinks",
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
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"card preparation failed: {error}") from error
