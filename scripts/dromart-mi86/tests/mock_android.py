"""Sandbox-only Android command doubles for test_enable_adb.py; never run on a frame."""

from __future__ import annotations

import base64
import fcntl
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

LABEL = "u:object_r:adb_keys_file:s0"


def execute(command: str, args: list[str], stdin: bytes, state: dict, root: Path) -> int:
    def path(value: str) -> Path:
        candidate = Path(value)
        # Reject escapes even if a future production change calls a destructive command.
        candidate.resolve().relative_to(root)
        return candidate

    def once(fault: str) -> bool:
        if fault not in state["faults"] or fault in state["fired"]:
            return False
        state["fired"].append(fault)
        return True

    def metadata(target: Path) -> dict:
        return state["metadata"].setdefault(
            str(target), {"uid": 0, "gid": 0, "mode": "600", "label": LABEL}
        )

    keys = path(state["keys"])
    installed = state["phase"] == "installed"
    if command == "dirname":
        print(path(args[0]).parent)
    elif command == "date":
        print("mock clock")
    elif command == "id":
        print(state["uid"] if args == ["-u"] else f'uid={state["uid"]} gid=0')
    elif command == "getprop":
        if args[0] == "ro.build.fingerprint" and once("fingerprint_read"):
            # A plausible value must not conceal a failed property read.
            print(state["properties"][args[0]])
            return 1
        if args[0] == "persist.adb.tcp.port" and installed and once("property_readback"):
            state["properties"][args[0]] = "unexpected"
        print(state["properties"].get(args[0], ""))
    elif command == "setprop":
        name, value = args
        if value == "5555" and once("set_" + name):
            return 1
        if state["phase"] == "restored" and once("rollback_property"):
            return 1
        state["properties"][name] = value
    elif command in {"stop", "start"}:
        assert args == ["adbd"], args
        if installed and once(command + "_adbd"):
            return 1
        state["properties"]["init.svc.adbd"] = "running" if command == "start" else "stopped"
        if command == "start":
            if installed and once("adbd_start_timeout"):
                state["properties"]["init.svc.adbd"] = "stopped"
            listener = state["properties"]["service.adb.tcp.port"] == "5555"
            if installed and once("listener"):
                listener = False
            for name in state["listeners"]:
                path(name).write_text("0: 00000000:15B3 00000000:0000 0A\n" if listener else "")
    elif command == "mkdir":
        path(args[0]).mkdir()
    elif command == "touch":
        path(args[0]).touch()
    elif command == "rm":
        assert args[0] == "-f", args
        for name in args[1:]:
            target = path(name)
            target.unlink(missing_ok=True)
            state["metadata"].pop(str(target), None)
            if target == keys and installed:
                state["phase"] = "restored"
    elif command == "cp":
        source, dest = map(path, args)
        shutil.copyfile(source, dest)
    elif command == "mv":
        names = args[1:] if args[0] == "-f" else args
        source, dest = map(path, names)
        rollback = ".frameo.rollback." in source.name
        if dest == keys:
            if rollback and once("rollback_replace"):
                return 1
            if not rollback and once("replace_before"):
                return 1
        source_metadata = metadata(source).copy()
        source.replace(dest)
        state["metadata"].pop(str(source), None)
        state["metadata"][str(dest)] = source_metadata
        if dest == keys:
            state["phase"] = "restored" if rollback else "installed"
            if not rollback and once("replace_after"):
                return 1
    elif command == "cmp":
        assert args[0] == "-s", args
        left, right = map(path, args[1:])
        if left == keys and installed and right.name == "adb_keys.merged" and once("key_readback"):
            keys.write_bytes(b"corrupted installed bytes\n")
        return int(left.read_bytes() != right.read_bytes())
    elif command == "mktemp":
        template = path(args[0])
        assert template.name.endswith("XXXXXX"), template
        fd, name = tempfile.mkstemp(prefix=template.name[:-6], dir=template.parent)
        os.close(fd)
        print(name)
    elif command == "stat":
        assert args[:2] == ["-c", "%u %g %a"], args
        target = path(args[2])
        if target == keys and installed and once("metadata_readback"):
            metadata(target)["mode"] = "400"
        m = metadata(target)
        print(m["uid"], m["gid"], m["mode"])
    elif command == "ls":
        assert args[0] == "-Zd", args
        target = path(args[1])
        print(metadata(target)["label"], target)
    elif command in {"chown", "chmod", "chcon"}:
        value, name = args
        m = metadata(path(name))
        if command == "chown":
            m["uid"], m["gid"] = map(int, value.split(":"))
        else:
            m["mode" if command == "chmod" else "label"] = value
    elif command in {"base64", "toybox", "busybox"}:
        selected = "standalone" if command == "base64" else command
        if selected != state["base64_tool"]:
            return 1
        if command != "base64":
            assert args[0] == "base64", args
            args = args[1:]
        if args == ["-d"]:
            sys.stdout.buffer.write(base64.b64decode(stdin))
        else:
            sys.stdout.buffer.write(base64.b64encode(path(args[0]).read_bytes()) + b"\n")
    elif command == "od":
        assert args[:3] == ["-An", "-v", "-tu1"], args
        print(" ".join(map(str, path(args[3]).read_bytes())))
    elif command == "tr":
        assert args == ["-d", "\\n"], args
        sys.stdout.buffer.write(stdin.replace(b"\n", b""))
    elif command == "cat":
        for name in args:
            sys.stdout.buffer.write(path(name).read_bytes())
    elif command == "sync":
        if once("snapshot_sync"):
            return 1
        if once("concurrent_content"):
            keys.write_bytes(b"concurrent edit\n")
        if once("concurrent_metadata"):
            metadata(keys)["mode"] = "400"
        if once("concurrent_creation"):
            keys.write_bytes(b"concurrent creation\n")
    elif command == "sleep":
        pass  # Polling stays deterministic; no real sleep or daemon is involved.
    else:
        raise AssertionError(f"unmocked command: {command}")
    return 0


def main() -> int:
    command = Path(sys.argv[0]).name
    args = sys.argv[1:]
    # Read pipeline input before taking the lock: the producer also uses this mock.
    consumes_stdin = command == "tr" or (command in {"base64", "toybox", "busybox"} and args[-1:] == ["-d"])
    stdin = sys.stdin.buffer.read() if consumes_stdin else b""
    state_file = Path(os.environ["MI86_MOCK_STATE"])
    root = Path(os.environ["MI86_MOCK_ROOT"]).resolve()
    state_file.resolve().relative_to(root)
    # Shell pipelines run mocks concurrently; serialize shared metadata and fault counters.
    with state_file.with_suffix(".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(state_file.read_text())
        state["calls"].append({"command": command, "args": args})
        try:
            return execute(command, args, stdin, state, root)
        finally:
            state_file.write_text(json.dumps(state))


if __name__ == "__main__":
    raise SystemExit(main())
