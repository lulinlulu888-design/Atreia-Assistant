import sys
import hashlib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "localization"))
from build_steam_26077854 import build, apply_global_review
from steam_26077854_review import replacement


class Steam26077854ReviewTests(unittest.TestCase):
    def test_achievement_templates_are_scoped_and_exact(self):
        key = "AchievementString_example"
        self.assertEqual(replacement(key, "Collect 3 Types of Unique Expedition Artwork"), "收集3种唯一远征画作")
        self.assertEqual(replacement(key, "Hero's Footsteps VI"), "英雄的足迹VI")
        self.assertEqual(replacement(key, "Clear Draupnir Conquest on Hard 21 times"), "德拉乌伯尼尔征服[困难]完成21次")
        self.assertIsNone(replacement(key, "Clear Draupnir Conquest on Hard 22 times"))
        self.assertIsNone(replacement("QuestString_example", "Hero's Footsteps VI"))
        self.assertIsNone(replacement(key, "Collect 7 Types of Unique Expedition Artwork"))
        self.assertIsNone(replacement(key, "Use a Scroll 5 times {value}"))

    def test_unreviewed_rows_are_reported_and_baseline_is_preserved(self):
        baseline = {"format": 3, "entries": {}, "corrections": {}}
        source = {"AchievementString_a": "Log in 3 times", "AchievementString_b": "Unreviewed text"}
        result, remaining, translated, identifiers = build(source, baseline, list(source))
        self.assertEqual((remaining, translated, identifiers), (["AchievementString_b"], 1, 0))
        self.assertEqual(baseline["entries"], {})
        self.assertEqual(result["entries"]["AchievementString_a"][0]["translation"], "登录3次")

    def test_only_reviewed_server_identifiers_are_skipped(self):
        baseline = {"format": 3, "entries": {}, "corrections": {}}
        source = {"ServerName_1_short_desc": "RUT", "ServerName_2_short_desc": "NEW"}
        _, remaining, translated, identifiers = build(source, baseline, list(source))
        self.assertEqual((remaining, translated, identifiers), (["ServerName_2_short_desc"], 0, 1))

    def test_global_review_composes_previous_binding_and_keeps_other_clients(self):
        digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
        baseline = {"format": 3, "entries": {"other": [{"source_sha256": digest("other"), "translation": "其他"}]}, "corrections": {"NoteData_a": [{"source_sha256": digest("A note"), "previous_translation_sha256": digest("旧的混合译文"), "translation": "中间的译文"}]}}
        record = {"key": "NoteData_a", "source_sha256": digest("A note"), "previous_translation_sha256": digest("中间的译文"), "translation": "完整的笔记译文"}
        result = apply_global_review({"NoteData_a": "A note"}, baseline, [record])
        self.assertEqual(result["entries"], baseline["entries"])
        self.assertEqual(result["corrections"]["NoteData_a"], [{"source_sha256": digest("A note"), "previous_translation_sha256": digest("旧的混合译文"), "translation": "完整的笔记译文"}])
        self.assertEqual(baseline["corrections"]["NoteData_a"][0]["translation"], "中间的译文")
        with self.assertRaises(ValueError):
            apply_global_review({"NoteData_a": "Changed note"}, baseline, [record])

    def test_global_review_rejects_lost_parameters(self):
        digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
        record = {"key": "QuestString_a", "source_sha256": digest("Defeat {npc:a}"), "previous_translation_sha256": digest("old"), "translation": "消灭敌人"}
        with self.assertRaises(ValueError):
            apply_global_review({"QuestString_a": "Defeat {npc:a}"}, {"format": 3, "entries": {}, "corrections": {}}, [record])


if __name__ == "__main__":
    unittest.main()
