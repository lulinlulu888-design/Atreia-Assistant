import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "localization"))
from build_dual_release import digest, load_snapshot, merge


def variant(source, translation):
    return {"source_sha256": digest(source), "translation": translation}


class DualReleaseTests(unittest.TestCase):
    def test_preserves_steam_entries_and_corrections_without_mutating_inputs(self):
        primary = {"format": 3, "entries": {"delete": [variant("24 hours", "24小时")]},
                   "corrections": {"delete": [{**variant("24 hours", "24 小时"),
                                               "previous_translation_sha256": digest("24小时")}]}}
        before = copy.deepcopy(primary)
        official = {"format": 1, "entries": {"delete": variant("7 days", "7天"),
                                               "new": variant("PURPLE only", "本端新增")}}
        result, report = merge(primary, official, {"delete": "24 hours"},
                               {"delete": "7 days", "new": "PURPLE only"})
        self.assertEqual(primary, before)
        self.assertEqual(result["corrections"], primary["corrections"])
        self.assertEqual(result["entries"]["delete"], [variant("24 hours", "24小时"), variant("7 days", "7天")])
        self.assertEqual(report["added_purple_variants"], 2)

    def test_never_adds_a_variant_that_could_change_steam_output(self):
        primary = {"format": 3, "entries": {}, "corrections": {}}
        official = {"format": 1, "entries": {"shared": variant("Same", "相同")}}
        result, report = merge(primary, official, {"shared": "Same"}, {"shared": "Same"})
        self.assertEqual(result["entries"], {})
        self.assertEqual(report["protected_steam_pairs"], 1)

    def test_retains_existing_reviewed_same_source_wording(self):
        primary = {"format": 3, "entries": {"p": [variant("Old source", "审核译文")]}, "corrections": {}}
        official = {"format": 1, "entries": {"p": variant("Old source", "官方译文")}}
        result, report = merge(primary, official, {"p": "Different"}, {"p": "Old source"})
        self.assertEqual(result["entries"], primary["entries"])
        self.assertEqual(report["retained_reviewed_pairs"], 1)

    def test_rejects_source_mismatch_and_conflicting_released_variants(self):
        primary = {"format": 3, "entries": {"p": [variant("P", "一"), variant("P", "二")]}, "corrections": {}}
        official = {"format": 1, "entries": {"p": variant("P", "一")}}
        for purple in ({"p": "Changed"}, {"p": "P"}):
            with self.assertRaises(ValueError):
                merge(primary, official, {}, purple)

    def test_unknown_snapshots_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "new.json"
            source.write_text("{}", encoding="utf-8")
            for name in ("steam", "purple", "traditional"):
                with self.assertRaises(ValueError):
                    load_snapshot(source, name)


if __name__ == "__main__":
    unittest.main()
