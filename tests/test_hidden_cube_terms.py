import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "localization"))
from unify_hidden_cube import build, digest, normalize


class HiddenCubeTermsTests(unittest.TestCase):
    def test_names_actions_keys_and_objectives(self):
        for source, old, expected in (
            ("Hidden Cube", "隐藏背包", "隐藏宝箱"),
            ("Opening the Hidden Cube...", "正在开启隐藏背包……", "正在开启隐藏宝箱……"),
            ("Key: Hidden Cube (Bound)", "钥匙：隐藏背包（绑定）", "钥匙：隐藏宝箱（绑定）"),
            ("Open 40 Hidden Cubes with a key", "使用钥匙开启隐藏背包40个", "使用钥匙开启隐藏宝箱40个"),
        ):
            self.assertEqual(normalize(source, old), expected)

    def test_does_not_change_bags_or_tokens(self):
        self.assertEqual(normalize("Hidden Backpack", "隐藏背包"), "隐藏背包")
        self.assertEqual(normalize("{Hidden Cube}", "隐藏背包"), "隐藏背包")
        self.assertEqual(normalize("Hidden Cube {0}", "<隐藏背包>{隐藏背包}隐藏背包{0}"),
                         "<隐藏背包>{隐藏背包}隐藏宝箱{0}")

    def test_exact_source_binding_preservation_and_idempotence(self):
        matched = {"source_sha256": digest("Hidden Cube"), "translation": "隐藏背包"}
        stale = {"source_sha256": digest("Old Hidden Cube"), "translation": "隐藏背包"}
        bundle = {"format": 3, "entries": {"name": [matched, stale]}, "corrections": {
            "name": [dict(matched, previous_translation_sha256="original-binding")]}}
        saved = copy.deepcopy(bundle)
        result, count = build(bundle, [{"name": "Hidden Cube"}])
        self.assertEqual(count, 4)
        self.assertEqual(bundle, saved)
        self.assertEqual(result["entries"]["name"][1], stale)
        self.assertEqual(result["corrections"]["name"][0]["previous_translation_sha256"], "original-binding")
        self.assertEqual(build(result, [{"name": "Hidden Cube"}]), (result, 0))
