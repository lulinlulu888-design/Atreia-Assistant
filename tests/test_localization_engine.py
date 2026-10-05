import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from localization_engine import LocalizationEngine, verify_engine
from localization_paths import inspect_installation, PAK


class LocalizationEngineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        pak = root / PAK
        pak.parent.mkdir(parents=True)
        pak.write_bytes(b"synthetic game bytes")
        self.game = inspect_installation(root, "steam")
        self.engine = LocalizationEngine.__new__(LocalizationEngine)
        self.engine.directory = root
        self.engine.helper = root / "trusted-helper.exe"
        self.engine.engine = root / "trusted-engine.exe"

    def response(self, operation, ok=True, **extra):
        data = {"operation": operation, "ok": ok, "message": "synthetic response", **extra}
        return subprocess.CompletedProcess([], 0, json.dumps(data).encode(), b"")

    def test_writes_require_explicit_consent_for_both_clients(self):
        with patch("localization_engine.subprocess.run") as runner:
            for operation in ("install", "restore"):
                for consent in (False, 1, "yes"):
                    with self.assertRaises(ValueError):
                        self.engine.execute(operation, self.game, consent)
            purple = inspect_installation(self.game.root, "purple")
            with self.assertRaises(ValueError):
                self.engine.execute("install", purple, False)
        runner.assert_not_called()

    def test_purple_uses_selected_client_for_all_operations(self):
        purple = inspect_installation(self.game.root, "purple")
        for operation in ("inspect", "install", "restore"):
            with patch("localization_engine.verify_engine"), patch("localization_engine.subprocess.run", return_value=self.response(operation)) as runner:
                self.engine.execute(operation, purple, consented=operation != "inspect")
            self.assertEqual(runner.call_args.args[0][-3:], [operation, str(purple.root), "purple"])

    def test_write_process_is_not_killed_on_timeout_and_has_exact_arguments(self):
        with patch("localization_engine.verify_engine") as verify, \
                patch("localization_engine.subprocess.run", return_value=self.response("install")) as runner:
            self.engine.execute("install", self.game, True)
        verify.assert_called_once()
        self.assertNotIn("timeout", runner.call_args.kwargs)
        self.assertEqual(runner.call_args.args[0][-3:], ["install", str(self.game.root), "steam"])
        self.assertNotIn("shell", runner.call_args.kwargs)
        self.assertEqual((self.game.root / PAK).read_bytes(), b"synthetic game bytes")

    def test_inspection_has_timeout_and_cancellation_is_not_success(self):
        with patch("localization_engine.verify_engine"), \
                patch("localization_engine.subprocess.run", return_value=self.response("inspect")) as runner:
            self.engine.execute("inspect", self.game)
        self.assertEqual(runner.call_args.kwargs["timeout"], 30)
        with patch("localization_engine.verify_engine"), patch("localization_engine.subprocess.run",
                return_value=self.response("install", ok=False, cancelled=True)):
            self.assertFalse(self.engine.execute("install", self.game, True)["ok"])

    def test_invalid_response_or_engine_hash_is_rejected(self):
        invalid = self.game.root / "unknown-engine.exe"
        invalid.write_bytes(b"unknown program")
        with self.assertRaises(ValueError):
            verify_engine(invalid)
        for response in (self.response("restore"), self.response("install", ok="true"),
                         subprocess.CompletedProcess([], 1, b'{"ok":false,"operation":"install","message":"failure"}', b"")):
            with patch("localization_engine.verify_engine"), \
                    patch("localization_engine.subprocess.run", return_value=response):
                with self.assertRaises((ValueError, RuntimeError)):
                    self.engine.execute("install", self.game, True)

    @unittest.skipUnless(os.environ.get("ATREIA_LOCALIZATION_COMPONENTS"), "requires staged official engine")
    def test_native_inspection_is_read_only_in_isolated_fixture(self):
        engine = LocalizationEngine(os.environ["ATREIA_LOCALIZATION_COMPONENTS"])
        def contents():
            return {str(path.relative_to(self.game.root)): path.read_bytes()
                    for path in self.game.root.rglob("*") if path.is_file()}
        before = contents()
        # A synthetic directory is not a valid language package. Real decoding
        # must reject it, rather than claiming compatibility from its layout.
        with self.assertRaises(RuntimeError):
            engine.execute("inspect", self.game)
        self.assertEqual(contents(), before)
