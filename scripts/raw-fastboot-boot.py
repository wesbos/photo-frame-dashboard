#!/usr/bin/env python3
"""Send the exact reviewed legacy diagnostic image to fastboot RAM, then boot.
Dry-run by default. No flash, erase, unlock, or arbitrary command support.
"""
import argparse
import ctypes as C
import hashlib
from pathlib import Path
import struct
import sys

EXPECTED_SHA='d6aac2f324840b0ef5ef66bcd110b9dc5e86309d50d0b94890b3d0ad5b8b9f96'
EXPECTED_SIZE=48423072

class Descriptor(C.Structure):
    _fields_=[('length',C.c_uint8),('type',C.c_uint8),('usb',C.c_uint16),
              ('device_class',C.c_uint8),('subclass',C.c_uint8),('protocol',C.c_uint8),
              ('packet_size',C.c_uint8),('vendor',C.c_uint16),('product',C.c_uint16),
              ('release',C.c_uint16),('manufacturer',C.c_uint8),('product_string',C.c_uint8),
              ('serial',C.c_uint8),('configurations',C.c_uint8)]

class Endpoint(C.Structure):
    _fields_=[('length',C.c_uint8),('type',C.c_uint8),('address',C.c_uint8),
              ('attributes',C.c_uint8),('packet',C.c_uint16),('interval',C.c_uint8),
              ('refresh',C.c_uint8),('sync',C.c_uint8),('extra',C.c_void_p),('extra_length',C.c_int)]

class InterfaceDescriptor(C.Structure):
    _fields_=[('length',C.c_uint8),('type',C.c_uint8),('number',C.c_uint8),
              ('alternate',C.c_uint8),('endpoints_count',C.c_uint8),('class_',C.c_uint8),
              ('subclass',C.c_uint8),('protocol',C.c_uint8),('string',C.c_uint8),
              ('endpoint',C.POINTER(Endpoint)),('extra',C.c_void_p),('extra_length',C.c_int)]

class Interface(C.Structure):
    _fields_=[('alternate',C.POINTER(InterfaceDescriptor)),('count',C.c_int)]

