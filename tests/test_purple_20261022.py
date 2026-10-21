"""Synthetic client-variant safety checks; no game data required."""
from copy import deepcopy
import hashlib
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "localization"))
from build_purple_20261022 import build


class PurpleUpdateTests(unittest.TestCase):
    def test_audit_ignores_corrections_for_other_client_keys(self):
        try:
            import audit_generated_payload as audit
        except ImportError as error:
            self.skipTest(str(error))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, baseline, corrections, payload = [root / name for name in
                ("source.json", "baseline.json", "corrections.gz", "payload.dat")]
            source.write_text(json.dumps({"present": "Source"}), encoding="utf-8")
            baseline.write_text(json.dumps({"present": "Translation"}), encoding="utf-8")
            corrections.write_bytes(gzip.compress(json.dumps({"corrections": {
                "other-client": [{"source_sha256": "absent"}]}}).encode()))
            payload.write_bytes(b"synthetic")
            with patch.object(audit, "decode", return_value={"present": "Translation"}), \
                    patch.object(audit, "read_manifest", return_value={}):
                report = audit.audit(root / "manifest", payload, source, "purple",
                                     baseline, corrections, source)
            self.assertEqual(report["preserved_released_keys"], 1)

    def test_preserves_existing_variants_corrections_and_unchanged_rows(self):
        digest = hashlib.sha256(b"New chest").hexdigest()
        baseline = {"format": 3, "entries": {"chest": [
            {"source_sha256": "steam-source", "translation": "Steam translation"},
            {"source_sha256": digest, "translation": "Reviewed translation"}]},
            "corrections": {"old": [{"translation": "Reviewed correction"}]}}
        original = deepcopy(baseline)
        result, report = build({"chest": "New chest", "door": "Door"},
                               {"chest": "New chest", "door": "Door", "unused": "Extra"},
                               {"chest": "Old chest", "door": "Door"}, baseline)
        self.assertEqual(baseline, original)
        self.assertEqual(result["entries"], baseline["entries"])
        self.assertEqual(result["corrections"], baseline["corrections"])
        self.assertEqual(report["retained_reviewed_variants"], 1)
        self.assertEqual(report["unused_traditional_keys"], ["unused"])
        self.assertNotIn("door", result["entries"])

    def test_missing_key_and_parameter_changes_are_rejected(self):
        baseline = {"format": 3, "entries": {}, "corrections": {}}
        with self.assertRaises(ValueError):
            build({"key": "Hello"}, {}, {}, baseline)
        with self.assertRaisesRegex(ValueError, "parameter"):
            build({"key": "Hello {name}"}, {"key": "Hello"}, {}, baseline)

    def test_new_variant_is_bound_to_full_source(self):
        result, report = build({"key": "New"}, {"key": "New"}, {"key": "Old"},
                               {"format": 3, "entries": {}, "corrections": {}})
        self.assertEqual(report["added_variants"], 1)
        self.assertEqual(result["entries"]["key"][0]["source_sha256"],
                         hashlib.sha256(b"New").hexdigest())
