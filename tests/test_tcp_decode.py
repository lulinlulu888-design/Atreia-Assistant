import io
import struct
import unittest
from transport import Packet, TcpStream, decode_tcp, read_pcap


def ipv4(payload=b"abc", sequence=100, flags=0x18, options=b""):
    tcp = struct.pack("!HHIIBBHHH", 1234, 7777, sequence, 0, 0x50, flags, 4096, 0, 0) + payload
    return (struct.pack("!BBHHHBBH4s4s", 0x45 + len(options) // 4, 0,
                        20 + len(options) + len(tcp), 0, 0x4000, 64, 6, 0,
                        b"\x0a\x00\x00\x01", b"\x0a\x00\x00\x02") + options + tcp)


def ethernet(ip, vlan=False):
    return bytes(12) + (b"\x81\x00\x00\x01\x08\x00" if vlan else b"\x08\x00") + ip


class DecodeTests(unittest.TestCase):
    def test_offline_null_header_uses_capture_byte_order(self):
        for endian in ("<", ">"):
            frame = struct.pack(endian + "I", 2) + ipv4()
            data = struct.pack(endian + "IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65536, 0)
            data += struct.pack(endian + "IIII", 1, 0, len(frame), len(frame)) + frame
            packet, = read_pcap(io.BytesIO(data))
            segment = decode_tcp(packet)
            self.assertEqual(segment.payload, b"abc")
            self.assertEqual(segment.destination, ("10.0.0.2", 7777))

    def test_null_headers_fail_closed_for_unknown_family_and_truncation(self):
        for data in (b"", bytes(3), struct.pack("<I", 24) + bytes(40),
                     struct.pack("<I", 999) + ipv4(), struct.pack("<I", 2),
                     struct.pack("<I", 2) + bytes(40)):
            with self.assertRaises(ValueError):
                decode_tcp(Packet(0, 0, data))
        with self.assertRaisesRegex(ValueError, "byte order"):
            decode_tcp(Packet(0, 0, struct.pack("<I", 2) + ipv4(), "invalid"))

    def test_ethernet_raw_ip_vlan_and_options(self):
        for options in (b"", bytes(4)):
            ip = ipv4(options=options)
            for packet in (Packet(5, 101, ip), Packet(5, 1, ethernet(ip)),
                           Packet(5, 1, ethernet(ip, True) + bytes(10))):
                segment = decode_tcp(packet)
                self.assertEqual(segment.payload, b"abc")
                self.assertEqual(segment.source, ("10.0.0.1", 1234))
                self.assertEqual(segment.destination, ("10.0.0.2", 7777))
                self.assertEqual(segment.sequence, 100)

    def test_syn_consumes_sequence_with_wrap(self):
        segment = decode_tcp(Packet(0, 101, ipv4(b"", 0xFFFFFFFF, 2)))
        self.assertEqual(segment.payload_sequence, 0)

    def test_non_tcp_and_arp_skipped(self):
        udp = bytearray(ipv4())
        udp[9] = 17
        self.assertIsNone(decode_tcp(Packet(0, 101, bytes(udp))))
        self.assertIsNone(decode_tcp(Packet(0, 1, bytes(12) + b"\x08\x06")))

    def test_fragmentation_and_ipv6_fail_explicitly(self):
        fragment = bytearray(ipv4())
        fragment[6:8] = b"\x20\x00"
        for packet in (Packet(0, 101, bytes(fragment)),
                       Packet(0, 1, bytes(12) + b"\x86\xdd" + bytes(40))):
            with self.assertRaises(ValueError):
                decode_tcp(packet)

    def test_bad_header_lengths_and_truncation(self):
        for length in (0, 19, 25, 39):
            with self.assertRaises(ValueError):
                decode_tcp(Packet(0, 101, ipv4()[:length]))
        for offset, value in ((0, 0x44), (32, 0x40), (32, 0xF0)):
            data = bytearray(ipv4())
            data[offset] = value
            with self.assertRaises(ValueError):
                decode_tcp(Packet(0, 101, bytes(data)))

    def test_pcap_to_ordered_payload_without_duplicate(self):
        data = struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65536, 1)
        packets = (ipv4(b"", 99, 2), ipv4(b"def", 103),
                   ipv4(b"abc", 100), ipv4(b"abcdef", 100))
        for index, ip in enumerate(packets):
            frame = ethernet(ip)
            data += struct.pack("<IIII", index + 1, 0, len(frame), len(frame)) + frame
        stream, output = None, bytearray()
        for packet in read_pcap(io.BytesIO(data)):
            segment = decode_tcp(packet)
            if segment.flags & 2:
                stream = TcpStream(segment.payload_sequence)
            output.extend(stream.feed(segment.payload_sequence, segment.payload))
        self.assertEqual(bytes(output), b"abcdef")
