#!/usr/bin/env python3
"""Offline transaction tests; all firewall commands are file-backed doubles.

Run: python3 scripts/pf1007l-boot/test-firewall.py
These test shell control flow and packet decisions, not Android kernel support.
No adb, network, root privileges, or real iptables commands are used.
"""
import json
import os
from pathlib import Path
import sys


def mock_command():
    path = Path(os.environ["MOCK_STATE"])
    state = json.loads(path.read_text())
    tool = Path(sys.argv[0]).name
    args = sys.argv[1:]
    rc, output = 0, ""
    if tool == "mockctl":
        if args[0] == "checkpoint":
            state["prior"] = json.loads(json.dumps(state["tables"]))
            state["trace"] = []
        elif args[0] == "arm":
            state["fail_at"] = [int(x) for x in args[1:]]
        elif args[0] == "damage":
            table = state["tables"]["iptables"]
            chain = table["INPUT"][0][-1]
            if args[1] == "input":
                table["INPUT"].pop(0)
            elif args[1] == "body":
                table[chain].pop()
            elif args[1] == "precedence":
                table["INPUT"].insert(0, ["-j", "ACCEPT"])
        elif args[0] == "block-delete":
            state["block_delete"] = True
    elif tool == "log":
        state["logs"].append(" ".join(args))
    else:
        state["trace"].append([tool, *args])
        table = state["tables"][tool]
        fail = len(state["trace"]) in state.get("fail_at", [])
        fail |= state.get("missing6", False) and tool == "ip6tables"
        fail |= state.get("no_state", False) and "--state" in args
        fail |= state.get("block_delete", False) and args[0] == "-D"
        if fail:
            rc = 1
        else:
            op = args[0]
            name = args[1] if len(args) > 1 else None
            if op == "-S":
                names = [name] if name else list(table)
                if any(n not in table for n in names):
                    rc = 1
                else:
                    lines = []
                    for n in names:
                        lines.append(f"-P {n} ACCEPT" if n in ("INPUT", "OUTPUT") else f"-N {n}")
                        lines += [f"-A {n} {' '.join(r)}" for r in table[n]]
                    output = "\n".join(lines) + "\n"
            elif op == "-N":
                if name in table:
                    rc = 1
                else:
                    table[name] = []
            elif name not in table:
                rc = 1
            elif op in ("-A", "-I"):
                rule = args[3:] if op == "-I" else args[2:]
                target = rule[rule.index("-j") + 1]
                if target not in ("ACCEPT", "DROP", "RETURN") and target not in table:
                    rc = 1
                elif op == "-I":
                    table[name].insert(int(args[2]) - 1, rule)
                else:
                    table[name].append(rule)
            elif op in ("-C", "-D"):
                rule = args[2:]
                if rule not in table[name]:
                    rc = 1
                elif op == "-D":
                    table[name].remove(rule)
            elif op in ("-F", "-X"):
                referenced = any(
                    (flag in rule and rule[rule.index(flag) + 1] == name)
                    for rules in table.values() for rule in rules for flag in ("-j", "-g")
                )
                if referenced:
                    # Real -F would succeed: record a safety violation rather than protect the code.
                    state["unsafe_flush"].append([tool, op, name])
                if op == "-F":
                    table[name] = []
                elif referenced or table[name] or name in ("INPUT", "OUTPUT"):
                    rc = 1
                else:
                    del table[name]
            else:
                raise AssertionError(f"Unexpected mock command: {args}")
    path.write_text(json.dumps(state))
    sys.stdout.write(output)
    sys.exit(rc)


if Path(sys.argv[0]).name in ("iptables", "ip6tables", "log", "mockctl"):
    mock_command()

import ipaddress
import shlex
import shutil
import subprocess
import tempfile
import unittest

