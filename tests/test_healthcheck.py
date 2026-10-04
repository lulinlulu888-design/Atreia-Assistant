import os
import unittest
from healthcheck import packet, check_backend
from transport import decode_tcp


class HealthcheckTests(unittest.TestCase):
    def test_synthetic_packet_has_expected_tcp_fields(self):
        decoded = decode_tcp(packet(b"test", 100, 0x18))
        self.assertEqual(decoded.payload, b"test")
        self.assertEqual(decoded.sequence, 100)
        self.assertEqual(decoded.destination, ("10.0.0.2", 7777))

    @unittest.skipUnless(os.environ.get("ATREIA_BACKEND"), "requires built Rust backend")
    def test_smoke_report_does_not_claim_live_compatibility(self):
        result = check_backend(os.environ["ATREIA_BACKEND"])
        self.assertEqual(result["synthetic_profiles"], ["steam", "purple"])
        self.assertEqual(result["compatibility"], "unverified")
        self.assertFalse(result["real_game_tested"])
        self.assertFalse(result["packet_capture_started"])
