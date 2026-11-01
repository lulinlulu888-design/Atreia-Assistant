from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'localization'))
from reviewed_japanese import reviewed_translation


class ReviewedJapaneseTests(unittest.TestCase):
    def test_known_skill_property_preserves_style_and_order(self):
        key = 'SkillString_STR_SKILL_PC_TEST_skill_spec_effect'
        self.assertEqual(reviewed_translation(key, '<Unique>ノンターゲット|チャージ スキル|移動可能</>'),
                         '<Unique>非锁定|蓄力技能|可移动施放</>')

    def test_unknown_property_and_wrong_context_are_not_guessed(self):
        self.assertIsNone(reviewed_translation('SkillString_STR_SKILL_PC_TEST_skill_spec_effect', '<unique>未知|移動可能</>'))
        self.assertIsNone(reviewed_translation('Quest_title', '<unique>移動可能</>'))

    def test_none_only_in_skill_context(self):
        self.assertEqual(reviewed_translation('SkillString_TEST_skill_desc_effect', 'None'), '无')
        self.assertIsNone(reviewed_translation('NpcTalk_TEST_text', 'None'))

    def test_complete_clauses_preserve_dynamic_parameters_and_quantities(self):
        source = '{se:1:range}m内の最大5体の敵に<chat_combat>{se_dmg:2:min}～{se_dmg:2:max}</>のダメージを与えます。\n\n<chat_combat>[暴走状態]</>\n的中時に[連環拳]の再使用時間が{se:3:time}減少します。\n\nグロッキー ゲージ ダメージ量20'
        result = reviewed_translation('SkillString_TEST_skill_desc_effect', source)
        self.assertIn('对{se:1:range}米范围内最多5名敌人', result)
        self.assertIn('<chat_combat>{se_dmg:2:min}～{se_dmg:2:max}</>', result)
        self.assertIn('冷却时间减少{se:3:time}', result)
        self.assertTrue(result.endswith('失衡值伤害20'))

    def test_one_unknown_clause_rejects_whole_description(self):
        self.assertIsNone(reviewed_translation('SkillString_TEST_skill_desc_effect', 'スキル速度が20%増加します。未知の効果を付与します。'))
        self.assertIsNone(reviewed_translation('SkillString_TEST_skill_desc_effect', 'HP20%吸収§0§'))


if __name__ == '__main__':
    unittest.main()
