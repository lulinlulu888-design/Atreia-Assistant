"""Generate local source-bound additions from matching official EN/TW tables.

Generated game text stays outside Git. Dependencies: opencc-python-reimplemented.
"""
import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

from mainland_names import embedded_names, name_terms
from reviewed_mainland import reviewed_translation

TOKENS = re.compile(r"<[^>]*>|\{[^}]*\}|%\d*\$?[a-zA-Z]|\\[nrt]")
PARAMETERS = re.compile(r"\{[^}]*\}|%\d*\$?[a-zA-Z](?![a-zA-Z])|\\[nrt]")
REVIEWED = {
    "GuideData_TG_Tutorial_UI_Enchant_006_tooltip_desc": "点击强化所选装备。{input:Action}",
    "SkillString_STR_SKILL_PC_GLADIATOR_11110030_specialized_skill_desc": "武器格挡成功后，移动速度提高{abe:1111003811:value02:divide100}%，持续{se:1111003811:effect_value02:time}。",
    "String_UI_ARCANA_INFO_SET_NAME_EQUIP_COUNT_body": "{0} (1}",
    "String_UI_SUBSCRIBE_ONBOARDING_PREMIUM_INFO_TOOLTIP_SUBSCRIBED_body": "订阅奎灵会员即可获得高级奖励。",
}
REVIEWED_SOURCES = {
    "GuideData_TG_Tutorial_UI_Enchant_006_tooltip_desc": "Click to enhance the selected gear. {input:Action}",
    "SkillString_STR_SKILL_PC_GLADIATOR_11110030_specialized_skill_desc": "+{abe:1111003811:value02:divide100}% Move Speed for {se:1111003811:effect_value02:time} on Parry",
    "String_UI_ARCANA_INFO_SET_NAME_EQUIP_COUNT_body": "{0} (1}",
    "String_UI_SUBSCRIBE_ONBOARDING_PREMIUM_INFO_TOOLTIP_SUBSCRIBED_body": "You can obtain  premium rewards with a Quai Membership.",
}

# AION 1 mainland terminology takes precedence over a mechanical zh-TW to
# zh-Hans conversion. These additions cover simplified TW wording that is not
# represented separately in the checked-in glossary.
MAINLAND_TERMS = {
    "深渊点数": "欧比斯点数",
    "欧比斯点数": "欧比斯点数",
    "物理暴击": "物理致命一击",
    "魔法暴击": "魔法致命一击",
    "英德尔地卡": "因特尔蒂卡",
    "泰奥勃莫斯": "泰奥勃莫斯",
    "伊斯夏尔肯": "伊斯夏尔肯",
    "阿尔特盖德": "阿尔特盖德",
    "布鲁斯特豪宁": "布鲁斯特豪宁",
    "贝尔特伦": "贝尔特伦",
    "埃尔特内": "埃尔特内",
    "莫尔海姆": "莫尔海姆",
    "贝鲁斯兰": "贝鲁斯兰",
    "凯西内尔": "凯西内尔",
    "以太": "奥德",
    "长剑": "长剑",
    "巨剑": "大剑",
    "魔法书": "法书",
    "法珠": "宝珠",
    "晕眩": "眩晕",
    "击退": "击退",
    "治愈量增加": "治愈量增加",
    "服务器": "服务器",
    "伺服器": "服务器",
    "商人公会": "商团",
    "舒戈公会": "术古商团",
    "舒戈": "术古",
    "巴劳尔": "龙族",
    "用户端": "客户端",
    "登入": "登录",
    "讯息": "消息",
    "影片": "视频",
    "有著": "有着",
    "标示": "显示",
}
GLOSSARY_PATH = Path(__file__).with_name("mainland_glossary.tsv")


