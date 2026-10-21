"""Reviewed Steam build 26077854 achievement text, matched by full source."""

import re

EXACT = {
    "Clear Ascension Trial 1 time": "通关升天试炼1次",
    "Clear Expedition Conquest 1 time": "通关远征征服1次",
    "Clear Nightmare (any level) 1 time": "通关任意层数的噩梦1次",
    "Clear Transcendence Dungeon 1 time": "通关超越副本1次",
    "Log in 3 times": "登录3次",
    "Obtain 1 piece of Unique Gear": "获得1件唯一装备",
    "Obtain 10 Pet Souls": "获得10个宠物灵魂",
    "Participate in Dimensional Invasion 1 time": "参与次元入侵1次",
    "Successful Gear Extraction": "装备提取成功",
    "Successful Gear Soul Binding": "装备灵魂绑定成功",
    "Successful Substance Morph": "物质变化成功",
    "Use a Scroll 5 times": "使用咒文书5次",
    "[Event] Abyss": "[活动]深渊",
    "[Event] Ascension Trial": "[活动]升天试炼",
    "[Event] Dimensional Invasion": "[活动]次元入侵",
    "[Event] Expedition": "[活动]远征",
    "[Event] Login": "[活动]登录",
    "[Event] Nightmare": "[活动]噩梦",
    "[Event] Obtain Gear": "[活动]获得装备",
    "[Event] Shugo Festival": "[活动]树古庆典",
    "[Event] Transcendence": "[活动]超越",
    "[Event] Use Scrolls": "[活动]使用咒文书",
}


def replacement(key, source):
    if not key.startswith("AchievementString_"):
        return None
    if source in EXACT:
        return EXACT[source]
    match = re.fullmatch(r"Collect ([1-6]) Types? of (Heroic|Unique) Expedition Artwork", source)
    if match:
        return "收集" + match[1] + "种" + {"Heroic": "英雄", "Unique": "唯一"}[match[2]] + "远征画作"
    match = re.fullmatch(r"Hero's Footsteps (I|II|III|IV|V|VI)", source)
    if match:
        return "英雄的足迹" + match[1]
    match = re.fullmatch(r"Clear (Draupnir|Ferocious Horn Den|Vakron Sky Island) Conquest on Hard (18|21|23|25) times", source)
    if match:
        names = {"Draupnir": "德拉乌伯尼尔", "Ferocious Horn Den": "凶猛的角岩窟", "Vakron Sky Island": "巴克隆空中岛"}
        return names[match[1]] + "征服[困难]完成" + match[2] + "次"
    match = re.fullmatch(r"Clear Hall of Illusion Conquest on Normal (10|15) times", source)
    if match:
        return "通关普通难度的幻影殿堂征服" + match[1] + "次"
    match = re.fullmatch(r"(Draupnir|Ferocious Horn|Vakron Sky Island) Conquest Depths Clear VII", source)
    if match:
        names = {"Draupnir": "德拉乌伯尼尔", "Ferocious Horn": "凶猛的角岩窟", "Vakron Sky Island": "巴克隆空中岛"}
        return names[match[1]] + "征服深层完成VII"
    return None
