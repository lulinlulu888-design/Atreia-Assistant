import os
import unittest
from healthcheck import packet, check_backend, check_localization
from unittest.mock import Mock
from transport import decode_tcp


class HealthcheckTests(unittest.TestCase):
    def test_localization_smoke_uses_inspect_only_and_requires_verified_state(self):
        engine = Mock()
        engine.execute.return_value = {"ok": True, "state": "not_installed", "engine_version": "2.4.0"}
        self.assertEqual(check_localization(engine), "passed_read_only_fixture")
        self.assertEqual(engine.execute.call_args.args[0], "inspect")
        self.assertEqual(engine.execute.call_args.kwargs, {})
        root = engine.execute.call_args.args[1].root
        self.assertFalse(root.exists())
        engine.execute.return_value["state"] = "installed"
        with self.assertRaises(RuntimeError):
            check_localization(engine)

    def test_synthetic_packet_has_expected_tcp_fields(self):
        decoded = decode_tcp(packet(b"test", 100, 0x18))
        self.assertEqual(decoded.payload, b"test")
        self.assertEqual(decoded.sequence, 100)
        self.assertEqual(decoded.destination, ("10.0.0.2", 7777))

    @unittest.skipUnless(os.environ.get("ATREIA_BACKEND"), "requires built Rust backend")
    def test_smoke_report_does_not_claim_live_compatibility(self):
        result = check_backend(os.environ["ATREIA_BACKEND"])
        self.assertEqual(result["synthetic_profiles"], ["steam", "purple"])
        self.assertEqual(result["synthetic_scoped_loopback_profiles"], ["steam", "purple"])
        self.assertEqual(result["synthetic_auto_group_profiles"], ["steam", "purple"])
        self.assertEqual(result["compatibility"], "unverified")
        self.assertFalse(result["real_game_tested"])
        self.assertFalse(result["packet_capture_started"])