class Configuration(C.Structure):
    _fields_=[('length',C.c_uint8),('type',C.c_uint8),('total',C.c_uint16),
              ('interfaces_count',C.c_uint8),('value',C.c_uint8),('string',C.c_uint8),
              ('attributes',C.c_uint8),('power',C.c_uint8),('interface',C.POINTER(Interface)),
              ('extra',C.c_void_p),('extra_length',C.c_int)]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('image',type=Path)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--boot',action='store_true',help='Actually upload to RAM and send boot')
    mode.add_argument('--query',action='store_true',help='Only query the download limit; no upload or boot')
    args=p.parse_args()
    image=args.image.read_bytes()
    if len(image)!=EXPECTED_SIZE or hashlib.sha256(image).hexdigest()!=EXPECTED_SHA:
        raise ValueError('Image does not match the independently reviewed candidate')
    if image[:4]!=bytes.fromhex('27051956'):raise ValueError('Expected legacy image')
    print('Verified exact legacy image:',len(image),'bytes',flush=True)
    if not (args.boot or args.query):
        print('Dry run; no USB access.');return
    usb=C.CDLL('/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib')
    def bind(name,restype,args):
        fn=getattr(usb,'libusb_'+name);fn.restype=restype;fn.argtypes=args;return fn
    ptr=C.c_void_p
    init=bind('init',C.c_int,[C.POINTER(ptr)])
    exit_=bind('exit',None,[ptr])
    listing=bind('get_device_list',C.c_ssize_t,[ptr,C.POINTER(C.POINTER(ptr))])
    free_list=bind('free_device_list',None,[C.POINTER(ptr),C.c_int])
    desc=bind('get_device_descriptor',C.c_int,[ptr,C.POINTER(Descriptor)])
    config=bind('get_active_config_descriptor',C.c_int,[ptr,C.POINTER(C.POINTER(Configuration))])
    free_config=bind('free_config_descriptor',None,[C.POINTER(Configuration)])
    open_=bind('open',C.c_int,[ptr,C.POINTER(ptr)])
    close=bind('close',None,[ptr])
    claim=bind('claim_interface',C.c_int,[ptr,C.c_int])
    release=bind('release_interface',C.c_int,[ptr,C.c_int])
    bulk=bind('bulk_transfer',C.c_int,[ptr,C.c_ubyte,ptr,C.c_int,C.POINTER(C.c_int),C.c_uint])
    def check(result,operation):
        if result<0:raise RuntimeError(f'{operation}: libusb error {result}')
        return result
    ctx=ptr();devices=C.POINTER(ptr)();handle=ptr();claimed=None
    check(init(C.byref(ctx)),'init')
    try:
        count=check(listing(ctx,C.byref(devices)),'enumerate')
        matches=[]
        for i in range(count):
            d=Descriptor();check(desc(devices[i],C.byref(d)),'descriptor')
            if (d.vendor,d.product)==(0x18d1,0xd00d):matches.append(devices[i])
        if len(matches)!=1:raise RuntimeError(f'Need exactly one 18d1:d00d device, found {len(matches)}')
        cfg=C.POINTER(Configuration)();check(config(matches[0],C.byref(cfg)),'active configuration')
        try:
            interfaces=[]
            for i in range(cfg.contents.interfaces_count):
                intf=cfg.contents.interface[i]
                for j in range(intf.count):
                    alt=intf.alternate[j]
                    if (alt.class_,alt.subclass,alt.protocol,alt.alternate)!=(255,66,3,0):continue
                    ins=[];outs=[]
                    for k in range(alt.endpoints_count):
                        ep=alt.endpoint[k]
                        if ep.attributes&3==2:(ins if ep.address&128 else outs).append(ep.address)
                    if len(ins)==len(outs)==1:interfaces.append((alt.number,ins[0],outs[0]))
            if len(interfaces)!=1:raise RuntimeError('Need exactly one standard fastboot bulk interface')
            number,ep_in,ep_out=interfaces[0]
        finally:free_config(cfg)
        check(open_(matches[0],C.byref(handle)),'open')
        check(claim(handle,number),'claim');claimed=number
        def send(data):
            buf=C.create_string_buffer(data);done=C.c_int()
            check(bulk(handle,ep_out,buf,len(data),C.byref(done),10000),'bulk OUT')
            if done.value!=len(data):raise RuntimeError('Short transfer; aborting without boot')
        def response(expected):
            for _ in range(32):
                buf=C.create_string_buffer(4096);done=C.c_int()
                check(bulk(handle,ep_in,buf,4096,C.byref(done),10000),'bulk IN')
                data=buf.raw[:done.value]
                if len(data)<4:raise RuntimeError('Short fastboot response')
                print('Response:',repr(data[:256]),flush=True)
                if data[:4] in (b'INFO',b'TEXT'):continue
                if data[:4]!=expected:raise RuntimeError(f'Expected {expected!r}, got {data[:256]!r}')
                return data[4:]
            raise RuntimeError('Too many informational responses')
        send(b'getvar:max-download-size');maximum=response(b'OKAY')
        if int(maximum,16)!=0x04000000:raise RuntimeError('Unexpected download capacity')
        if args.query:return
        send(f'download:{len(image):08x}'.encode())
        size=response(b'DATA')
        if len(size)!=8 or int(size,16)!=len(image):raise RuntimeError('Download size mismatch')
        for offset in range(0,len(image),1024*1024):send(image[offset:offset+1024*1024])
        response(b'OKAY')
        print('Uploaded exact image bytes; sending boot.',flush=True)
        send(b'boot');response(b'OKAY')
        print('Boot command acknowledged; running recovery still requires separate verification.',flush=True)
    finally:
        if claimed is not None:release(handle,claimed)
        if handle:close(handle)
        if devices:free_list(devices,1)
        exit_(ctx)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError) as e:
        print('Stopped:',e,file=sys.stderr);sys.exit(1)
