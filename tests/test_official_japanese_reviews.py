from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'localization'))
from official_japanese_reviews import propose
from reviewed_japanese import reviewed_translation, reviewed_wing_stats, reviewed_item_stats


class OfficialJapaneseReviewTests(unittest.TestCase):
    def test_evasion_review_retains_current_cap_and_markup(self):
        key = 'String_UI_desc_Evasion_body'
        jp = '攻撃を回避するとダメージを受けません。\n回避率は最大<Mythic>30%</>です。'
        reviews, rejected = propose({key: 'Evasion'}, {key: jp}, {key: 'Evasion'},
                                    {key: '回避率最多<Mythic>50%</>。'}, {}, {})
        self.assertFalse(rejected)
        self.assertIn('<Mythic>30%</>', reviews[key]['translation'])
        self.assertNotIn('50%', reviews[key]['translation'])
        self.assertIsNone(reviewed_translation(key, jp + '\n未知の説明。'))

    def test_title_review_preserves_name_and_replaces_all_outdated_attributes(self):
        key = 'String_STR_ITEM_TITLE_L_TEST_DESC_body'
        ja = '[空間を支配する者]のタイトルを獲得します。\n\n[保有効果]\nPvEダメージ耐性：1.0%\n\n[装着効果]\n追加防御力：340\nHP：1,000'
        own = '获得[空间支配者]称号。\n\n[持有效果]\n精神力20'
        text = reviewed_item_stats(key, ja, own)
        self.assertIn('获得[空间支配者]称号。', text)
        self.assertIn('PvE伤害抗性：1.0%', text)
        self.assertIn('生命力：1,000', text)
        self.assertNotIn('精神力', text)
        self.assertIsNone(reviewed_item_stats(key, ja.replace('HP：1,000', '未知：1,000'), own))

    def test_wing_stat_review_uses_japanese_values_and_all_labels(self):
        key = 'String_STR_ITEM_WING_L_TEST_DESC_body'
        ja = '[妖精の夢の翼(刻印)]を獲得します。\n\n[装着効果]\nHP：400\n[保有効果]\n追加命中：20\nPvPダメージ耐性1.00%'
        own = '获得[妖精之梦翅膀]。\n\n[装备效果]\n生命力：200'
        result = reviewed_wing_stats(key, ja, own)
        self.assertIn('获得[妖精之梦翅膀（绑定）]。', result)
        self.assertIn('生命力：400', result)
        self.assertIn('额外命中：20', result)
        self.assertIn('PvP伤害抗性：1.00%', result)
        self.assertIsNone(reviewed_wing_stats(key, ja + '\n新属性：5', own))
        self.assertIsNone(reviewed_wing_stats(key, ja.replace('400', '{value}'), own))
        self.assertIsNone(reviewed_wing_stats(key, ja.replace('[保有効果]', '[未知]'), own))
        reviews, _ = propose({key: 'Changed wing'}, {key: ja}, {key: 'Old wing'}, {key: own}, {}, {})
        self.assertNotIn(key, reviews)

    def test_authored_ui_labels_preserve_values_and_reject_changed_source(self):
        key = 'String_UI_NPCSHOP_ITEMLIST_BUTTON_ADDMAX79_body'
        self.assertEqual(reviewed_translation(key, 'MAX 79.9%'), '最大79.9%')
        self.assertIsNone(reviewed_translation(key, 'MAX unknown'))
        self.assertIsNone(reviewed_translation('NpcTalk_example', 'HERO'))
        message = 'Message_MSG_GET_VEHICLE_CREATURE_SOUL_POINT_body'
        self.assertEqual(reviewed_translation(message, '魂結晶を{1}個獲得しました。'), '获得了{1}个灵魂结晶。')
        self.assertIsNone(reviewed_translation(message, '魂結晶を{0}個獲得しました。'))

    def test_source_mismatch_never_reuses_same_key(self):
        reviews, rejected = propose({'a': 'New'}, {'a': '新'}, {}, {}, {'a': 'Old'}, {'a': '舊'})
        self.assertFalse(reviews)
        self.assertEqual(rejected[0]['reason'], 'official_english_sources_differ')

    def test_existing_mainland_translation_is_not_replaced(self):
        reviews, rejected = propose({'a': 'Siel'}, {'a': 'シエル'}, {'a': 'Siel'}, {'a': '希埃尔'}, {'a': 'Siel'}, {'a': '西爾'})
        self.assertEqual(reviews, {})
        self.assertEqual(rejected, [])

    def test_official_source_is_converted_with_mainland_glossary(self):
        reviews, rejected = propose({'a': 'Server'}, {'a': 'サーバー'}, {}, {}, {'a': 'Server'}, {'a': '伺服器'})
        self.assertFalse(rejected)
        self.assertEqual(reviews['a']['translation'], '服务器')
        self.assertEqual(reviews['a']['provenance'], 'local_official_tw')

    def test_japanese_tokens_and_numbers_are_required(self):
        for japanese, traditional, expected in [('{pcname} 3回', '3次', 'japanese_runtime_signature_differs'),
                                                 ('3回', '5次', 'japanese_numbers_differ')]:
            reviews, rejected = propose({'a': 'Example'}, {'a': japanese}, {}, {}, {'a': 'Example'}, {'a': traditional})
            self.assertFalse(reviews)
            self.assertEqual(rejected[0]['reason'], expected)

    def test_number_only_source_variant_is_bound_to_japanese_values(self):
        reviews, rejected = propose({'a': 'Complete 5 times'}, {'a': '3回完了'}, {}, {},
                                    {'a': 'Complete 3 times'}, {'a': '完成3次'})
        self.assertFalse(rejected)
        self.assertEqual(reviews['a']['translation'], '完成3次')
        self.assertEqual(reviews['a']['source_match'], 'same_english_prose_parameter_or_number_difference')
        reviews, rejected = propose({'a': 'Complete 5 times'}, {'a': '3回完了'}, {}, {},
                                    {'a': 'Purchase 3 times'}, {'a': '购买3次'})
        self.assertFalse(reviews)
        self.assertEqual(rejected[0]['reason'], 'official_english_sources_differ')

    def test_hidden_cube_term_does_not_rename_regular_backpack(self):
        reviews, _ = propose({'a': 'Hidden Cube'}, {'a': '隠されたキューブ'}, {}, {}, {'a': 'Hidden Cube'}, {'a': '隱藏背包'})
        self.assertEqual(reviews['a']['translation'], '隐藏宝箱')
        reviews, _ = propose({'a': 'Backpack'}, {'a': 'バッグ'}, {}, {}, {'a': 'Backpack'}, {'a': '背包'})
        self.assertEqual(reviews['a']['translation'], '背包')

    def test_missing_global_english_can_use_current_official_tw_with_matching_japanese_parameters(self):
        reviews, rejected = propose({'a': '???'}, {'a': '{pcname}、こんにちは。'}, {'a': '???'}, {'a': '???'},
                                    {'a': 'Hello, {pcname}.'}, {'a': '{pcname}，你好。'})
        self.assertFalse(rejected)
        self.assertEqual(reviews['a']['translation'], '{pcname}，你好。')
        self.assertEqual(reviews['a']['source_match'], 'english_unavailable_official_japanese_and_tw_key_runtime_and_values')
        reviews, rejected = propose({'a': '???'}, {'a': '{pcname}、こんにちは。'}, {}, {},
                                    {'a': 'Hello'}, {'a': '你好'})
        self.assertFalse(reviews)
        self.assertEqual(rejected[0]['reason'], 'japanese_runtime_signature_differs')

    def test_unknown_english_does_not_hide_a_known_changed_english_source(self):
        reviews, rejected = propose({'a': 'Purchase'}, {'a': '購入'}, {}, {}, {'a': 'Delete'}, {'a': '删除'})
        self.assertFalse(reviews)
        self.assertEqual(rejected[0]['reason'], 'official_english_sources_differ')


if __name__ == '__main__':
    unittest.main()
