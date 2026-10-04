"""Offline transport primitives; no live capture or game protocol decoding."""
from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class Packet:
    timestamp_ns: int
    link_type: int
    data: bytes


def read_pcap(stream):
    """Read classic PCAP records, rejecting partial or snaplen-truncated packets.

    Ethernet (1) and raw IP (101) are supported; PCAPNG/loopback are not yet.
    Records contain link-layer bytes, NOT decoded AION2 combat events.
    """
    header = stream.read(24)
    formats = {b"\xd4\xc3\xb2\xa1": ("<", 1000), b"\xa1\xb2\xc3\xd4": (">", 1000),
               b"\x4d\x3c\xb2\xa1": ("<", 1), b"\xa1\xb2\x3c\x4d": (">", 1)}
    if len(header) != 24 or header[:4] not in formats:
        raise ValueError("Classic PCAP header required")
    endian, scale = formats[header[:4]]
    major, minor, _, _, snaplen, link = struct.unpack(endian + "HHIIII", header[4:])
    if (major, minor) != (2, 4) or link not in (1, 101) or not 0 < snaplen <= 1024 * 1024:
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
        yield Packet(seconds * 1_000_000_000 + fraction * scale, link, data)


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
