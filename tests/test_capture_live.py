import unittest
import ctypes as c
import threading
from unittest.mock import Mock
from capture_live import capture_filter, Npcap, Header, CaptureError


class CaptureFilterTests(unittest.TestCase):
    def test_filter_is_limited_to_explicit_game_connection(self):
        self.assertEqual(capture_filter("192.0.2.1", 7777), "ip and tcp and host 192.0.2.1 and port 7777")

    def test_no_arbitrary_filter_injection(self):
        for address in ("any", "192.0.2.1 or port 443", "::1", "", "999.1.1.1"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                capture_filter(address, 7777)
        for port in (0, -1, 65536, "7777", True):
            with self.subTest(port=port), self.assertRaises(ValueError):
                capture_filter("192.0.2.1", port)


class NpcapMockTests(unittest.TestCase):
    """Test adapter control flow only, without a driver or live traffic."""
    def reader(self):
        reader = Npcap.__new__(Npcap)
        reader.devices = lambda: [("fixture-device", "Synthetic adapter")]
        reader.dll = Mock()
        reader.dll.pcap_open_live.return_value = 1
        reader.dll.pcap_datalink.return_value = 1
        reader.dll.pcap_compile.return_value = 0
        reader.dll.pcap_setfilter.return_value = 0
        reader.dll.pcap_setnonblock.return_value = 0
        return reader

    def test_mock_packet_copy_and_cleanup(self):
        reader = self.reader()
        cancelled = threading.Event()
        header = Header(1, 2, 3, 3)
        data = (c.c_ubyte * 3)(97, 98, 99)
        def next_packet(handle, header_out, data_out):
            c.cast(header_out, c.POINTER(c.POINTER(Header)))[0] = c.pointer(header)
            c.cast(data_out, c.POINTER(c.POINTER(c.c_ubyte)))[0] = c.cast(data, c.POINTER(c.c_ubyte))
            cancelled.set()
            return 1
        reader.dll.pcap_next_ex.side_effect = next_packet
        packet, = reader.packets("fixture-device", "192.0.2.1", 7777, cancelled)
        self.assertEqual(packet.data, b"abc")
        self.assertEqual(packet.timestamp_ns, 1_000_002_000)
        self.assertEqual(reader.dll.pcap_open_live.call_args.args[2], 0)  # no promiscuous request
        reader.dll.pcap_close.assert_called_once_with(1)

    def test_filter_failure_stops_before_reading(self):
        reader = self.reader()
        reader.dll.pcap_setfilter.return_value = -1
        with self.assertRaises(CaptureError):
            list(reader.packets("fixture-device", "192.0.2.1", 7777, threading.Event()))
        reader.dll.pcap_next_ex.assert_not_called()
        reader.dll.pcap_freecode.assert_called_once()
        reader.dll.pcap_close.assert_called_once()

    def test_unknown_device_is_not_opened(self):
        reader = self.reader()
        with self.assertRaises(CaptureError):
            list(reader.packets("other", "192.0.2.1", 7777, threading.Event()))
        reader.dll.pcap_open_live.assert_not_called()
