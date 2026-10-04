"""Offline transport primitives; no live capture or game protocol decoding."""
from dataclasses import dataclass
import socket
import struct


@dataclass(frozen=True)
class Packet:
    timestamp_ns: int
    link_type: int
    data: bytes
    # Npcap runs on little-endian Windows; offline PCAP supplies capture order.
    null_byte_order: str = "<"


@dataclass(frozen=True)
class TcpSegment:
    timestamp_ns: int
    source: tuple
    destination: tuple
    sequence: int
    flags: int
    payload: bytes

    @property
    def payload_sequence(self):
        # SYN occupies a sequence number even when it carries no data.
        return (self.sequence + bool(self.flags & 2)) % 2 ** 32


def decode_tcp(packet):
    """Extract IPv4/TCP; skip ARP/UDP, reject unsupported IPv6/fragments.

    Ethernet, up to two VLAN tags, raw IPv4, and DLT_NULL IPv4 are supported. Checksums are
    deliberately not checked because capture may precede checksum offload.
    This extracts transport bytes only and never interprets game damage.
    """
    data = packet.data
    if packet.link_type == 1:
        if len(data) < 14:
            raise ValueError("Truncated Ethernet header")
        offset, protocol = 14, int.from_bytes(data[12:14], "big")
        for _ in range(2):
            if protocol not in (0x8100, 0x88A8):
                break
            if len(data) < offset + 4:
                raise ValueError("Truncated VLAN header")
            protocol = int.from_bytes(data[offset + 2:offset + 4], "big")
            offset += 4
        if protocol in (0x8100, 0x88A8):
            raise ValueError("More than two VLAN tags are unsupported")
        if protocol == 0x86DD:
            raise ValueError("IPv6 decoding not implemented")
        if protocol != 0x0800:
            return None
        data = data[offset:]
    elif packet.link_type == 0:
        if len(data) < 4:
            raise ValueError("Truncated DLT_NULL header")
        if packet.null_byte_order not in ("<", ">"):
            raise ValueError("Invalid DLT_NULL byte order")
        family, = struct.unpack(packet.null_byte_order + "I", data[:4])
        if family == 24:
            raise ValueError("IPv6 decoding not implemented")
        if family != 2:
            raise ValueError("Unsupported DLT_NULL address family")
        data = data[4:]
    elif packet.link_type != 101:
        raise ValueError("Unsupported link type")
    if not data or data[0] >> 4 != 4:
        raise ValueError("IPv4 packet required")
    if len(data) < 20:
        raise ValueError("Truncated IPv4 header")
    ihl, size = (data[0] & 15) * 4, int.from_bytes(data[2:4], "big")
    if ihl < 20 or not ihl <= size <= len(data):
        raise ValueError("Invalid IPv4 length")
    if data[9] != 6:
        return None
    if int.from_bytes(data[6:8], "big") & 0x3FFF:
        raise ValueError("Fragmented IPv4 TCP requires IP reassembly")
    tcp = data[ihl:size]
    if len(tcp) < 20:
        raise ValueError("Truncated TCP header")
    tcp_length = (tcp[12] >> 4) * 4
    if not 20 <= tcp_length <= len(tcp):
        raise ValueError("Invalid TCP header length")
    src, dst, sequence = struct.unpack("!HHI", tcp[:8])
    return TcpSegment(packet.timestamp_ns, (socket.inet_ntoa(data[12:16]), src),
                      (socket.inet_ntoa(data[16:20]), dst), sequence, tcp[13], tcp[tcp_length:])


def read_pcap(stream):
    """Read classic PCAP records, rejecting partial or snaplen-truncated packets.

    Ethernet (1), raw IP (101), and DLT_NULL (0) are supported; PCAPNG is not.
    Records contain link-layer bytes, NOT decoded AION2 combat events.
    """
    header = stream.read(24)
    formats = {b"\xd4\xc3\xb2\xa1": ("<", 1000), b"\xa1\xb2\xc3\xd4": (">", 1000),
               b"\x4d\x3c\xb2\xa1": ("<", 1), b"\xa1\xb2\x3c\x4d": (">", 1)}
    if len(header) != 24 or header[:4] not in formats:
        raise ValueError("Classic PCAP header required")
    endian, scale = formats[header[:4]]
    major, minor, _, _, snaplen, link = struct.unpack(endian + "HHIIII", header[4:])
    if (major, minor) != (2, 4) or link not in (0, 1, 101) or not 0 < snaplen <= 1024 * 1024:
        raise ValueError("Unsupported PCAP metadata")
    while True:
        record = stream.read(16)
        if not record:
            return
        if len(record) != 16:
            raise ValueError("Truncated packet header")
        seconds, fraction, captured, original = struct.unpack(endian + "IIII", record)
        if captured > snaplen or captured != original or fraction >= 1_000_000_000 // scale:
            raise ValueError("Invalid or snaplen-truncated packet")
        data = stream.read(captured)
        if len(data) != captured:
            raise ValueError("Truncated packet data")
        yield Packet(seconds * 1_000_000_000 + fraction * scale, link, data, endian)


class TcpStream:
    """One directional payload stream. Caller manages flows, SYN/FIN/reset.

    start_sequence is the first payload sequence (SYN sequence + 1).
    Missing bytes block emission. Conflicting overlaps reject atomically.
    Retransmissions older than retained history are discarded, not verified.
    """
    def __init__(self, start_sequence, window=65536):
        if type(start_sequence) is not int or not 0 <= start_sequence < 2 ** 32:
            raise ValueError("Invalid sequence")
        if type(window) is not int or not 1 <= window <= 1024 * 1024:
            raise ValueError("Invalid buffer window")
        self.next_sequence = start_sequence
        self.window = window
        self._pending = {}
        self._history = {}
        self._position = 0

    def feed(self, sequence, payload):
        if type(sequence) is not int or not 0 <= sequence < 2 ** 32 or not isinstance(payload, bytes):
            raise ValueError("Invalid TCP payload")
        delta = (sequence - self.next_sequence + 2 ** 31) % 2 ** 32 - 2 ** 31
        if len(payload) > self.window or delta + len(payload) > self.window:
            raise ValueError("TCP gap/buffer limit exceeded")
        start = self._position + delta
        additions = {}
        for offset, byte in enumerate(payload):
            position = start + offset
            known = self._history.get(position) if position < self._position else self._pending.get(position)
            if known is not None and known != byte:
                raise ValueError("Conflicting TCP retransmission")
            if position >= self._position:
                additions[position] = byte
        self._pending.update(additions)
        result = bytearray()
        while self._position in self._pending:
            byte = self._pending.pop(self._position)
            result.append(byte)
            self._history[self._position] = byte
            self._history.pop(self._position - self.window, None)
            self._position += 1
        self.next_sequence = (self.next_sequence + len(result)) % 2 ** 32
        return bytes(result)
