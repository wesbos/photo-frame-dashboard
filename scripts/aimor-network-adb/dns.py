#!/usr/bin/env python3
"""Temporary DNS proxy: redirect only the firmware's vendor command hostname.

Allowlist clients explicitly. Forward other questions to public DNS; never log
question names or response bodies. Run BEFORE changing DNS settings and restore
the original settings BEFORE stopping. No DNS or router settings are changed here.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import socket
import socketserver
import struct
import threading
from server import event, private_ipv4

HOSTNAME = 'imsconnect.efercro.com'
ALTERNATE_HOSTNAME = 'iwsconnect.efercro.com'


def file_clients(path):
    """Read a small owner-managed list of verified frame IPs; reject bad input."""
    with Path(path).open() as handle:
        content = handle.read(4097)
    if len(content) > 4096:
        raise ValueError('Client file too large')
    values = json.loads(content)
    if not isinstance(values, list) or not 1 <= len(values) <= 16:
        raise ValueError('Expected 1 to 16 verified private IPv4 addresses')
    if any(not isinstance(value, str) for value in values):
        raise ValueError('Client addresses must be strings')
    return {private_ipv4(value) for value in values}


def client_allowed(server, peer):
    if peer in server.allowed:
        return True
    path = getattr(server, 'clients_file', None)
    if path is not None:
        try:
            return peer in file_clients(path)
        except (OSError, ValueError, argparse.ArgumentTypeError):
            # A missing, partial or invalid file never grants frame access.
            pass
    return False


def question(packet):
    if len(packet) < 12:
        raise ValueError('Short DNS packet')
    ident, flags, count, *_ = struct.unpack('!6H', packet[:12])
    if flags & 0x8000 or flags & 0x7800 or count != 1:
        raise ValueError('Expected one standard DNS question')
    labels, pos = [], 12
    while True:
        if pos >= len(packet):
            raise ValueError('Truncated question')
        length = packet[pos]
        pos += 1
        if length == 0:
            break
        if length > 63 or pos + length > len(packet):
            raise ValueError('Invalid label')
        labels.append(packet[pos:pos+length].decode('ascii').lower())
        pos += length
        if pos > 267:
            raise ValueError('DNS name too long')
    if pos + 4 > len(packet):
        raise ValueError('Truncated question type')
    kind, cls = struct.unpack('!HH', packet[pos:pos+4])
    return ident, flags, '.'.join(labels), kind, cls, pos+4


def read_exact(conn, size):
    data = bytearray()
    while len(data) < size:
        piece = conn.recv(size-len(data))
        if not piece:
            raise OSError('Truncated DNS stream')
        data.extend(piece)
    return bytes(data)


class Resolver:
    def __init__(self, mac_ip, upstreams=('8.8.8.8', '1.1.1.1'), hostname=HOSTNAME):
        self.mac_ip = ipaddress.IPv4Address(mac_ip).packed
        self.upstreams = upstreams
        self.hostname = hostname

    def reply(self, packet):
        ident, flags, name, kind, cls, end = question(packet)
        response_flags = 0x8080 | (flags & 0x0110)  # QR, RA, original RD/CD
        if name == self.hostname:
            answer = b''
            if cls == 1 and kind == 1:
                answer = b'\xc0\x0c' + struct.pack('!HHIH', 1, 1, 5, 4) + self.mac_ip
            # AAAA and other vendor-command queries get no addresses: no bypass.
            return struct.pack('!6H', ident, response_flags, 1, int(bool(answer)), 0, 0) + packet[12:end] + answer
        for upstream in self.upstreams:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.settimeout(2)
                    sock.connect((upstream, 53))
                    sock.send(packet)
                    reply = sock.recv(65535)
                if len(reply) < 12 or reply[:2] != packet[:2] or not reply[2] & 0x80:
                    continue
                if reply[2] & 0x02:  # TC: retrieve full answer over TCP
                    with socket.create_connection((upstream, 53), timeout=2) as conn:
                        conn.sendall(struct.pack('!H', len(packet)) + packet)
                        reply = read_exact(conn, struct.unpack('!H', read_exact(conn, 2))[0])
                    if len(reply) < 12 or reply[:2] != packet[:2] or not reply[2] & 0x80:
                        continue
                return reply
            except OSError:
                continue
        return struct.pack('!6H', ident, response_flags | 2, 1, 0, 0, 0) + packet[12:end]


class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        if not client_allowed(self.server, self.client_address[0]):
            return
        data, sock = self.request
        try:
            result = self.server.resolver.reply(data)
            if question(data)[2] == self.server.resolver.hostname:
                event('command_host_dns_query', peer=self.client_address[0],
                      query_type=question(data)[3], redirected_to=self.server.bind_ip)
            sock.sendto(result, self.client_address)
        except (ValueError, UnicodeError, OSError):
            return


class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        if not client_allowed(self.server, self.client_address[0]):
            return
        self.request.settimeout(5)
        try:
            packet = read_exact(self.request, struct.unpack('!H', read_exact(self.request, 2))[0])
            reply = self.server.resolver.reply(packet)
            self.request.sendall(struct.pack('!H', len(reply)) + reply)
        except (ValueError, UnicodeError, OSError):
            return


class UDPServer(socketserver.ThreadingUDPServer):
    daemon_threads = True


class TCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', required=True, type=private_ipv4)
    parser.add_argument('--hostname', choices=(HOSTNAME, ALTERNATE_HOSTNAME),
                        default=HOSTNAME,
                        help='Command hostname selected by the verified firmware server mode')
    parser.add_argument('--allow-client', action='append', required=True, type=private_ipv4)
    parser.add_argument('--clients-file', type=Path,
                        help='Reload owner-verified frame IPv4 list for each request')
    parser.add_argument('--port', type=int, default=53)
    parser.add_argument('--udp-only', action='store_true',
                        help='Leave existing TCP DNS listener untouched; serve UDP only')
    args = parser.parse_args()
    if args.clients_file is not None:
        args.clients_file = args.clients_file.resolve()
        try:
            file_clients(args.clients_file)
        except (OSError, ValueError, argparse.ArgumentTypeError) as error:
            parser.error('Invalid client file: {}'.format(error))
    resolver = Resolver(args.bind, hostname=args.hostname)
    if not 1 <= args.port <= 65535:
        parser.error('Port outside bounds')
    with UDPServer((args.bind, args.port), UDPHandler) as udp:
        tcp = None if args.udp_only else TCPServer((args.bind, args.port), TCPHandler)
        for server in (udp, tcp):
            if server is not None:
                server.resolver, server.allowed, server.bind_ip = resolver, set(args.allow_client), args.bind
                server.clients_file = args.clients_file
        # Sudo is needed only to bind port 53. Run DNS handlers as the owner.
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            uid, gid = int(os.environ.get('SUDO_UID', '0')), int(os.environ.get('SUDO_GID', '0'))
            if uid <= 0 or gid <= 0:
                if tcp is not None:
                    tcp.server_close()
                parser.error('Launch through sudo as your normal Mac user')
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
        if tcp is not None:
            threading.Thread(target=tcp.serve_forever, daemon=True).start()
        event('dns_listening', bind=args.bind, port=args.port, allowed_clients=args.allow_client,
              override=args.hostname, ttl_seconds=5, system_dns_changed=False,
              tcp_enabled=tcp is not None, running_uid=os.geteuid() if hasattr(os, 'geteuid') else None)
        if args.clients_file is not None:
            event('dns_reloadable_clients', clients_file=str(args.clients_file),
                  frame_clients=sorted(file_clients(args.clients_file)))
        try:
            udp.serve_forever()
        finally:
            if tcp is not None:
                tcp.shutdown()
                tcp.server_close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        event('dns_stopped')
