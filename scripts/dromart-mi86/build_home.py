#!/usr/bin/env python3
"""Build the MI86 PersistentHome dex jar locally; no downloads or device commands.

Needs JDK 17 and an installed Android SDK (platform 35, build-tools 36.1.0 by default).
The output directory must not exist. Only source is distributed; no jar is committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from prepare_card import find_sdk

SOURCE = Path(__file__).with_name("PersistentHome.java")


def build(out: Path, sdk: Path, platform: str, build_tools: str) -> dict:
    if out.exists() or out.is_symlink():
        raise SystemExit("Output directory already exists; choose a new --out directory")
    android_jar = sdk / "platforms" / platform / "android.jar"
    d8 = sdk / "build-tools" / build_tools / "d8"
    java_home = os.environ.get("JAVA_HOME")
    javac = str(Path(java_home) / "bin/javac") if java_home else shutil.which("javac")
    if not javac or not Path(javac).is_file():
        raise SystemExit("javac not found; set JAVA_HOME to a JDK 17 installation")
    if not android_jar.is_file() or not d8.is_file():
        raise SystemExit("Install the selected SDK platform/build-tools before building")
    with tempfile.TemporaryDirectory(prefix="mi86-home-") as directory:
        temp = Path(directory)
        classes = temp / "classes"
        classes.mkdir()
        subprocess.run([
            javac, "-source", "8", "-target", "8", "-bootclasspath", str(android_jar),
            "-d", str(classes), str(SOURCE),
        ], check=True)
        jar = temp / "persistent-home.jar"
        subprocess.run([
            str(d8), "--min-api", "23", "--lib", str(android_jar), "--output", str(jar),
            str(classes / "PersistentHome.class"),
        ], check=True)
        with zipfile.ZipFile(jar) as archive:
            if archive.testzip() is not None or not archive.read("classes.dex").startswith(b"dex\n"):
                raise SystemExit("DEX jar verification failed")
        contents = jar.read_bytes()
        manifest = {
            "source": SOURCE.name,
            "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "artifact": jar.name,
            "artifact_bytes": len(contents),
            "artifact_sha256": hashlib.sha256(contents).hexdigest(),
            "min_api": 23,
            "compile_platform": platform,
            "build_tools": build_tools,
        }
        out.mkdir(parents=True, exist_ok=False)
        destination = out / jar.name
        destination.write_bytes(contents)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != manifest["artifact_sha256"]:
            raise SystemExit("Output readback verification failed")
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="new output directory")
    parser.add_argument("--sdk", type=Path, help="installed Android SDK; otherwise use normal SDK discovery")
    parser.add_argument("--platform", default="android-35")
    parser.add_argument("--build-tools", default="36.1.0")
    args = parser.parse_args()
    if args.out.exists() or args.out.is_symlink():
        raise SystemExit("Output directory already exists; choose a new --out directory")
    manifest = build(args.out, args.sdk or find_sdk(), args.platform, args.build_tools)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