def load_mainland_terms(converter=None):
    terms = dict(MAINLAND_TERMS)
    for line in GLOSSARY_PATH.read_text(encoding="utf-8-sig").splitlines():
        if not line or line.startswith("#"):
            continue
        source, translation = line.split("\t", 1)
        for spelling in (source, converter.convert(source) if converter else source):
            if spelling in terms and terms[spelling] != translation:
                raise ValueError(f"Conflicting mainland term: {spelling}")
            terms[spelling] = translation
    return terms


def transform_prose(text, transform):
    parts, position = [], 0
    for token in TOKENS.finditer(text):
        parts.extend((transform(text[position:token.start()]), token.group()))
        position = token.end()
    parts.append(transform(text[position:]))
    return "".join(parts)


def mainland_terms(text, terms=None, source=""):
    source = TOKENS.sub("", source)
    terms = dict(load_mainland_terms() if terms is None else terms)
    terms.update(name_terms(source))
    if re.search(r"\bEmpyrean Lords?\b", source, re.I):
        terms["天界之主"] = "主神"
        terms["天界领主"] = "主神"
    if re.search(r"\bDragon Lords?\b", source, re.I):
        terms["龙主"] = "龙帝"
    if "Siel's Wings" in source:
        terms.update({"谢尔之翼": "希埃尔之翼", "西尔之翼": "希埃尔之翼"})
    if "Daeva Pass" in source:
        terms.update({"天族通行证": "守护者通行证", "天培通行证": "守护者通行证"})
    if re.search(r"[\u3400-\u9fff]", TOKENS.sub("", text)):
        # Do not hide an untranslated English paragraph by translating only names.
        text = transform_prose(text, lambda prose: embedded_names(prose, source))
    if not terms:
        return text
    # Single-pass matching avoids replacement cascades and changing tokens.
    pattern = re.compile("|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True)))
    return transform_prose(text, lambda prose: pattern.sub(lambda m: terms[m.group()], prose))


def build(english, traditional):
    from opencc import OpenCC

    if english.keys() != traditional.keys():
        raise ValueError("Official language tables must contain the same keys")
    convert = OpenCC("t2s")
    terms = load_mainland_terms(convert)
    entries, rejected = {}, []
    for key, source in english.items():
        # Preserve the exact spelling of tags, variable names and escapes.
        text = traditional[key]
        translation = transform_prose(text, convert.convert)
        if key in REVIEWED and source == REVIEWED_SOURCES[key]:
            translation = REVIEWED[key]
        exact = reviewed_translation(key, source)
        if exact is not None:
            translation = exact
        translation = mainland_terms(translation, terms, source)
        if key.startswith("NpcTalk_"):
            # Preserve the English table's character-name binding count while
            # retaining official dialogue. Extra vocatives become a noun.
            expected = source.count("{pcname}")
            found = 0
            def name(match):
                nonlocal found
                found += 1
                return "{pcname}" if found <= expected else "守护者"
            translation = re.sub(r"\{pcname\}", name, translation)
            if found < expected:
                translation = "{pcname}，" * (expected - found) + translation
        # Official rich text may intentionally use different emphasis or
        # translated angle-bracket prose. Runtime parameters must still match.
        if sorted(PARAMETERS.findall(source)) != sorted(PARAMETERS.findall(translation)):
            rejected.append({"key": key, "source": source, "translation": translation})
            continue
        entries[key] = {"source_sha256": hashlib.sha256(source.encode()).hexdigest(), "translation": translation}
    return {"format": 1, "origin": "local official zh-TW table converted to Simplified Chinese", "entries": entries}, rejected


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("english", type=Path)
    parser.add_argument("traditional", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("review", type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.review.exists():
        raise ValueError("Outputs must be new")
    payload, rejected = build(json.loads(args.english.read_text(encoding="utf-8")), json.loads(args.traditional.read_text(encoding="utf-8")))
    with gzip.open(args.output, "xb") as output:
        output.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
    args.review.write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(payload['entries'])} source-bound translations; {len(rejected)} token mismatches require review")
