import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('japanese_mapping', Path(__file__).parents[1] / 'localization/japanese_mapping.py')
mapping = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mapping)


class JapaneseMappingTests(unittest.TestCase):
    def test_reuses_own_mainland_term_and_japanese_order(self):
        result, report = mapping.build({'b': 'World', 'a': 'Hello'}, {'a': 'こんにちは', 'b': '世界'},
                                       {'b': 'World', 'a': 'Hello'}, {'b': '亚特雷亚', 'a': '你好'})
        self.assertEqual(list(result), ['a', 'b'])
        self.assertEqual(result['b'], '亚特雷亚')
        mapping.require_complete({'a': 'こんにちは', 'b': '世界'}, result, report)

    def test_same_key_changed_english_is_not_reused(self):
        result, report = mapping.build({'a': 'New quest'}, {'a': '新任務'}, {'a': 'Old quest'}, {'a': '旧任务'})
        self.assertEqual(result, {})
        with self.assertRaises(ValueError):
            mapping.require_complete({'a': '新任務'}, result, report)

    def test_japanese_new_functional_tokens_cannot_be_dropped(self):
        _, report = mapping.build({'a': 'Damage'}, {'a': '{se_dmg:123} ダメージ'}, {'a': 'Damage'}, {'a': '伤害'})
        self.assertEqual(report['unresolved'][0]['reason'], 'japanese_runtime_tokens_or_markup_changed')

    def test_japanese_numbers_are_authoritative(self):
        _, report = mapping.build({'a': 'Complete 5 times'}, {'a': '3 回達成'}, {'a': 'Complete 5 times'}, {'a': '完成 5 次'})
        self.assertEqual(report['unresolved'][0]['reason'], 'japanese_numeric_values_need_review')

    def test_number_spacing_and_fullwidth_do_not_change_values(self):
        result, report = mapping.build({'a': 'Complete 5 times'}, {'a': '５回達成'}, {'a': 'Complete 5 times'}, {'a': '完成5次'})
        self.assertEqual(result['a'], '完成5次')
        self.assertTrue(report['publishable'])

    def test_review_is_bound_to_both_sources(self):
        review = {'english_sha256': mapping.fingerprint('Damage'), 'japanese_sha256': mapping.fingerprint('{se:1}'), 'translation': '{se:1} 伤害'}
        result, report = mapping.build({'a': 'Damage'}, {'a': '{se:1}'}, {}, {}, {'a': review})
        self.assertEqual(result['a'], '{se:1} 伤害')
        self.assertTrue(report['publishable'])
        with self.assertRaises(ValueError):
            mapping.build({'a': 'Damage'}, {'a': '{se:2}'}, {}, {}, {'a': review})

    def test_no_partial_prefix_or_count_cap(self):
        en = {f'quest_{n}': 'Hello' for n in range(600)}
        ja = {k: 'こんにちは' for k in en}
        cn = {k: '你好' for k in en}
        result, report = mapping.build(en, ja, en, cn)
        self.assertEqual(len(result), 600)
        self.assertTrue(report['publishable'])

    def test_unchanged_english_is_not_called_translated(self):
        _, report = mapping.build({'a': 'Accept'}, {'a': '承諾'}, {'a': 'Accept'}, {'a': 'Accept'})
        self.assertFalse(report['publishable'])


if __name__ == '__main__':
    unittest.main()
