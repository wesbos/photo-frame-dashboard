#!/usr/bin/env bash
# Usage: ADB_PRIVATE_KEY=/path/to/adbkey ./connect.sh HOST or HOST:PORT
# Python 3 supervises only a dedicated server started by this invocation.
set -euo pipefail
exec python3 - "$@" <<'PY'
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

if len(sys.argv) != 2:
    sys.exit("Usage: connect.sh HOST or HOST:PORT")
host = sys.argv[1]
if host.startswith("-") or not host:
    sys.exit("Usage: connect.sh HOST or HOST:PORT")
serial = host if ":" in host else host + ":" + os.environ.get("ADB_TCP_PORT", "5555")
key = os.environ.get("ADB_PRIVATE_KEY")
process = None
work = None
log = None
def interrupted(_signum, _frame):
    raise KeyboardInterrupt("connection cancelled")
signal.signal(signal.SIGTERM, interrupted)
signal.signal(signal.SIGINT, interrupted)
try:
    env = dict(os.environ)
    prefix = ["adb"]
    if key:
        if not Path(key).is_file():
            raise RuntimeError("ADB_PRIVATE_KEY is not a regular file")
        # A caller may request an explicit test port; an occupied endpoint is
        # always refused. Otherwise select an unused loopback port.
        probe = socket.socket()
        try:
            requested = int(os.environ.get("ADB_PRIVATE_SERVER_PORT", "0"))
            if not 0 <= requested <= 65535:
                raise ValueError("port range")
            probe.bind(("127.0.0.1", requested))
            port = probe.getsockname()[1]
        finally:
            probe.close()
        work = tempfile.TemporaryDirectory(prefix="frameo-adb-key-")
        home = Path(work.name)
        (home / ".android").mkdir(mode=0o700)
        private = home / ".android/adbkey"
        shutil.copyfile(key, private)
        private.chmod(0o600)
        for name in ("ADB_VENDOR_KEYS", "ADB_SERVER_SOCKET", "ANDROID_ADB_SERVER_PORT", "ANDROID_USER_HOME", "ANDROID_SDK_HOME"):
            env.pop(name, None)
        env["HOME"] = str(home)
        env["ADB_VENDOR_KEYS"] = str(private)
        env["ADB_SERVER_SOCKET"] = f"tcp:127.0.0.1:{port}"
        log = (home / "server.log").open("wb")
        process = subprocess.Popen(["adb", "-L", env["ADB_SERVER_SOCKET"], "nodaemon", "server"],
                                   env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        deadline = time.monotonic() + 10
        while True:
            if process.poll() is not None:
                raise RuntimeError("owned ADB server failed to start")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("owned ADB server startup timed out")
                time.sleep(0.05)
        if process.poll() is not None:
            raise RuntimeError("owned ADB server exited during startup")
        prefix += ["-H", "127.0.0.1", "-P", str(port)]
    def run(args, device=False):
        command = prefix + (["-s", serial] if device else []) + args
        subprocess.run(command, env=env, check=True, timeout=15)
    run(["connect", serial])
    run(["devices", "-l"])
    run(["shell", "id"], device=True)
    run(["shell", "su 0 id"], device=True)
except KeyboardInterrupt:
    print("Connection cancelled", file=sys.stderr)
    sys.exit(130)
except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
    print("Connection failed: " + str(exc), file=sys.stderr)
    sys.exit(1)
finally:
    # Never kill-server: even on startup failure, terminate only our own child.
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    if log:
        log.close()
    if work:
        work.cleanup()
PY
