import os
import unittest
from pipeline import BackendBridge, ConnectionRouter
from transport import Packet
from test_tcp_decode import ipv4


class FakeBackend:
    def __init__(self):
        self.received = []

    def feed(self, flow, timestamp, payload):
        self.received.append((flow, timestamp, payload))
        return {"status": "no_combat_detected"}


class RouterTests(unittest.TestCase):
    def test_ordering_retransmission_and_connection_filter(self):
        backend = FakeBackend()
        router = ConnectionRouter(backend, 7777)
        for payload, sequence, flags in ((b"", 99, 2), (b"def", 103, 0x18),
                                         (b"abc", 100, 0x18), (b"abcdef", 100, 0x18)):
            router.feed(Packet(1_000_000, 101, ipv4(payload, sequence, flags)))
        self.assertEqual([r[2] for r in backend.received], [b"abcdef"])
        self.assertEqual(router.partial_streams, 0)
        self.assertIsNone(ConnectionRouter(FakeBackend(), 8888).feed(Packet(0, 101, ipv4())))

    def test_reconnect_gets_new_parser_stream(self):
        backend = FakeBackend()
        router = ConnectionRouter(backend, 7777)
        for sequence in (100, 1000):
            router.feed(Packet(0, 101, ipv4(b"", sequence - 1, 2)))
            router.feed(Packet(0, 101, ipv4(b"x", sequence)))
        self.assertNotEqual(backend.received[0][0], backend.received[1][0])

    def test_server_ip_is_checked_beyond_native_filter(self):
        backend = FakeBackend()
        router = ConnectionRouter(backend, 7777, server_ip="192.0.2.1")
        self.assertIsNone(router.feed(Packet(0, 101, ipv4())))
        self.assertEqual(backend.received, [])

    def test_midstream_and_closed_gaps_are_reported(self):
        router = ConnectionRouter(FakeBackend(), 7777)
        router.feed(Packet(0, 101, ipv4(b"a", 100)))
        router.feed(Packet(0, 101, ipv4(b"c", 102)))
        router.feed(Packet(0, 101, ipv4(b"", 103, 4)))
        self.assertEqual(router.partial_streams, 1)
        self.assertEqual(router.closed_gaps, 1)
        self.assertEqual(router.diagnostics()["pending_bytes"], 0)


@unittest.skipUnless(os.environ.get("ATREIA_BACKEND"), "requires built Rust backend")
class BackendIntegrationTests(unittest.TestCase):
    def test_wire_capture_to_backend_for_both_clients(self):
        # Synthetic protocol record; explicitly not a real client capture.
        payload = bytes.fromhex("0f053878026400d007000032")
        for client in ("steam", "purple"):
            with BackendBridge(os.environ["ATREIA_BACKEND"], client) as backend:
                router = ConnectionRouter(backend, 7777)
                router.feed(Packet(1_000_000_000, 101, ipv4(b"", 99, 2)))
                router.feed(Packet(1_000_000_000, 101, ipv4(payload[:4], 100)))
                snapshot = router.feed(Packet(1_001_000_000, 101, ipv4(payload[4:], 104)))
                self.assertEqual(snapshot["targets"][0]["damage"], 50)
                self.assertEqual(snapshot["client"], client)
                self.assertEqual(snapshot["compatibility"], "unverified")
                self.assertIsNone(router.feed(Packet(1_001_000_000, 101, ipv4(payload, 100))))
