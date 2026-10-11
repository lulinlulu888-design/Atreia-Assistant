import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "localization"))
import build_mainland_corrections as corrections
from reviewed_mainland import reviewed_translation


class MainlandCorrectionTests(unittest.TestCase):
    def test_binds_both_source_and_old_text_and_preserves_inputs(self):
        source = {"ServerName_1_desc": "Israphel", "NpcTalk_1": "Empyrean Lord Marchutan"}
        previous = {"ServerName_1_desc": "伊斯拉斐尔", "NpcTalk_1": "天界之主马库坦"}
        original = copy.deepcopy(previous)
        bundle, preview, report = corrections.build(source, previous)
        self.assertEqual(bundle["format"], 3)
        self.assertEqual(report["corrected_rows"], 2)
        self.assertEqual(preview, {"ServerName_1_desc": "伊斯拉佩尔", "NpcTalk_1": "主神马勒库坦"})
        self.assertEqual(previous, original)
        entry = bundle["corrections"]["ServerName_1_desc"][0]
        self.assertEqual(entry["source_sha256"], corrections.digest("Israphel"))
        self.assertEqual(entry["previous_translation_sha256"], corrections.digest("伊斯拉斐尔"))

    def test_preserves_existing_additions_and_does_not_mutate_them(self):
        original = {"format": 1, "entries": {"x": {"source_sha256": "digest", "translation": "译文"}}}
        saved = copy.deepcopy(original)
        bundle, _, _ = corrections.build({}, {}, original)
        self.assertEqual(bundle["entries"]["x"], [original["entries"]["x"]])
        self.assertEqual(original, saved)
        with self.assertRaises(ValueError):
            corrections.build({}, {}, bundle)

    def test_does_not_claim_uncertain_names_or_technical_brands(self):
        source = {"ServerName_1_desc": "Hithanya", "String_UI_brand": "DLSS", "NpcTalk_1": "Class"}
        bundle, preview, report = corrections.build(source, source)
        self.assertEqual(preview, source)
        self.assertEqual(report["corrected_rows"], 0)

    def test_precise_ui_and_geographic_reviews(self):
        self.assertEqual(reviewed_translation("ServerName_1_desc", "Ishalgen"), "伊斯夏尔肯")
        self.assertIsNone(reviewed_translation("NpcTalk_1", "Sanctum"))
        self.assertIsNone(reviewed_translation("String_UI_1", "Server List Changed"))
        source = {"String_UI_1": 'Step "{1}" of "{0}" Complete'}
        _, preview, _ = corrections.build(source, source)
        self.assertEqual(preview["String_UI_1"], '完成“{0}”的“{1}”阶段')

    def test_context_specific_ui_and_digest_reviews_do_not_leak(self):
        self.assertEqual(reviewed_translation("String_UI_LOBBY_GAMESERVER_LIST_CHECKBUTTON_AVAILABLE_body", "Available"), "可连接")
        self.assertIsNone(reviewed_translation("String_UI_MINIMAP_QUEST_TOOLTIP_ACQUIRE_body", "Available"))
        self.assertIsNone(reviewed_translation("NoteData_Note_Dungeon_D_0021_01_text", "Updated notice"))
        source = "Reached Level 10 of [Ereshkigal's Monolith]\nYou are growing skilled at finding Empyrean Traces."
        expected = "[艾莱休奇卡独石柱]达到10级\n你寻找主神痕迹的本领越发娴熟了。"
        self.assertEqual(reviewed_translation("Title_D_Monolith_004_desc_long", source), expected)

    def test_rejects_missing_keys_reordered_keys_and_unsafe_reviews(self):
        with self.assertRaises(ValueError):
            corrections.build({"a": "a", "b": "b"}, {"b": "b", "a": "a"})
        with self.assertRaises(ValueError):
            corrections.build({"a": "a"}, {})
        with patch.object(corrections, "reviewed_translation", return_value="丢失参数"):
            with self.assertRaisesRegex(ValueError, "parameters"):
                corrections.build({"a": "Hello {0}"}, {"a": "Hello {0}"})
        with patch.object(corrections, "reviewed_translation", return_value="丢失标签"):
            with self.assertRaisesRegex(ValueError, "tags"):
                corrections.build({"a": "<QK>Hello</>"}, {"a": "<QK>Hello</>"})

    def test_preview_is_idempotent(self):
        source = {"ServerName_1_desc": "Nezekan", "String_UI_1": "Server List"}
        _, preview, _ = corrections.build(source, source)
        _, second, report = corrections.build(source, preview)
        self.assertEqual(second, preview)
        self.assertEqual(report["corrected_rows"], 0)


if __name__ == "__main__":
    unittest.main()
