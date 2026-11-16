#!/usr/bin/env python3
"""Verify, stage and run the locally built MI86 Home helper through selected ADB.

Even inspect stages files on the frame: obtain approval before running this tool.
The temporary upload is untrusted and is never used as executable code. No downloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import tempfile
import zipfile
from io import BytesIO

SOURCE = Path(__file__).with_name("PersistentHome.java")
FINGERPRINT = "rockchip/rk312x/rk312x:6.0.1/MXC89K/user.zcx.20250822.060141:user/release-keys"


class HomeError(RuntimeError):
    pass


def local_payload(directory: Path) -> bytes:
    manifest = json.loads((directory / "manifest.json").read_text())
    contents = (directory / "persistent-home.jar").read_bytes()
    expected = {
        "source": SOURCE.name,
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "artifact": "persistent-home.jar",
        "artifact_bytes": len(contents),
        "artifact_sha256": hashlib.sha256(contents).hexdigest(),
        "min_api": 23,
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise HomeError("Build manifest does not match the source/artifact; rebuild locally")
    with zipfile.ZipFile(BytesIO(contents)) as archive:
        if archive.testzip() is not None or not archive.read("classes.dex").startswith(b"dex\n"):
            raise HomeError("Invalid DEX jar")
    return contents


class Adb:
    def __init__(self, serial: str):
        if not serial:
            raise HomeError("An explicit ADB serial is required")
        self.prefix = ["adb", "-s", serial]

    def call(self, *args: str, data: bytes | None = None) -> bytes:
        result = subprocess.run(
            [*self.prefix, *args], input=data, capture_output=True, timeout=60,
        )
        if result.returncode:
            raise HomeError(f"ADB failed ({result.returncode}): {result.stderr.decode(errors='replace')}")
        return result.stdout

    def checked(self, script: str, *, root: bool = True) -> bytes:
        # Android 6 may not report remote exit status. Require a fresh completion
        # suffix, emitted only after success, even when the client returns zero.
        marker = ("\nMI86_OK_" + secrets.token_hex(16) + "\n").encode()
        wrapped = "(\n" + script + "\n) && printf %s " + shlex.quote(marker.decode())
        command = "sh -c " + shlex.quote(wrapped)
        if root:
            command = "su 0 " + command
        output = self.call("exec-out", command)
        if not output.endswith(marker):
            raise HomeError("Remote command did not confirm completion; stop and inspect its state")
        return output[:-len(marker)]


def trusted_ancestry() -> str:
    # /data may be root:system 0771 on this firmware. Neither shell's group
    # nor other users may write an ancestor of the protected directory.
    return """for parent in / /data; do
  [ -d "$parent" ] && [ ! -L "$parent" ] || exit 1
  [ "$(stat -c %u "$parent")" = 0 ] || exit 1
  mode=$(stat -c %a "$parent") && group=$(stat -c %g "$parent") || exit 1
  [ $((0$mode & 0002)) -eq 0 ] || exit 1
  if [ $((0$mode & 0020)) -ne 0 ]; then
    [ "$group" = 0 ] || [ "$group" = 1000 ] || exit 1
  fi
done"""


def protected_directory(directory: str, mode: str = "750", group: str = "1000") -> str:
    return (
        f"[ -d {directory} ] && [ ! -L {directory} ] && "
        f"[ \"$(stat -c '%u %g %a' {directory})\" = '0 {group} {mode}' ]"
    )


def protected_jar(jar: str) -> str:
    return (
        f"[ -f {jar} ] && [ ! -L {jar} ] && "
        f"[ \"$(stat -c '%u %g %a' {jar})\" = '0 1000 640' ]"
    )


def run(serial: str, directory: Path, operation: str) -> bytes:
    if operation not in {"inspect", "set", "clear"}:
        raise HomeError("Operation must be inspect, set or clear")
    contents = local_payload(directory)  # Immutable expected bytes, before device IO.
    adb = Adb(serial)
    identity = adb.checked('[ "$(id -u)" = 0 ] && getprop ro.build.fingerprint')
    if identity.strip() != FINGERPRINT.encode():
        raise HomeError("Firmware fingerprint mismatch; no staging files written")
    token = secrets.token_hex(16)
    protected = "/data/mi86-home-" + token
    jar = protected + "/persistent-home.jar"
    incoming = "/data/local/tmp/mi86-home-" + token + ".jar"
    created = False
    uploaded = False
    attempted = False
    error = None
    output = b""
    try:
        try:
            adb.checked(trusted_ancestry() + f"\numask 077 && mkdir {protected} && "
                        + protected_directory(protected, "700", "0"))
        except (HomeError, OSError, subprocess.SubprocessError) as failure:
            raise HomeError(f"Staging creation unconfirmed; inspect {protected}: {failure}") from failure
        created = True
        # Snapshot bytes avoid rereading a mutable local jar after validation.
        uploaded = True
        with tempfile.TemporaryDirectory(prefix="mi86-home-upload-") as temporary:
            upload = Path(temporary) / "persistent-home.jar"
            upload.write_bytes(contents)
            adb.call("push", str(upload), incoming)
        adb.checked(protected_directory(protected, "700", "0") + " && "
                    f"cp {incoming} {jar} && chown 0:1000 {jar} && chmod 640 {jar} && "
                    + protected_jar(jar))
        readback = adb.checked(protected_directory(protected, "700", "0") + " && "
                               + protected_jar(jar) + f" && cat {jar}")
        if readback != contents:
            raise HomeError("Protected payload readback differs; helper was not executed")
        adb.checked(f"chown 0:1000 {protected} && chmod 750 {protected} && "
                    + protected_directory(protected))
        uid = "0" if operation == "inspect" else "1000"
        attempted = True
        output = adb.checked(trusted_ancestry() + "\n" + protected_directory(protected)
                             + " && " + protected_jar(jar)
                             + f" && su {uid} env CLASSPATH={jar} /system/bin/app_process"
                             + f" /system/bin PersistentHome {operation}")
    except (HomeError, OSError, subprocess.SubprocessError) as failure:
        error = str(failure)
    finally:
        cleanup = []
        if uploaded:
            try:
                adb.checked(f"rm -f {incoming}", root=False)
            except (HomeError, OSError, subprocess.SubprocessError) as failure:
                cleanup.append(f"untrusted upload {incoming}: {failure}")
        if created:
            try:
                # No recursive deletion, no wildcard and no permission broadening.
                adb.checked(f"[ -d {protected} ] && [ ! -L {protected} ] && "
                            f"[ \"$(stat -c %u {protected})\" = 0 ] && "
                            f"rm -f {jar} && rmdir {protected}")
            except (HomeError, OSError, subprocess.SubprocessError) as failure:
                cleanup.append(f"protected staging {protected}: {failure}")
        if cleanup:
            error = (error + "; " if error else "") + "Cleanup failed: " + "; ".join(cleanup)
    if error:
        state = "Helper execution was attempted; inspect Home state before retrying." if attempted else "Helper was not executed."
        raise HomeError(error + "\n" + state)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="explicit ADB target")
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("operation", choices=("inspect", "set", "clear"))
    args = parser.parse_args()
    try:
        sys.stdout.buffer.write(run(args.serial, args.build_dir, args.operation))
    except (HomeError, OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        parser.exit(1, f"run_home: {error}\n")


if __name__ == "__main__":
    main()
