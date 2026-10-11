"""Identity-based AION names. Evidence and unresolved names: MAINLAND_AUDIT.md."""
import re


MAINLAND_NAMES = {
    "Israphel": "伊斯拉佩尔",
    "Nezekan": "奈萨肯",
    "Siel": "希埃尔",
    "Vaizel": "白杰尔",
    "Kaisinel": "凯西内尔",
    "Yustiel": "尤斯迪埃",
    "Ariel": "艾瑞尔",
    "Azphel": "阿斯佩尔",
    "Marchutan": "马勒库坦",
    "Zikel": "吉凯尔",
    "Triniel": "崔妮尔",
    "Lumiel": "鲁米埃尔",
    "Fregion": "普雷奇温",
    "Meslamtaeda": "梅斯兰泰达",
    "Ereshkigal": "艾莱休奇卡",
    "Beritra": "布里特拉",
}

# Never turn an unrelated character into another deity based on screen order.
# These spellings may be normalized only when the English identifies the deity.
NAME_ALIASES = {
    "Israphel": ("伊斯拉斐尔", "伊斯拉菲尔"),
    "Marchutan": ("马库坦", "马尔库坦", "玛尔库坦", "马胡坦", "马楚坦", "马钱坦"),
    "Zikel": ("齐凯尔", "齐克尔"),
    "Yustiel": ("尤斯提尔", "尤斯蒂尔"),
    "Ariel": ("阿里尔",),
    "Azphel": ("阿斯菲尔",),
    "Triniel": ("特里尼尔",),
    "Lumiel": ("露米尔", "露梅尔", "鲁米艾尔"),
    "Kaisinel": ("卡西内尔",),
    "Fregion": ("普雷奇翁",),
    "Ereshkigal": ("埃列什基伽勒", "艾莱修奇卡"),
    "Beritra": ("贝里特拉",),
    "Meslamtaeda": ("梅斯拉姆塔埃达", "梅斯拉姆泰达"),
}


def source_names(source):
    return [name for name in MAINLAND_NAMES
            if re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", source, re.I)]


def name_terms(source):
    return {alias: MAINLAND_NAMES[name] for name in source_names(source)
            for alias in NAME_ALIASES.get(name, ())}


def embedded_names(prose, source):
    for name in source_names(source):
        prose = re.sub(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])",
                       lambda _: MAINLAND_NAMES[name], prose, flags=re.I)
    return prose
