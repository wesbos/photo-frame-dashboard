#!/usr/bin/env python3
"""Byte-level diff summary of two same-sized images.

diffsum.py OLD NEW [--block N] [--regions name:start:end,...]
Prints changed byte count and the changed ranges (merged per --block bytes,
default 1 = exact byte runs), each tagged with the region it falls in.
"""
import argparse


def ranges(a, b, block):
    out = []
    n = len(a)
    step = 1 << 20
    for base in range(0, n, step):
        ca, cb = a[base:base + step], b[base:base + step]
        if ca == cb:
            continue
        for o in range(0, len(ca), block):
            if ca[o:o + block] != cb[o:o + block]:
                s = base + o
                if out and out[-1][1] == s:
                    out[-1][1] = s + block
                else:
                    out.append([s, s + block])
    return out


def exact_runs(a, b, lo, hi):
    """first and last differing byte inside [lo, hi)"""
    idx = [i for i in range(lo, min(hi, len(a))) if a[i] != b[i]]
    return idx[0], idx[-1], len(idx)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--block", type=int, default=4096)
    ap.add_argument("--regions", default="")
    ap.add_argument("--max", type=int, default=40)
    a = ap.parse_args()
    old, new = open(a.old, "rb").read(), open(a.new, "rb").read()
    assert len(old) == len(new), "sizes differ: %d vs %d" % (len(old), len(new))
    regions = []
    for r in filter(None, a.regions.split(",")):
        name, s, e = r.split(":")
        regions.append((name, int(s), int(e)))
    rs = ranges(old, new, a.block)
    total = sum(1 for s, e in rs for i in range(s, min(e, len(old))) if old[i] != new[i])
    print("%s -> %s: size %d, %d bytes differ, in %d range(s) of %d-byte blocks covering %d bytes" % (
        a.old, a.new, len(old), total, len(rs), a.block, sum(e - s for s, e in rs)))
    per = {}
    for s, e in rs:
        name = next((n for n, rs_, re_ in regions if rs_ <= s < re_), "-")
        per.setdefault(name, []).append((s, e))
    for name, lst in per.items():
        print("  region %-22s %4d range(s), %8d bytes in changed blocks" % (name, len(lst), sum(e - s for s, e in lst)))
        for s, e in lst[:a.max]:
            f, l, c = exact_runs(old, new, s, e)
            print("      bytes %d-%d (%d differ; first %d, last %d)" % (s, e - 1, c, f, l))
        if len(lst) > a.max:
            print("      ... %d more" % (len(lst) - a.max))


if __name__ == "__main__":
    main()
