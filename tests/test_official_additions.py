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
            "欧比斯点数、奥德、公会、物理致命一击、魔法致命一击、大剑、法书、宝珠",
        )

    def test_mainland_places_and_lords_are_stable(self):
        source = "英德尔地卡、贝尔特伦、马库坦、凯西内尔"
        self.assertEqual(
            additions.mainland_terms(source, source="Inggison, Verteron, Marchutan, Kaisinel"),
            "因特尔蒂卡、贝尔特伦、马勒库坦、凯西内尔",
        )

    def test_glossary_matches_simplified_form_after_opencc(self):
        converter = SimpleNamespace(convert=lambda text: {
            "機率": "机率", "販售": "贩售", "組合包": "组合包"
        }.get(text, text))
        terms = additions.load_mainland_terms(converter)
        self.assertEqual(additions.mainland_terms("机率、贩售、组合包", terms),
                         "概率、出售、组合包")

    def test_merchant_guild_is_a_trade_group_not_a_player_legion(self):
        self.assertEqual(additions.mainland_terms("森卡商人公会"), "森卡商团")
        self.assertEqual(additions.mainland_terms("舒戈公会"), "术古商团")
        self.assertEqual(additions.mainland_terms("这家公会的商人"), "这家公会的商人")

    def test_mainland_ui_and_lore_vocabulary(self):
        source = "用户端登入伺服器后显示讯息，并开启档案和影片。巴劳尔与舒戈有著记录。"
        self.assertEqual(
            additions.mainland_terms(source),
            "客户端登录服务器后显示消息，并开启档案和视频。龙族与术古有着记录。",
        )

    def test_ambiguous_terms_are_not_global_substitutions(self):
        text = "刺客、牧师、吟遊詩人、奥德尔、古文石、组合包、深渊、档案"
        self.assertEqual(additions.mainland_terms(text), text)

    def test_name_aliases_require_the_same_english_identity(self):
        self.assertEqual(additions.mainland_terms("伊斯拉斐尔与马库坦",
                         source="Israphel and Marchutan"), "伊斯拉佩尔与马勒库坦")
        self.assertEqual(additions.mainland_terms("马库坦", source="Yustiel"), "马库坦")

    def test_lord_titles_and_alternate_spellings_require_source_context(self):
        self.assertEqual(additions.mainland_terms("天界之主尤斯提尔与齐克尔",
                         source="Empyrean Lords Yustiel and Zikel"), "主神尤斯迪埃与吉凯尔")
        self.assertEqual(additions.mainland_terms("龙主", source="Dragon Lord"), "龙帝")
        self.assertEqual(additions.mainland_terms("天界之主"), "天界之主")

    def test_embedded_names_are_translated_without_touching_identifiers(self):
        source = "Empyrean Lord Stats: Justice [Nezekan]"
        text = '<QK>天界领主属性：正义[Nezekan]</>{npc:Nezekan} Nezekan_Debug'
        self.assertEqual(additions.mainland_terms(text, source=source),
                         '<QK>主神属性：正义[奈萨肯]</>{npc:Nezekan} Nezekan_Debug')
        self.assertEqual(additions.mainland_terms("Zikel remains here", source="Zikel remains here"),
                         "Zikel remains here")
        self.assertEqual(additions.mainland_terms("齐克尔", source="{npc:Zikel}"), "齐克尔")

    def test_siel_wings_and_daeva_pass_are_contextual_not_generic(self):
        self.assertEqual(additions.mainland_terms("谢尔之翼与西尔之翼", source="Siel's Wings"),
                         "希埃尔之翼与希埃尔之翼")
        self.assertEqual(additions.mainland_terms("谢尔与西尔维娅", source="Siel's Wings"), "谢尔与西尔维娅")
        self.assertEqual(additions.mainland_terms("天族通行证", source="Daeva Pass"), "守护者通行证")
        self.assertEqual(additions.mainland_terms("天族通行证", source="Elyos Pass"), "天族通行证")

    def test_terms_never_modify_tags_or_runtime_bindings(self):
        text = '<伺服器 attr="深渊点数">伺服器{深渊点数}%s\\n</>'
        self.assertEqual(additions.mainland_terms(text),
                         '<伺服器 attr="深渊点数">服务器{深渊点数}%s\\n</>')

    def test_replacements_do_not_cascade(self):
        self.assertEqual(additions.mainland_terms("abc ab", {"abc": "ab", "ab": "x"}), "ab x")
        self.assertEqual(additions.mainland_terms("伺服器", {}), "伺服器")

    def test_conflicting_simplified_glossary_entries_fail_closed(self):
        converter = SimpleNamespace(convert=lambda _: "伺服器")
        with self.assertRaisesRegex(ValueError, "Conflicting mainland term"):
            additions.load_mainland_terms(converter)

    def test_build_preserves_tokens_during_both_conversion_and_normalization(self):
        text = '<樹古>{樹古}樹古</>'
        fake_opencc = SimpleNamespace(OpenCC=lambda _: SimpleNamespace(
            convert=lambda value: value.replace("樹", "树")))
        with patch.dict(sys.modules, {"opencc": fake_opencc}):
            payload, rejected = additions.build({"key": text}, {"key": text})
        self.assertEqual(rejected, [])
        self.assertEqual(payload["entries"]["key"]["translation"], '<樹古>{樹古}术古</>')

    def test_official_server_names_use_identity_not_tw_spelling(self):
        fake_opencc = SimpleNamespace(OpenCC=lambda _: SimpleNamespace(convert=lambda value: value))
        with patch.dict(sys.modules, {"opencc": fake_opencc}):
            payload, rejected = additions.build({"ServerName_1_desc": "Israphel"},
                                               {"ServerName_1_desc": "伊斯拉斐尔"})
        self.assertEqual(rejected, [])
        self.assertEqual(payload["entries"]["ServerName_1_desc"]["translation"], "伊斯拉佩尔")

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
