"""Synthetic regression fixtures; no proprietary game tables are required."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "localization"))
import build_client_variants as variants


class ClientVariantsTests(unittest.TestCase):
    def test_pins_paired_snapshots_and_rejects_updates_and_mixed_versions(self):
        with tempfile.TemporaryDirectory() as scratch:
            purple, steam = Path(scratch) / "purple.json", Path(scratch) / "steam.json"
            pairs = []
            for label in ("old", "new"):
                data = {client: json.dumps({"key": label + client}).encode()
                        for client in ("purple", "steam")}
                pairs.append(data)
            pins = {str(i): {k: hashlib.sha256(v).hexdigest() for k, v in pair.items()}
                    for i, pair in enumerate(pairs)}
            with patch.object(variants, "SNAPSHOTS", pins):
                for pair in pairs:
                    purple.write_bytes(pair["purple"])
                    steam.write_bytes(pair["steam"])
                    self.assertEqual(variants.snapshots(purple, steam),
                                     (json.loads(pair["purple"]), json.loads(pair["steam"])))
                purple.write_bytes(pairs[0]["purple"])
                steam.write_bytes(pairs[1]["steam"])
                with self.assertRaisesRegex(ValueError, "mixed-client"):
                    variants.snapshots(purple, steam)
                steam.write_text('{"unreviewed":"new patch"}')
                with self.assertRaises(ValueError):
                    variants.snapshots(purple, steam)

    def test_source_binding_and_original_purple_variant_preserved(self):
        source = "Reason for Penalty: {0}"
        purple_entry = {"source_sha256": hashlib.sha256(b"different original").hexdigest(),
                        "translation": "原版文本"}
        payload, count = variants.build({"key": purple_entry}, {}, {"key": source}, ["key"])
        self.assertEqual(count, 1)
        self.assertEqual(payload["entries"]["key"][0], purple_entry)
        added = payload["entries"]["key"][1]
        self.assertEqual(added["source_sha256"], hashlib.sha256(source.encode()).hexdigest())
        self.assertIn("{0}", added["translation"])

    def test_steam_shop_and_maintenance_do_not_reuse_purple_meaning(self):
        official = {"shop": {"translation": "测试"},
                    "maintenance": {"translation": "维护中，请选择其他服务器"}}
        self.assertEqual(variants.replacement("shop", "Founder's Pack", official, {}), "创始者礼包")
        self.assertEqual(variants.replacement("maintenance", "This server is under maintenance.", official, {}),
                         "该服务器正在维护。")

    def test_wings_preserve_steam_stats_order_and_flight_power(self):
        source = ("Grants [Ultimate Daeva Wings (Bound)].\n\n[Equipped Effect]\n"
                  "HP: 500\nMP: 250\nPenetration: 500\nCritical Hit: 35\n"
                  "[Owned Effect]\nFlight Power: 1000\nPenetration: 100\nAccuracy Bonus: 20\nAttack Bonus: 10")
        text = variants.steam_update_replacement(source)
        self.assertIn("飞行力：1000", text)
        self.assertIn("暴击：35", text)
        self.assertNotIn("额外防御力", text)
        import re
        self.assertEqual(re.findall(r"\d+", source), re.findall(r"\d+", text))
        self.assertEqual(source.count("\n"), text.count("\n"))
        self.assertIsNone(variants.steam_update_replacement(source + "\nUnknown Stat: 7"))

    def test_rewards_preserve_quantities_and_reject_unknown_items(self):
        prefix = "Contains rewards that assist Daeva in combat.\n\n"
        text = variants.steam_update_replacement(prefix + "1,000 Power Shard (Bound)\n3 Life Crystal (Bound)")
        self.assertIn("封魂石（绑定）×1,000", text)
        self.assertIn("生命结晶（绑定）×3", text)
        self.assertIsNone(variants.steam_update_replacement(prefix + "2 Unknown Item (Bound)"))

    def test_unreviewed_variant_and_parameter_mismatch_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unreviewed variants"):
            variants.build({}, {}, {"key": "Unexpected wording {0}"}, ["key"])
        with patch.object(variants, "replacement", return_value="丢失参数"):
            with self.assertRaises(ValueError):
                variants.build({}, {}, {"key": "Original {0}"}, ["key"])


if __name__ == "__main__":
    unittest.main()
