from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'localization'))
from official_japanese_reviews import propose
from reviewed_japanese import reviewed_translation


class OfficialJapaneseReviewTests(unittest.TestCase):
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
