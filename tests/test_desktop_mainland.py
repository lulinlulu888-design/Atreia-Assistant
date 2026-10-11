"""Check the shipped simplified dictionaries, not just generator fixtures."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "localization"))
from build_official_additions import PARAMETERS


def read(group, language):
    return json.loads((ROOT / "desktop/src/data/i18n" / group / (language + ".json")).read_text(encoding="utf-8"))


def strings(value, prefix=""):
    result = {}
    for key, item in value.items():
        if isinstance(item, str):
            result[prefix + key] = item
        elif isinstance(item, dict):
            result.update(strings(item, prefix + key + "."))
    return result


class DesktopMainlandTests(unittest.TestCase):
    def test_ui_has_all_source_keys_and_preserves_parameters(self):
        english, chinese = strings(read("ui", "en")), strings(read("ui", "zh-Hans"))
        self.assertEqual(english.keys(), chinese.keys())
        for key in english:
            self.assertEqual(sorted(PARAMETERS.findall(english[key])),
                             sorted(PARAMETERS.findall(chinese[key])), key)

    def test_skill_names_use_reviewed_mainland_spellings(self):
        skills = read("skills", "zh-Hans")
        for key, expected in {"15300000": "鲁米埃尔空间", "18330000": "马勒库坦愤怒",
                              "30012251": "神石：伊斯拉佩尔的从容",
                              "30012071": "神石：普雷奇温的计谋",
                              "30012081": "神石：艾莱休奇卡的监禁"}.items():
            self.assertEqual(skills[key], expected)

    def test_boss_name_residuals_are_fixed_without_losing_metadata(self):
        names = read("npcs", "zh-Hans")
        for key in ("2920232", "2920432", "2920998", "2921000"):
            self.assertEqual(names[key]["name"], "凯西内尔的幻影")
        for key in ("2920325", "2920379", "2920510"):
            self.assertEqual(names[key]["name"], "吉凯尔的幻影")
        self.assertTrue(names["2702132"]["isBoss"])
        self.assertEqual(names["2702132"]["name"], "马勒库坦躯壳")


if __name__ == "__main__":
    unittest.main()
