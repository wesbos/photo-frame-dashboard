#!/usr/bin/env python3
"""Build a local ARM64 legacy multi-image for the documented diagnostic recovery.

No USB operations. Preserves the exact verified kernel and AP6256 gzip ramdisk.
Uses a privately captured live OF tree and removes only stale initrd bounds.
The fourth, zero-filled component provides space for in-place DTB expansion.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zlib

CANDIDATE_SHA = 'e88e7e4a7a37a84cb898ae2b4cb4f4ed9d515ccb4a5a46aad1302347a0db731e'
KERNEL_SHA = '61f8ae942299bdfeed281bed05be6cd1062fadfc84053d380512bde713563266'
DOWNLOAD_BASE = 0x00c00800  # Confirmed from installed U-Boot callback disassembly.
KERNEL_LOAD = 0x06080000
MAX_DOWNLOAD = 0x04000000
WORKSPACE = 0x4000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def align4(n):
    return (n+3)&~3


def tree_digest(root):
    digest = hashlib.sha256()
    count = total = 0
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink(), 'Live tree must not contain symlinks')
        if not p.is_file():
            continue
        name = p.relative_to(root).as_posix().encode()
        content = p.read_bytes()
        require(len(content) <= 1024*1024, 'Unexpectedly large device-tree property')
        count += 1
        total += len(content)
        require(count <= 20000 and total <= 32*1024*1024, 'Unexpectedly large device tree')
        digest.update(struct.pack('>I', len(name))+name+struct.pack('>I',len(content))+content)
    return dict(sha256=digest.hexdigest(), files=count, property_bytes=total)


def ranges_from_reg(content):
    require(len(content)%16 == 0, 'Expected 64-bit address/size cells')
    return [(a,a+s) for a,s in struct.iter_unpack('>QQ',content) if s]


def overlap(a,b):
    return a[0]<b[1] and b[0]<a[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--live-tree', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path, help='Must be new; contains private device data')
    parser.add_argument('--dtc', default='dtc')
    args = parser.parse_args()
    candidate=args.candidate.read_bytes()
    require(sha(candidate)==CANDIDATE_SHA,'Unexpected AP6256 diagnostic source')
    spec=importlib.util.spec_from_file_location('recovery_builder',Path(__file__).with_name('build-diagnostic-recovery.py'))
    recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)
    components,_=recovery.parse_image(candidate)
    kernel,ramdisk=components['kernel'],components['ramdisk']
    require(sha(kernel)==KERNEL_SHA,'Stock kernel mismatch')
    require(kernel[56:60]==b'ARM\x64','Missing ARM64 Image header')
    text_offset,image_size,flags=struct.unpack_from('<QQQ',kernel,8)
    require(text_offset==0x80000 and image_size>=len(kernel) and flags&8,
            'Kernel does not support the verified placement assumptions')
    require((KERNEL_LOAD-text_offset)%0x200000==0,'Kernel base is not 2 MiB aligned')
    source_tree=tree_digest(args.live_tree)
    require(source_tree['files']>=4000,'Incomplete live device tree')
    for prop in ['#address-cells','#size-cells']:
        require((args.live_tree/prop).read_bytes()==struct.pack('>I',2),'Unexpected root cell widths')
    memory=[]
    for p in args.live_tree.glob('memory*/reg'):
        memory += ranges_from_reg(p.read_bytes())
    require(memory==[(0x200000,0x8400000),(0x9400000,0x80000000)],
            'Live memory map differs from reviewed hardware')
    reserved=[]
    for p in args.live_tree.glob('reserved-memory/*/reg'):
        reserved += ranges_from_reg(p.read_bytes())
    args.output_dir.mkdir(mode=0o700,parents=False,exist_ok=False)
    tree=args.output_dir/'working-tree'
    shutil.copytree(args.live_tree,tree)
    removed=[]
    for name in ['linux,initrd-start','linux,initrd-end']:
        p=tree/'chosen'/name
        require(p.is_file(),'Expected stale initrd property missing')
        p.unlink();removed.append('/chosen/'+name)
    dtb_path=args.output_dir/'running-tree.dtb'
    with (args.output_dir/'dtc.log').open('x') as log:
        subprocess.run([args.dtc,'-I','fs','-O','dtb','-o',str(dtb_path),str(tree)],
                       stdout=log,stderr=subprocess.STDOUT,check=True)
    require(tree_digest(args.live_tree)==source_tree,'Source live tree changed during build')
    spec=importlib.util.spec_from_file_location('inspect_backup',Path(__file__).with_name('inspect-backup.py'))
    inspector=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspector)
    dtb=dtb_path.read_bytes();nodes,total=inspector.parse_fdt(dtb)
    require(total==len(dtb) and not any(k.startswith('linux,initrd-') for k in nodes['/chosen']),
            'Stale initrd properties remain')
    # Every exposed live property except the two removals must survive compilation.
    # dtc treats filesystem "name" properties as redundant node names and omits them.
    for p in tree.rglob('*'):
        if not p.is_file() or p.name=='name':continue
        relative=p.relative_to(tree)
        node='/'+'/'.join(relative.parts[:-1])
        if node=='/':node=''
        require(nodes.get(node,{}).get(p.name)==p.read_bytes(),f'Changed tree property: {relative}')
    # Reserve-map values added at runtime are not visible through /proc/device-tree.
    reserve_offset=struct.unpack_from('>I',dtb,16)[0]
    require(dtb[reserve_offset:reserve_offset+16]==bytes(16),'Unexpected compiled reserve map')
    parts=[kernel,ramdisk,dtb,bytes(WORKSPACE)]
    table=struct.pack('>5I',*(len(p) for p in parts),0)
    payload=bytearray(table);layout=[]
    for name,part in zip(['kernel','ramdisk','fdt','fdt-workspace'],parts):
        offset=64+len(payload)
        layout.append(dict(name=name,offset=offset,bytes=len(part),sha256=sha(part),
                           source_address=DOWNLOAD_BASE+offset))
        payload.extend(part)
        payload.extend(bytes(align4(len(payload))-len(payload)))
    require(layout[2]['source_address']%8==0,'ARM64 DTB would not be 8-byte aligned')
    header=bytearray(struct.pack('>7I4B32s',0x27051956,0,0,len(payload),KERNEL_LOAD,KERNEL_LOAD,
                                 zlib.crc32(payload),5,22,4,0,b'Skylight AP6256 diagnostics'))
    struct.pack_into('>I',header,4,zlib.crc32(header))
    image=bytes(header)+payload
    require(len(image)<MAX_DOWNLOAD,'Legacy image exceeds fastboot 64 MiB limit')
    intervals={'download':(DOWNLOAD_BASE,DOWNLOAD_BASE+len(image)),
               'kernel_runtime':(KERNEL_LOAD,KERNEL_LOAD+image_size),
               'ramdisk_in_place':(layout[1]['source_address'],layout[1]['source_address']+len(ramdisk)),
               'fdt_with_growth':(layout[2]['source_address'],layout[2]['source_address']+len(dtb)+0x3000)}
    for name,interval in intervals.items():
        require(any(a<=interval[0]<interval[1]<=b for a,b in memory),f'{name} outside usable RAM')
        require(not any(overlap(interval,r) for r in reserved),f'{name} overlaps reserved memory')
    require(not overlap(intervals['download'],intervals['kernel_runtime']),'Kernel overwrites downloaded image')
    require(intervals['fdt_with_growth'][1]<=intervals['download'][1],'Insufficient in-image FDT workspace')
    require(not overlap(intervals['ramdisk_in_place'],intervals['fdt_with_growth']),
            'FDT growth overlaps ramdisk')
    # Parse the constructed format again, recomputing both legacy CRCs and all lengths.
    stored=struct.unpack('>7I4B32s',image[:64]);check=bytearray(image[:64]);check[4:8]=bytes(4)
    require(zlib.crc32(check)==stored[1] and zlib.crc32(image[64:])==stored[6], 'Legacy CRC mismatch')
    require(stored[3]==len(image)-64 and stored[7:11]==(5,22,4,0),'Legacy header type/size mismatch')
    offset=64+20
    for part in parts:
        require(image[offset:offset+len(part)]==part,'Legacy component differs')
        offset+=align4(len(part))
    require(offset==len(image),'Unexpected legacy image trailing data')
    partial=args.output_dir/'recovery.uimg.partial';partial.write_bytes(image)
    report=dict(status='BUILT_AND_VERIFIED_OFFLINE_NOT_BOOTED',format='legacy-multi',
                candidate_sha256=sha(image),candidate_bytes=len(image),
                source_android_sha256=CANDIDATE_SHA,source_tree=source_tree,
                source_ramdisk_sha256=sha(ramdisk),source_cpio_sha256=sha(gzip.decompress(ramdisk)),
                dtb_properties_removed=removed,components=layout,kernel_text_offset=text_offset,
                kernel_runtime_image_size=image_size,kernel_flags=flags,
                kernel_load=KERNEL_LOAD,kernel_entry=KERNEL_LOAD,memory_intervals=intervals,
                live_memory_ranges=memory,live_reserved_ranges=reserved,
                relocation_assumption='Rockchip bootm_board_start defaults absent initrd_high/fdt_high to all-ones, preserving ramdisk/FDT in-place. Existing runtime environment cannot be read through ordinary fastboot; alternative relocation behavior remains unverified.',
                reserve_map_caveat='Original stock DTB reserve headers were empty. Live OF filesystem does not expose runtime-added reserve-header entries; usable banks and reserved-memory properties were checked.',
                note='Fourth zero component is ignored by Linux multi-image selection and supplies in-place FDT growth space; kernel and gzip ramdisk are bit-identical to verified source. Contains private device identifiers; do not publish images or raw tree.')
    manifest=args.output_dir/'manifest.json.partial';manifest.write_text(json.dumps(report,indent=2)+'\n')
    os.link(partial,args.output_dir/'recovery.uimg');partial.unlink()
    os.link(manifest,args.output_dir/'manifest.json');manifest.unlink()
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,EOFError,struct.error,subprocess.CalledProcessError) as error:
        print(f'Build failed: {error}',file=sys.stderr);sys.exit(1)
