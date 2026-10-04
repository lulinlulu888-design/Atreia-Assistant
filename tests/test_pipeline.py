import os
import unittest
import struct
from pipeline import BackendBridge, ConnectionRouter, ScopedConnectionRouter, BackendError
from transport import Packet
from connection_scope import ConnectionScope
from test_tcp_decode import ipv4


class FakeBackend:
    def __init__(self):
        self.received = []
        self.closed = []

    def feed(self, flow, timestamp, payload):
        self.received.append((flow, timestamp, payload))
        return {"status": "no_combat_detected"}

    def close_flow(self, flow, timestamp):
        self.closed.append(flow)
        return {"status": "no_combat_detected"}


class RouterTests(unittest.TestCase):
    def test_exact_scope_filters_unrelated_tcp_before_backend(self):
        backend = FakeBackend()
        scope = ConnectionScope("10.0.0.1", 1234, "10.0.0.2", 7777)
        router = ConnectionRouter(backend, 7777, server_ip="10.0.0.2", scope=scope)
        unrelated = bytearray(ipv4(b"other"))
        unrelated[20:22] = (1235).to_bytes(2, "big")
        self.assertIsNone(router.feed(Packet(0, 101, bytes(unrelated))))
        self.assertEqual(router.segments, 0)
        self.assertEqual(backend.received, [])
        router.feed(Packet(0, 101, ipv4(b"game")))
        self.assertEqual([record[2] for record in backend.received], [b"game"])
        with self.assertRaises(ValueError):
            ConnectionRouter(FakeBackend(), 7778, server_ip="10.0.0.2", scope=scope)

    def test_scoped_tuple_cannot_reopen_after_close_without_new_detection(self):
        scope = ConnectionScope("10.0.0.1", 1234, "10.0.0.2", 7777)
        router = ConnectionRouter(FakeBackend(), 7777, server_ip="10.0.0.2", scope=scope)
        router.feed(Packet(0, 101, ipv4(b"done", 100, 0x19)))
        with self.assertRaisesRegex(BackendError, "重新检测"):
            router.feed(Packet(0, 101, ipv4(b"", 199, 2)))

    def test_scoped_tuple_reuse_without_observed_close_requires_detection(self):
        scope = ConnectionScope("10.0.0.1", 1234, "10.0.0.2", 7777)
        for reverse_only in (False, True):
            backend = FakeBackend()
            router = ConnectionRouter(backend, 7777, server_ip="10.0.0.2", scope=scope)
            data = bytearray(ipv4(b"a", 100))
            if reverse_only:
                data[12:16], data[16:20] = data[16:20], data[12:16]
                data[20:22], data[22:24] = data[22:24], data[20:22]
            router.feed(Packet(0, 101, bytes(data)))
            with self.assertRaisesRegex(BackendError, "重新检测"):
                router.feed(Packet(0, 101, ipv4(b"", 199, 2)))
            self.assertEqual(len(backend.received), 1)

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
        self.assertEqual(backend.closed, [backend.received[0][0]])

    def test_server_ip_is_checked_beyond_native_filter(self):
        backend = FakeBackend()
        router = ConnectionRouter(backend, 7777, server_ip="192.0.2.1")
        self.assertIsNone(router.feed(Packet(0, 101, ipv4())))
        self.assertEqual(backend.received, [])

    def test_closed_stream_retransmission_is_not_counted_again(self):
        backend = FakeBackend()
        router = ConnectionRouter(backend, 7777)
        router.feed(Packet(0, 101, ipv4(b"", 99, 2)))
        final = Packet(0, 101, ipv4(b"abc", 100, 0x19))
        router.feed(final)
        self.assertIsNone(router.feed(final))
        self.assertEqual(len(backend.received), 1)
        self.assertEqual(len(backend.closed), 1)
        router.feed(Packet(0, 101, ipv4(b"", 199, 2)))
        router.feed(Packet(0, 101, ipv4(b"def", 200, 0x19)))
        self.assertEqual(len(backend.received), 2)

    def test_new_initiating_syn_retires_reverse_direction(self):
        backend = FakeBackend()
        router = ConnectionRouter(backend, 7777)
        reverse = bytearray(ipv4(b"a", 500))
        reverse[12:16], reverse[16:20] = reverse[16:20], reverse[12:16]
        reverse[20:22], reverse[22:24] = reverse[22:24], reverse[20:22]
        router.feed(Packet(0, 101, bytes(reverse)))
        token = backend.received[0][0]
        router.feed(Packet(0, 101, ipv4(b"", 99, 2)))
        self.assertEqual(backend.closed, [token])
        self.assertEqual(len(router.flows), 1)

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
    def test_game_connection_group_keeps_streams_separate_and_ignores_outsiders(self):
        payload = bytes.fromhex("0f053878026400d007000032")
        scopes = tuple(ConnectionScope("127.0.0.1", p, "127.0.0.1", 1111) for p in (50000, 50001))
        def sample(port):
            data = bytearray(ipv4(payload))
            data[12:20] = b"\x7f\x00\x00\x01" * 2
            data[20:24] = struct.pack("!HH", port, 1111)
            return Packet(1_000_000_000, 0, struct.pack("<I", 2) + bytes(data))
        for client in ("steam", "purple"):
            with BackendBridge(os.environ["ATREIA_BACKEND"], client) as backend:
                router = ScopedConnectionRouter(backend, scopes)
                self.assertIsNone(router.feed(sample(50002)))
                first = router.feed(sample(50000))
                self.assertEqual(first["targets"][0]["damage"], 50)
                second = router.feed(sample(50001))
                self.assertEqual(second["targets"][0]["damage"], 100)
                self.assertIsNone(router.feed(sample(50000)))
                self.assertEqual(router.diagnostics()["payload_bytes"], 2 * len(payload))
                self.assertEqual(second["compatibility"], "unverified")

    def test_synthetic_loopback_scope_to_backend_for_both_clients(self):
        payload = bytes.fromhex("0f053878026400d007000032")
        scope = ConnectionScope("127.0.0.1", 50000, "127.0.0.1", 1111)
        def loopback_packet(local_port):
            data = bytearray(ipv4(payload))
            data[12:20] = b"\x7f\x00\x00\x01" * 2
            data[20:22] = local_port.to_bytes(2, "big")
            data[22:24] = (1111).to_bytes(2, "big")
            return Packet(1_000_000_000, 0, struct.pack("<I", 2) + bytes(data))
        for client in ("steam", "purple"):
            with BackendBridge(os.environ["ATREIA_BACKEND"], client) as backend:
                router = ConnectionRouter(backend, 1111, server_ip="127.0.0.1", scope=scope)
                self.assertIsNone(router.feed(loopback_packet(50001)))
                snapshot = router.feed(loopback_packet(50000))
                self.assertEqual(snapshot["targets"][0]["damage"], 50)
                self.assertEqual(snapshot["compatibility"], "unverified")
                self.assertIsNone(router.feed(loopback_packet(50000)))
                self.assertEqual(router.payload_bytes, len(payload))

    def test_reset_preserves_tcp_connection_and_starts_new_totals(self):
        payload = bytes.fromhex("0f053878026400d007000032")
        for client in ("steam", "purple"):
            with BackendBridge(os.environ["ATREIA_BACKEND"], client) as backend:
                router = ConnectionRouter(backend, 7777)
                router.feed(Packet(1_000_000_000, 101, ipv4(b"", 99, 2)))
                first = router.feed(Packet(1_000_000_000, 101, ipv4(payload, 100)))
                reset = backend.reset_encounter()
                self.assertEqual(reset["previous_encounter"]["targets"][0]["damage"], 50)
                self.assertGreater(reset["revision"], first["revision"])
                second = router.feed(Packet(2_000_000_000, 101, ipv4(payload, 100 + len(payload))))
                self.assertEqual(second["encounter_id"], 2)
                self.assertEqual(second["targets"][0]["damage"], 50)
                self.assertEqual(second["active_flows"], 1)
                self.assertGreater(second["revision"], reset["revision"])

    def test_many_closed_connections_do_not_exhaust_backend(self):
        payload = bytes.fromhex("0f053878026400d007000032")
        for client in ("steam", "purple"):
            with BackendBridge(os.environ["ATREIA_BACKEND"], client) as backend:
                router = ConnectionRouter(backend, 7777)
                for index in range(40):
                    sequence = 100 + index * 100
                    router.feed(Packet(1_000_000_000, 101, ipv4(b"", sequence - 1, 2)))
                    snapshot = router.feed(Packet(1_000_000_000, 101, ipv4(payload, sequence, 0x19)))
                    self.assertEqual(snapshot["active_flows"], 0)
                self.assertEqual(snapshot["targets"][0]["damage"], 2000)
                self.assertEqual(snapshot["compatibility"], "unverified")

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
