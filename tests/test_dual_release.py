import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "localization"))
from build_dual_release import append_reviewed_steam, digest, load_snapshot, merge


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

    def test_new_shared_key_receives_current_official_translation(self):
        primary = {"format": 3, "entries": {}, "corrections": {}}
        official = {"format": 1, "entries": {"new": variant("New reward", "新奖励")}}
        result, report = merge(primary, official, {"new": "New reward"},
                               {"new": "New reward"}, {})
        self.assertEqual(result["entries"]["new"], [variant("New reward", "新奖励")])
        self.assertEqual(report["protected_steam_pairs"], 0)

    def test_changed_shared_source_is_filled_but_unchanged_source_is_protected(self):
        primary = {"format": 3, "entries": {}, "corrections": {}}
        official = {"format": 1, "entries": {"changed": variant("20 days", "20天"),
                                               "stable": variant("Same", "相同")}}
        source = {"changed": "20 days", "stable": "Same"}
        result, report = merge(primary, official, source, source,
                               {"changed": "10 days", "stable": "Same"})
        self.assertEqual(result["entries"], {"changed": [variant("20 days", "20天")]})
        self.assertEqual(report["protected_steam_pairs"], 1)

    def test_new_shared_source_preserves_existing_reviewed_variant(self):
        primary = {"format": 3, "entries": {"new": [variant("New", "审定译文")]}, "corrections": {}}
        official = {"format": 1, "entries": {"new": variant("New", "官方译文")}}
        result, report = merge(primary, official, {"new": "New"}, {"new": "New"}, {})
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
            for name in ("steam", "purple", "traditional", "reviewed_steam"):
                with self.assertRaises(ValueError):
                    load_snapshot(source, name)

    def test_steam_review_fills_untranslated_shared_title_without_overwriting_reviewed_wording(self):
        result = {"entries": {"title": [variant("Trick or Treat", "Trick or Treat")]}}
        review = {"format": 1, "entries": {"title": variant("Trick or Treat", "不给糖就捣蛋")}}
        report = append_reviewed_steam(result, review, {"title": "Trick or Treat"})
        self.assertEqual(result["entries"]["title"], [variant("Trick or Treat", "不给糖就捣蛋")])
        self.assertEqual(report["replaced_untranslated_variants"], 1)
        review["entries"]["title"]["translation"] = "别的译文"
        with self.assertRaises(ValueError):
            append_reviewed_steam(result, review, {"title": "Trick or Treat"})

    def test_steam_review_rejects_wrong_source_lost_parameters_or_tags(self):
        source = "<desc_point>{value}</> Recovery"
        for text, reviewed_source in (("恢复{value}", source), ("<desc_point>恢复</>", source),
                                      ("<desc_point>{value}</>恢复", "Changed")):
            with self.assertRaises(ValueError):
                append_reviewed_steam({"entries": {}}, {"format": 1, "entries": {"k": variant(reviewed_source, text)}}, {"k": source})

    def test_reviewed_display_name_can_be_localized_but_arbitrary_tag_changes_fail(self):
        review = {"format": 1, "entries": {"k": variant("Open <Red Halloween Candy>", "开启<红色风味万圣节糖果>")}}
        result = {"entries": {}}
        append_reviewed_steam(result, review, {"k": "Open <Red Halloween Candy>"})
        self.assertEqual(len(result["entries"]["k"]), 1)
        with self.assertRaises(ValueError):
            append_reviewed_steam({"entries": {}}, {"format": 1, "entries": {"k": variant("Open <QK>Candy</>", "开启<其他>Candy</>")}}, {"k": "Open <QK>Candy</>"})


if __name__ == "__main__":
    unittest.main()
