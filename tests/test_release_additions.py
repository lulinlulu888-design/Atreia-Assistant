import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "localization"))
import build_release_additions as release
from steam_release_review import patterned


class ReleaseReviewTests(unittest.TestCase):
    def test_expression_order_and_duplicates_are_preserved(self):
        masked, tokens = release.mask("Hit {dmg:a} and {dmg:a} for {duration:b}.")
        self.assertEqual(masked, "Hit @0@ and @1@ for @2@.")
        self.assertEqual(release.restore("持续@2@，伤害@0@及@1@。", tokens),
                         "持续{duration:b}，伤害{dmg:a}及{dmg:a}。")

    def test_missing_duplicated_and_extra_expressions_fail(self):
        for text in ("no marker", "@0@ @0@", "@1@"):
            with self.assertRaises(ValueError):
                release.restore(text, ["{damage}"])

    def test_complete_template_match_is_category_scoped(self):
        with patch.object(release, "SKILLS", {"SkillString_reviewed": "造成@0@点伤害。"}), patch.object(release, "KEYED", {}):
            templates = release.templates({"SkillString_reviewed": "Deals {damage:a} damage."})
        self.assertEqual(release.replacement("SkillString_other", "Deals {damage:b} damage.", templates), "造成{damage:b}点伤害。")
        self.assertIsNone(release.replacement("QuestString_other", "Deals {damage:b} damage.", templates))
        self.assertIsNone(release.replacement("SkillString_other", "Deals {damage:b} damage twice.", templates))

    def test_collection_patterns_preserve_rank_and_scope(self):
        self.assertEqual(patterned("String_STR_PERIOD_COLLECTION_test", "Retrieve White Dragon Armorsmith Armor II"), "收集白龙制甲师防具II")
        self.assertIsNone(patterned("QuestString_test", "Retrieve White Dragon Armorsmith Armor II"))
        self.assertIsNone(patterned("String_STR_PERIOD_COLLECTION_test", "Unknown Armor II"))

    def test_item_expiry_is_preserved(self):
        self.assertEqual(patterned("String_STR_ITEM_test", "Resurrection Spiritstone (10 Days) (Bound)"), "复活灵石（10天）（绑定）")
        self.assertIsNone(patterned("String_STR_ITEM_test", "Resurrection Spiritstone (99 Days) (Bound)"))


if __name__ == "__main__":
    unittest.main()
