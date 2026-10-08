#!/usr/bin/env python3
"""Build static Linux/AArch64 iw from downloaded official sources; no USB access."""

import concurrent.futures
import hashlib
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "diagnostics/tools/iw-build"
ZIG = BUILD / "zig-aarch64-macos-0.14.1/zig"


def run(args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def compile_files(files, output, includes, definitions=()):
    output.mkdir(exist_ok=True)

    def compile_file(source):
        run([ZIG, "cc", "-target", "aarch64-linux-musl", "-O2", "-D_GNU_SOURCE",
             *definitions, *["-I" + str(path) for path in includes], "-c", source,
             "-o", output / (source.stem + ".o")])

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(compile_file, files))


def main():
    for name, digest in {
        "zig.tar.xz": "39f3dc5e79c22088ce878edc821dedb4ca5a1cd9f5ef915e9b3cc3053e8faefa",
        "iw-6.9.tar.xz": "3f2db22ad41c675242b98ae3942dbf3112548c60a42ff739210f2de4e98e4894",
    }.items():
        if hashlib.sha256((BUILD / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Archive hash mismatch: {name}")
    nl = BUILD / "libnl-tiny"
    commit = subprocess.check_output(["git", "-C", str(nl), "rev-parse", "HEAD"], text=True).strip()
    if commit != "40493a655d8caa2ccf5206dde1e733abe2920432":
        raise RuntimeError("Unexpected libnl-tiny revision")
    names = "attr cache cache_mngt error genl genl_ctrl genl_family genl_mngt handlers msg nl object socket unl".split()
    nl_output = BUILD / "libnl-static"
    compile_files([nl / (name + ".c") for name in names], nl_output, [nl / "include"])
    run([ZIG, "ar", "rcs", nl_output / "libnl-tiny.a",
         *[nl_output / (name + ".o") for name in names]])
    iw = BUILD / "iw-6.9"
    run(["sh", "version.sh", "version.c"], cwd=iw)
    # Equivalent to upstream GNU sed generation, portable to macOS BSD sed.
    entries = []
    for line in (iw / "nl80211.h").read_text().splitlines():
        match = re.match(r"\tNL80211_CMD_([^=,]*),.*", line)
        if match and "reserved" not in match[1].lower():
            entries.append(f'\t[NL80211_CMD_{match[1]}] = "{match[1].lower()}",')
    (iw / "nl80211-commands.inc").write_text("\n".join(entries) + "\n")
    sources = sorted(iw.glob("*.c"))
    output = BUILD / "iw-static"
    compile_files(sources, output, [nl / "include"], ["-DCONFIG_LIBNL20"])
    run([ZIG, "cc", "-target", "aarch64-linux-musl", "-static", "-O2",
         "-Wl,--no-gc-sections", *[output / (source.stem + ".o") for source in sources],
         nl_output / "libnl-tiny.a", "-o", output / "iw"])
    print(output / "iw")
    print("SHA256", hashlib.sha256((output / "iw").read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
