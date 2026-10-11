"""Regression tests for the mainland terminology layer."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "localization"))
import build_official_additions as additions


class OfficialAdditionsTests(unittest.TestCase):
    def test_mainland_aion_terms_override_simplified_tw_wording(self):
        source = "深渊点数、以太、公会、物理暴击、魔法暴击、巨剑、魔法书、法珠"
        self.assertEqual(
            additions.mainland_terms(source),
            "欧比斯点数、奥德、军团、物理致命一击、魔法致命一击、大剑、法书、宝珠",
        )

    def test_mainland_places_and_lords_are_stable(self):
        source = "英德尔地卡、贝尔特伦、马库坦、凯西内尔"
        self.assertEqual(
            additions.mainland_terms(source),
            "因特尔蒂卡、贝尔特伦、马勒库坦、凯西内尔",
        )

    def test_build_applies_terms_without_changing_runtime_parameters(self):
        english = {"key": "Gain {0} Abyss Points"}
        traditional = {"key": "获得{0}深渊点数"}
        fake_opencc = SimpleNamespace(OpenCC=lambda _config: SimpleNamespace(convert=lambda text: text))
        with patch.dict(sys.modules, {"opencc": fake_opencc}):
            payload, rejected = additions.build(english, traditional)
        self.assertEqual(rejected, [])
        self.assertEqual(payload["entries"]["key"]["translation"], "获得{0}欧比斯点数")


if __name__ == "__main__":
    unittest.main()
