import copy
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'localization'))
from build_clients_20261028 import build, append_variant, PURPLE_REVIEWED
from client_20261028_review import replacement, SKILLS
from build_official_additions import PARAMETERS


class ClientUpdateTests(unittest.TestCase):
    def baseline(self):
        return {'format': 3, 'entries': {}, 'corrections': {}}

    def test_all_reviewed_official_english_fallbacks_are_chinese(self):
        english = {k: pair[0] for k, pair in PURPLE_REVIEWED.items()}
        result, report = build(self.baseline(), {}, {}, english, english, {})
        for key, pair in PURPLE_REVIEWED.items():
            self.assertEqual(result['entries'][key][0]['translation'], pair[1])
        self.assertEqual(report['purple_added_variants'], 7)

    def test_reviewed_source_change_fails(self):
        with self.assertRaisesRegex(ValueError, 'reviewed source changed'):
            build(self.baseline(), {}, {}, {'String_UI_ABYSS_OUTLAND_RESULT_RANK_TITLE_body': 'Rank 2'},
                  {'String_UI_ABYSS_OUTLAND_RESULT_RANK_TITLE_body': 'Rank 2'}, {})

    def test_unknown_steam_text_remains_for_review(self):
        _, report = build(self.baseline(), {'new': 'Unreviewed content'}, {}, {}, {}, {})
        self.assertEqual(report['remaining_review_keys'], ['new'])

    def test_same_key_different_source_does_not_transfer(self):
        _, report = build(self.baseline(), {'k': 'Can delete after 24 hours'}, {},
                          {'k': 'Can delete after 7 days'}, {'k': '7天后可删除'}, {})
        self.assertEqual(report['remaining_review_keys'], ['k'])

    def test_unique_equivalent_source_can_transfer(self):
        result, report = build(self.baseline(), {'renamed': 'Hello'}, {},
                               {'original': 'Hello'}, {'original': '你好'}, {})
        self.assertEqual(report['remaining_review_keys'], [])
        self.assertEqual(result['entries']['renamed'][0]['translation'], '你好')

    def test_ambiguous_equivalent_source_rejected(self):
        _, report = build(self.baseline(), {'renamed': 'Hello'}, {},
                          {'a': 'Hello', 'b': 'Hello'}, {'a': '你好', 'b': '您好'}, {})
        self.assertEqual(report['remaining_review_keys'], ['renamed'])

    def test_existing_review_and_input_are_preserved(self):
        baseline = self.baseline()
        append_variant(baseline, 'k', 'Hello', '已审译文')
        before = copy.deepcopy(baseline)
        result, report = build(baseline, {'k': 'Hello'}, {}, {'k': 'Hello'}, {'k': '其他译文'}, {})
        self.assertEqual(baseline, before)
        self.assertEqual(result['entries'], before['entries'])
        self.assertEqual(report['steam_retained_variants'], 1)

    def test_runtime_parameters_are_not_silently_changed(self):
        with self.assertRaisesRegex(ValueError, 'parameters'):
            append_variant(self.baseline(), 'k', '{0} items', '{1}个道具')

    def test_pinned_skill_requires_full_source_digest(self):
        self.assertIsNone(replacement('SkillString_STR_SKILL_PC_CHANTER_18211230_skill_desc_effect', 'Changed skill'))
        self.assertEqual(len(SKILLS), 4)

    def test_reward_keeps_each_quantity_and_rejects_unknown_items(self):
        translated = replacement('String_STR_ITEM_EVENT', 'Contains rewards that assist Daeva in combat.\n\n1,000 Power Shard (Bound)\n2 Odyle Energy (Bound)')
        self.assertIn('封魂石（绑定）×1,000', translated)
        self.assertIn('奥德能量（绑定）×2', translated)
        self.assertIsNone(replacement('String_STR_ITEM_EVENT', 'Contains rewards that assist Daeva in combat.\n\n99 Unknown Item (Bound)'))


if __name__ == '__main__':
    unittest.main()
