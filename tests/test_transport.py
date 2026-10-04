import io
import struct
import unittest
from transport import TcpStream, read_pcap


def capture(endian="<", nano=False):
    magic = 0xA1B23C4D if nano else 0xA1B2C3D4
    return (struct.pack(endian + "IHHIIII", magic, 2, 4, 0, 0, 65536, 1)
            + struct.pack(endian + "IIII", 1, 2, 3, 3) + b"abc")


class TransportTests(unittest.TestCase):
    def test_pcap_endian_and_timestamp_formats(self):
        for endian in ("<", ">"):
            for nano in (False, True):
                packet, = read_pcap(io.BytesIO(capture(endian, nano)))
                self.assertEqual(packet.data, b"abc")
                self.assertEqual(packet.timestamp_ns, 1_000_000_000 + (2 if nano else 2000))

    def test_truncated_files_fail(self):
        data = capture()
        for length in (0, 3, 23, 25, 39, len(data) - 1):
            with self.subTest(length=length), self.assertRaises(ValueError):
                list(read_pcap(io.BytesIO(data[:length])))

    def test_unsupported_and_snaplen_truncation(self):
        with self.assertRaises(ValueError):
            list(read_pcap(io.BytesIO(b"\x0a\x0d\x0d\x0a")))
        for offset, value in ((20, 0), (36, 4), (32, 65537)):
            data = bytearray(capture())
            data[offset:offset + 4] = struct.pack("<I", value)
            with self.assertRaises(ValueError):
                list(read_pcap(io.BytesIO(data)))

    def test_gap_waits_and_retransmissions_do_not_duplicate(self):
        stream = TcpStream(100)
        self.assertEqual(stream.feed(103, b"def"), b"")
        self.assertEqual(stream.feed(100, b"abc"), b"abcdef")
        self.assertEqual(stream.feed(100, b"abcdef"), b"")
        self.assertEqual(stream.feed(104, b"efgh"), b"gh")

    def test_conflicting_overlap_is_atomic(self):
        stream = TcpStream(100)
        stream.feed(103, b"def")
        with self.assertRaises(ValueError):
            stream.feed(100, b"abcX")
        self.assertEqual(stream.feed(100, b"abc"), b"abcdef")
        with self.assertRaises(ValueError):
            stream.feed(105, b"X")

    def test_wraparound(self):
        stream = TcpStream(0xFFFFFFFE)
        self.assertEqual(stream.feed(0, b"cd"), b"")
        self.assertEqual(stream.feed(0xFFFFFFFE, b"ab"), b"abcd")
        self.assertEqual(stream.next_sequence, 2)

    def test_bounded_gap(self):
        stream = TcpStream(0, window=4)
        with self.assertRaises(ValueError):
            stream.feed(4, b"x")
        with self.assertRaises(ValueError):
            stream.feed(0, b"abcde")
        self.assertEqual(stream.feed(0, b"abcd"), b"abcd")