def decision(table, chain, packet):
    """Independent tiny packet interpreter for the rules emitted by the helper."""
    for rule in table[chain]:
        match, target = True, None
        i = 0
        while i < len(rule):
            flag, value = rule[i:i + 2]
            i += 2
            if flag == "-j":
                target = value
            elif flag == "-m":
                if value != "state":
                    raise AssertionError(value)
            elif flag in ("-s", "-d"):
                match &= ipaddress.ip_address(packet[flag]) in ipaddress.ip_network(value, strict=False)
            elif flag == "--state":
                match &= packet.get(flag) in value.split(",")
            else:
                match &= packet.get(flag) == value
        if match:
            if target in ("ACCEPT", "DROP"):
                return target
            if target == "RETURN":
                return None
            result = decision(table, target, packet)
            if result:
                return result
    return "ACCEPT" if chain in ("INPUT", "OUTPUT") else None


class FirewallTest(unittest.TestCase):
    def run_shell(self, commands, *, extra=None, config=None):
        with tempfile.TemporaryDirectory(prefix="frame-firewall-test-") as temp:
            directory = Path(temp)
            for tool in ("iptables", "ip6tables", "log", "mockctl"):
                (directory / tool).symlink_to(Path(__file__).resolve())
            table = {"INPUT": [["-j", "ANDROID_IN"]], "OUTPUT": [["-j", "ANDROID_OUT"]],
                     "ANDROID_IN": [["-j", "RETURN"]], "ANDROID_OUT": [["-j", "RETURN"]]}
            initial = {"tables": {"iptables": table, "ip6tables": table}, "trace": [],
                       "logs": [], "unsafe_flush": []}
            initial.update(extra or {})
            state_path = directory / "state.json"
            state_path.write_text(json.dumps(initial))
            env = dict(os.environ, PATH=f"{directory}:{os.environ['PATH']}", MOCK_STATE=str(state_path))
            env.update(FIREWALL_ALLOW="192.0.2.10:8080 198.51.100.10:443", FIREWALL_DNS="192.0.2.53",
                       ADB_ALLOW="192.0.2.0/24")
            env.update(config or {})
            helper = Path(__file__).parent / "device/frame-firewall.sh"
            result = subprocess.run(["bash", "-u", "-c", f". {shlex.quote(str(helper))}\n{commands}"],
                                    env=env, text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            state = json.loads(state_path.read_text())
            self.assertEqual(state["unsafe_flush"], [], "An active/referenced chain was flushed")
            return state

    def assert_prior_preserved(self, state):
        for tool, before in state["prior"].items():
            for chain, rules in before.items():
                self.assertEqual(state["tables"][tool][chain], rules, (tool, chain))

    def test_allowed_and_denied_packets(self):
        state = self.run_shell("frame_firewall && frame_firewall_healthy")
        packet = {"-i": "wlan0", "-o": "wlan0", "-s": "192.0.2.4", "-d": "192.0.2.10",
                  "-p": "tcp", "--sport": "50000", "--dport": "8080", "--state": "NEW"}
        cases = [
            ("iptables", "OUTPUT", {}, "ACCEPT"),
            ("iptables", "OUTPUT", {"-d": "203.0.113.8"}, "DROP"),
            ("iptables", "OUTPUT", {"-d": "203.0.113.8", "--state": "ESTABLISHED"}, "DROP"),
            ("iptables", "OUTPUT", {"--dport": "443"}, "DROP"),
            ("iptables", "OUTPUT", {"-d": "192.0.2.53", "-p": "udp", "--dport": "53"}, "ACCEPT"),
            ("iptables", "OUTPUT", {"-d": "203.0.113.53", "-p": "udp", "--dport": "53"}, "DROP"),
            ("iptables", "OUTPUT", {"-p": "udp", "--sport": "68", "--dport": "67"}, "ACCEPT"),
            ("iptables", "OUTPUT", {"-p": "udp", "--dport": "123"}, "ACCEPT"),
            ("iptables", "OUTPUT", {"--sport": "5555", "--dport": "50000", "--state": "ESTABLISHED"}, "ACCEPT"),
            ("iptables", "INPUT", {"--dport": "5555"}, "ACCEPT"),
            ("iptables", "INPUT", {"--dport": "5555", "-s": "203.0.113.1", "--state": "ESTABLISHED"}, "DROP"),
            ("iptables", "INPUT", {"-p": "udp", "--sport": "67", "--dport": "68"}, "ACCEPT"),
            ("iptables", "INPUT", {"--state": "ESTABLISHED"}, "ACCEPT"),
            ("iptables", "INPUT", {}, "DROP"),
            ("ip6tables", "INPUT", {"-p": "ipv6-icmp", "icmp-type": "router-advertisement"}, "DROP"),
            ("ip6tables", "OUTPUT", {"--state": "ESTABLISHED"}, "DROP"),
            ("ip6tables", "OUTPUT", {"-o": "lo"}, "ACCEPT"),
            ("ip6tables", "INPUT", {"-i": "lo"}, "ACCEPT"),
        ]
        for tool, chain, changes, expected in cases:
            with self.subTest(tool=tool, chain=chain, changes=changes):
                self.assertEqual(decision(state["tables"][tool], chain, packet | changes), expected)

    def test_invalid_configuration_does_not_touch_firewall(self):
        invalid = [
            {"FIREWALL_ALLOW": x} for x in ("", " ", "host.example:443", "192.0.2.10:0", "192.0.2.10:65536",
                                           "192.0.2.10:0443", "192.0.2.10:*", "[2001:db8::1]:443", "999.1.1.1:80")
        ] + [{"FIREWALL_DNS": x} for x in ("", " ", "dns.example", "1.1.1.1.", "01.1.1.1", "2001:db8::1")]
        invalid += [{"ADB_ALLOW": "192.0.2.0/33"}, {"ADB_ALLOW": "192.0.2.0/*"}]
        for config in invalid:
            with self.subTest(config=config):
                state = self.run_shell("if frame_firewall; then exit 1; fi", config=config)
                self.assertEqual(state["trace"], [])

    def test_missing_family_or_state_support_preserves_rules(self):
        for option in ("missing6", "no_state"):
            with self.subTest(option=option):
                state = self.run_shell("mockctl checkpoint\nif frame_firewall; then exit 1; fi", extra={option: True})
                self.assert_prior_preserved(state)
                self.assertEqual(state["tables"], state["prior"])

    def test_replacement_and_every_activation_failure(self):
        # Find real command boundaries in a successful second generation; fail each operation
        # kind/stage (creation, rule append/check, snapshot, four inserts, post-insert verification).
        baseline = self.run_shell("frame_firewall || exit 1\nmockctl checkpoint\nframe_firewall && frame_firewall_healthy")
        trace = baseline["trace"]
        first_insert = next(i for i, cmd in enumerate(trace) if cmd[1] == "-I")
        # Activation is exactly four inserts followed by four hook/body check pairs.
        # Reads in old-generation cleanup are deliberately non-fatal once the new policy verifies.
        activation_end = first_insert + 4 + 8
        probes = set(range(4))  # initial family/builtin reads
        probes.update(i for i, cmd in enumerate(trace[:activation_end]) if cmd[1] in ("-N", "-I"))
        # Exercise partial rule population and read-back failure in each family.
        for tool in ("iptables", "ip6tables"):
            for op in ("-A", "-C"):
                probes.add(next(i for i, cmd in enumerate(trace) if cmd[:2] == [tool, op]))
        probes.update(i for i in range(first_insert, activation_end) if trace[i][1] == "-S")
        probes.update(i for i in range(first_insert - 4, first_insert))  # staged snapshots
        # Each probe uses its own temporary filesystem and doubles; run four at a time to keep
        # this failure matrix quick without sharing shell state or touching a host firewall.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as workers:
            futures = {index: workers.submit(
                self.run_shell, f"frame_firewall || exit 1\nmockctl checkpoint\nmockctl arm {index + 1}\n"
                "if frame_firewall; then exit 1; fi\nframe_firewall_healthy") for index in sorted(probes)}
            for index, future in futures.items():
                with self.subTest(command=trace[index], index=index + 1):
                    state = future.result()
                    self.assert_prior_preserved(state)
                    self.assertEqual(state["tables"], state["prior"], "rollback left candidate chains/hooks")
        # Normal replacement has one pair per family; Android's original rules survive intact.
        for tool, table in baseline["tables"].items():
            self.assertEqual(len(table), 6)
            self.assertEqual(table["INPUT"][1:], baseline["prior"][tool]["INPUT"][1:])
            self.assertEqual(table["ANDROID_IN"], baseline["prior"][tool]["ANDROID_IN"])

    def test_rollback_delete_failure_retains_referenced_chain_and_reports(self):
        baseline = self.run_shell("frame_firewall || exit 1\nmockctl checkpoint\nframe_firewall")
        # Fail the last insert; then all candidate hook deletions fail persistently.
        index = next(i + 1 for i, cmd in enumerate(baseline["trace"])
                     if cmd[:3] == ["ip6tables", "-I", "OUTPUT"])
        state = self.run_shell(f"frame_firewall || exit 1\nmockctl checkpoint\nmockctl arm {index}\n"
                               "mockctl block-delete\nif frame_firewall; then exit 1; fi")
        for tool, before in state["prior"].items():
            for chain, rules in before.items():
                if chain not in ("INPUT", "OUTPUT"):
                    self.assertEqual(state["tables"][tool][chain], rules)
        self.assertTrue(any("rollback incomplete" in line for line in state["logs"]))
        self.assertTrue(any("protection is unverified" in line for line in state["logs"]))
        # The first candidate stays complete, never emptied while referenced.
        table = state["tables"]["iptables"]
        self.assertEqual(table[table["INPUT"][0][-1]][-1], ["-j", "DROP"])

    def test_old_cleanup_failure_keeps_verified_new_policy(self):
        baseline = self.run_shell("frame_firewall || exit 1\nmockctl checkpoint\nframe_firewall")
        # The first cleanup read immediately precedes its first deletion.
        cleanup_read = next(i for i, cmd in enumerate(baseline["trace"]) if cmd[1] == "-D")
        for fail in ("mockctl block-delete", f"mockctl arm {cleanup_read}"):
            with self.subTest(fail=fail):
                state = self.run_shell(f"frame_firewall || exit 1\nmockctl checkpoint\n{fail}\n"
                                       "frame_firewall && frame_firewall_healthy")
                self.assertTrue(any("old IPv4 cleanup incomplete" in line for line in state["logs"]))
                self.assertEqual(len(state["tables"]["iptables"]["INPUT"]), 3)

    def test_detects_and_repairs_input_body_and_precedence_changes(self):
        for damage in ("input", "body", "precedence"):
            with self.subTest(damage=damage):
                self.run_shell(f"frame_firewall || exit 1\nmockctl damage {damage}\n"
                               "if frame_firewall_healthy; then exit 1; fi\nframe_firewall && frame_firewall_healthy")

    def test_installer_rejects_bad_settings_and_network_adb_before_writes(self):
        source = Path(__file__).parent
        for invalid in (True, False):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                shutil.copytree(source / "device", directory / "device")
                shutil.copyfile(source / "install.sh", directory / "install.sh")
                (directory / "frame-boot.conf").write_text(
                    'FIREWALL=1\nFIREWALL_ALLOW="192.0.2.10:8080"\n'
                    + ('FIREWALL_DNS="bad.example"\n' if invalid else 'FIREWALL_DNS="192.0.2.53"\n'))
                calls = directory / "adb-calls"
                adb = directory / "adb"
                adb.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$MOCK_ADB_CALLS"\n'
                               'printf "192.0.2.2:5555\\n"\n')
                adb.chmod(0o755)
                env = dict(os.environ, PATH=f"{directory}:{os.environ['PATH']}", MOCK_ADB_CALLS=str(calls))
                result = subprocess.run(["bash", str(directory / "install.sh"), "apply"],
                                        env=env, text=True, capture_output=True, timeout=5)
                self.assertNotEqual(result.returncode, 0)
                if invalid:
                    self.assertIn("invalid firewall settings", result.stderr)
                    self.assertFalse(calls.exists())
                else:
                    self.assertIn("not network ADB", result.stderr)
                    self.assertEqual(calls.read_text().splitlines(), ["get-serialno"])

    def test_empty_adb_range_blocks_preexisting_adb(self):
        state = self.run_shell("frame_firewall && frame_firewall_healthy", config={"ADB_ALLOW": ""})
        packet = {"-i": "wlan0", "-p": "tcp", "--dport": "5555", "--state": "ESTABLISHED"}
        self.assertEqual(decision(state["tables"]["iptables"], "INPUT", packet), "DROP")


if __name__ == "__main__":
    unittest.main(verbosity=2)
