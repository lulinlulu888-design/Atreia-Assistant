import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "localization"))
from audit_mainland import audit


class MainlandAuditTests(unittest.TestCase):
    def test_all_rows_including_existing_translations_are_checked(self):
        source = {"ServerName_1_desc": "Nezekan", "ServerName_2_desc": "Israphel",
                  "String_UI_1": "Gain {0}", "NpcTalk_1": "Marchutan",
                  "String_1": "Press Enter", "String_2": "Press Enter", "missing": "x"}
        translated = {"ServerName_1_desc": "伊斯拉斐尔", "ServerName_2_desc": "伊斯拉斐尔",
                      "String_UI_1": "获得", "NpcTalk_1": "马库坦",
                      "String_1": "Press Enter", "String_2": "按 Enter", "extra": "x"}
        report = audit(source, translated)
        self.assertEqual(report["counts"]["server_name_mismatch"], 2)
        self.assertEqual(report["counts"]["parameter_mismatch"], 1)
        self.assertEqual(report["counts"]["lore_name_review"], 1)
        self.assertEqual(report["counts"]["unchanged_latin"], 1)
        self.assertEqual(report["counts"]["mixed_latin"], 1)
        self.assertEqual(report["counts"]["missing_key"], 1)
        self.assertEqual(report["extra_keys"], ["extra"])
        self.assertFalse(report["same_key_order"])

    def test_tokens_are_not_english_residuals(self):
        source = {"key": "<style>{pcname}\\n%s</>"}
        report = audit(source, source)
        self.assertEqual(report["counts"], {})

    def test_unknown_servers_are_not_claimed_internal_or_translated(self):
        report = audit({"ServerName_1_desc": "NewName"}, {"ServerName_1_desc": "新名字"})
        self.assertEqual(report["counts"], {"server_name_unreviewed": 1})

    def test_classification_is_read_only_and_categories_can_overlap(self):
        source, translated = {"key": "Abyss"}, {"key": "深渊伺服器 ABC"}
        report = audit(source, translated)
        self.assertEqual(translated["key"], "深渊伺服器 ABC")
        self.assertEqual(report["candidate_rows"], 1)
        self.assertEqual(report["counts"], {"context_review": 1, "mixed_latin": 1, "terminology_candidate": 1})


if __name__ == "__main__":
    unittest.main()
