"""Parse Android dynamic-partition (LP) metadata in a super image.

Usage: lp.py SUPER.img            print geometry, partitions and extents
"""
import hashlib
import struct
import sys

SECTOR = 512
GEOMETRY_MAGIC = 0x616C4467
HEADER_MAGIC = 0x414C5030
RESERVED = 4096
GEOMETRY_SIZE = 4096


def parse(path):
    with open(path, "rb") as f:
        f.seek(RESERVED)
        g = f.read(GEOMETRY_SIZE)
        f.seek(RESERVED + GEOMETRY_SIZE)
        g2 = f.read(GEOMETRY_SIZE)
        magic, gsize = struct.unpack("<LL", g[:8])
        if magic != GEOMETRY_MAGIC:
            raise ValueError("no LP geometry magic")
        gsum = g[8:40]
        if hashlib.sha256(g[:8] + b"\0" * 32 + g[40:gsize]).digest() != gsum:
            raise ValueError("LP geometry checksum mismatch")
        max_size, slots, lbs = struct.unpack("<LLL", g[40:52])
        geom = {"metadata_max_size": max_size, "slot_count": slots, "logical_block_size": lbs,
                "backup_geometry_identical": g == g2}
        metas = []
        base = RESERVED + 2 * GEOMETRY_SIZE
        for slot in range(slots):
            f.seek(base + slot * max_size)
            raw = f.read(max_size)
            metas.append(_parse_meta(raw, slot))
        return geom, metas


def _parse_meta(raw, slot):
    magic, major, minor, hsize = struct.unpack("<LHHL", raw[:12])
    if magic != HEADER_MAGIC:
        return {"slot": slot, "valid": False}
    hsum = raw[12:44]
    if hashlib.sha256(raw[:12] + b"\0" * 32 + raw[44:hsize]).digest() != hsum:
        raise ValueError("LP header checksum mismatch (slot %d)" % slot)
    tsize, = struct.unpack("<L", raw[44:48])
    tsum = raw[48:80]
    tables = raw[hsize : hsize + tsize]
    if hashlib.sha256(tables).digest() != tsum:
        raise ValueError("LP tables checksum mismatch (slot %d)" % slot)
    descs = struct.unpack("<12L", raw[80:128])
    p_off, p_n, p_sz, e_off, e_n, e_sz, g_off, g_n, g_sz, b_off, b_n, b_sz = descs
    extents = []
    for i in range(e_n):
        ns, ttype, tdata, tsrc = struct.unpack("<QLQL", tables[e_off + i * e_sz : e_off + i * e_sz + 24])
        extents.append({"num_sectors": ns, "target_type": ttype, "target_data": tdata, "target_source": tsrc})
    groups = []
    for i in range(g_n):
        name, flags, maxsz = struct.unpack("<36sLQ", tables[g_off + i * g_sz : g_off + i * g_sz + 48])
        groups.append({"name": name.rstrip(b"\0").decode(), "flags": flags, "max_size": maxsz})
    bdevs = []
    for i in range(b_n):
        fls, align, aoff, size, name, flags = struct.unpack(
            "<QLLQ36sL", tables[b_off + i * b_sz : b_off + i * b_sz + 64])
        bdevs.append({"first_logical_sector": fls, "alignment": align, "alignment_offset": aoff,
                      "size": size, "name": name.rstrip(b"\0").decode(), "flags": flags})
    parts = []
    for i in range(p_n):
        name, attrs, first, n, grp = struct.unpack("<36sLLLL", tables[p_off + i * p_sz : p_off + i * p_sz + 52])
        ex = extents[first : first + n]
        parts.append({"name": name.rstrip(b"\0").decode(), "attributes": attrs, "group": groups[grp]["name"],
                      "extents": ex, "size": sum(e["num_sectors"] for e in ex) * SECTOR})
    return {"slot": slot, "valid": True, "version": (major, minor), "partitions": parts, "groups": groups,
            "block_devices": bdevs, "raw_sha256": hashlib.sha256(raw[: hsize + tsize]).hexdigest()}


def partition_extents(path, name, slot=0):
    """Return [(byte_offset_in_super, byte_length), ...] for a logical partition."""
    geom, metas = parse(path)
    for p in metas[slot]["partitions"]:
        if p["name"] == name:
            out = []
            for e in p["extents"]:
                if e["target_type"] != 0 or e["target_source"] != 0:
                    raise ValueError("unsupported extent type for %s: %r" % (name, e))
                out.append((e["target_data"] * SECTOR, e["num_sectors"] * SECTOR))
            return out
    raise KeyError(name)


def main():
    geom, metas = parse(sys.argv[1])
    print("geometry:", geom)
    for m in metas:
        if not m["valid"]:
            print("slot %d: no metadata" % m["slot"])
            continue
        print("slot %d: version %d.%d, tables sha256 %s" % (m["slot"], *m["version"], m["raw_sha256"][:16]))
        for b in m["block_devices"]:
            print("  block device %(name)s: size %(size)d, first_logical_sector %(first_logical_sector)d" % b)
        for g in m["groups"]:
            print("  group %(name)s: max_size %(max_size)d" % g)
        used = 0
        for p in m["partitions"]:
            print("  partition %-10s attrs %d group %-8s size %d" % (p["name"], p["attributes"], p["group"], p["size"]))
            for e in p["extents"]:
                used += e["num_sectors"] * SECTOR
                print("      extent: type %d, super byte offset %d (sector %d), length %d (%d sectors)" % (
                    e["target_type"], e["target_data"] * SECTOR, e["target_data"],
                    e["num_sectors"] * SECTOR, e["num_sectors"]))
        print("  allocated %d bytes" % used)


if __name__ == "__main__":
    main()
