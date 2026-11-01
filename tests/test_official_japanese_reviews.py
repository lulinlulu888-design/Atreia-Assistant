from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'localization'))
from official_japanese_reviews import propose


class OfficialJapaneseReviewTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
