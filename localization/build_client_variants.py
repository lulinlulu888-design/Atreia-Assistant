"""Build reviewed, source-bound Steam variants without distributing game text.

The reviewed input snapshots are pinned: a different game update requires review,
not silently assigning the current TW meaning to an older Steam key.
"""
import argparse
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path

from build_official_additions import PARAMETERS

SNAPSHOTS = {
    "2026-10-05": {
        "steam": "c11773f7f8f443aa70eb4b4395b9ce6d2573c6bec859e9507219372e43879c03",
        "purple": "e214f8bbd7f5f4f0f292e6fffd26834b4ccce08fff8b656d25ad570757e9a21e",
    },
    "2026-10-10": {
        "steam": "f8c79eb669613ba68aaff45a22395b9cd12138631253d5789f96b023330254bf",
        "purple": "0c7b67bda6f4b0b1e5fec862fdf21b49b90711a198a59f457e2756ead154c172",
    },
}


def snapshots(purple_path, steam_path):
    purple, steam = purple_path.read_bytes(), steam_path.read_bytes()
    pair = {"purple": hashlib.sha256(purple).hexdigest(),
            "steam": hashlib.sha256(steam).hexdigest()}
    if pair not in SNAPSHOTS.values():
        raise ValueError("Unreviewed or mixed-client source snapshots")
    return json.loads(purple), json.loads(steam)


def steam_update_replacement(source):
    """Reviewed October update wording; preserve Steam-only rewards and stats.

    Called only after the full client snapshot pair has been verified. Runtime
    entries remain bound to the exact row source digest, not fuzzy key matches.
    """
    exact = {
        "Eagle Eye": "鹰眼", "Eyes Wide Open": "慧眼", "Step by Step": "步步前行",
        "Journey's Path": "旅途之路", "Title: Eagle Eye": "称号：鹰眼",
        "Title: Eyes Wide Open": "称号：慧眼", "Title: Step by Step": "称号：步步前行",
        "Title: Journey's Path": "称号：旅途之路",
        "Contains items that will greatly assist you on your adventure.": "内含能为你的冒险提供极大帮助的道具。",
        "Grants [Test Package].\nContains items that will greatly assist you on your adventure.": "获得[测试礼包]。\n内含能为你的冒险提供极大帮助的道具。",
        "Allows you to select a pet that will assist you on your adventure.": "可选择一只协助你冒险的宠物。",
        "Allows you to obtain a pet that will assist you on your adventure.": "可获得一只协助你冒险的宠物。",
        "Eternal Sun Weapon Skin Chest (8 Pieces) (Bound)": "永恒之日武器外形箱（8件）（绑定）",
        "A chest that grants one of every Eternal Sun Weapon Skin (Greatsword, Longsword, Dagger, Bow, Spellbook, Orb, Mace, Staff).": "可获得每种永恒之日武器外形各一件的箱子（巨剑、长剑、短剑、弓、法书、宝珠、钉锤、法杖）。",
        "A chest containing a Count Recharge Ticket that can be used to recharge the play count for a selected game mode.\n\n[Available Modes]\nShugo Festival\nDaily Dungeon - <Unknown Fissure> \nSeason - <Nightmare> <Ascension Trial>": "内含次数补充券的箱子，可补充所选玩法的参与次数。\n\n[适用玩法]\n树古庆典\n每日副本 - <未知裂缝> \n赛季 - <噩梦> <升天试炼>",
        "Please contact Customer Support.": "请联系客服。",
        "Disruption of Game Operations": "妨碍游戏运营",
        "Distributing Personal Information": "散布个人信息",
        "The selected region is currently undergoing maintenance and unavailable.": "所选地区正在维护，暂时无法使用。",
        "This server is under maintenance.": "该服务器正在维护。",
        "Creation or Distribution of Unauthorized Programs": "制作或传播未经授权的程序",
        "Gambling-Related Activity": "参与赌博相关活动",
        "Gameplay Disruption": "妨碍他人游戏",
        "Account Trading": "账号交易", "Inappropriate Name": "违规名称",
        "Ends: {0} (GMT)": "结束时间：{0}（GMT）",
        "Temporary Administrative Protection": "临时管理保护",
        "Reason for Penalty: {0}": "处罚原因：{0}", "User Request": "用户申请",
        "Fraud": "诈骗", "Until Penalty Ends": "至处罚结束",
        "Real Money Trading (RMT)": "现实货币交易（RMT）",
        "Inappropriate Language": "不当言论", "Unsportsmanlike Conduct": "不当游戏行为",
        "Identity Theft": "盗用身份", "Abuse of Game Systems": "滥用游戏系统",
        "Raid Content Exploit": "利用团队副本漏洞",
        "Creation of Inappropriate Appearance": "制作违规外形",
        "False or Misuse of Personal Information": "伪造或滥用个人信息",
        "False Reports": "虚假举报", "Use of Unauthorized Programs": "使用未经授权的程序",
        "Payment Fraud": "支付欺诈",
        "Distribution of Inappropriate Character Appearance": "传播违规角色外形",
        "Use of Unauthorized Programs (Minor)": "使用未经授权的程序（轻度违规）",
        "Account Theft": "盗用账号", "Boosting Play": "代练",
        "Other Policy Violation": "其他规则违规", "Open Market Abuse": "滥用交易市场",
        "Minor Bug Exploition System Abuse": "利用轻微漏洞滥用系统",
        "Attempted Real Money Trade (RMT) Transaction": "尝试进行现实货币交易（RMT）",
        "Gold Farming/Bot Operations": "打金或机器人运营", "Attempted Fraud": "诈骗未遂",
        "Advertisement Unrelated to the Game Service": "发布与游戏服务无关的广告",
        "Penalty Duration: {0}": "处罚期限：{0}", "Permanent": "永久",
        "Exploitation of Bugs or Game Limitations": "利用漏洞或游戏限制",
        "Founder's Pack": "创始者礼包", "Deluxe Skin": "豪华外形",
        "Ultimate Exclusive": "终极专属", "Title": "称号",
    }
    if source in exact:
        return exact[source]
    reward_prefix = "Contains rewards that assist Daeva in combat.\n\n"
    if source.startswith(reward_prefix):
        items = {"Power Shard": "封魂石", "Battle Enhance Scroll": "战斗强化咒文书",
                 "Life Crystal": "生命结晶", "Resurrection Spiritstone": "复活精灵石",
                 "Odyle Energy": "奥德能量", "Small Odyle Energy": "微小奥德能量",
                 "Content Usage Ticket Selection Chest": "内容使用补充券选择箱"}
        translated = []
        for line in source[len(reward_prefix):].split("\n"):
            match = re.fullmatch(r"([\d,]+) (.+) \(Bound\)", line)
            if not match or match[2] not in items:
                return None
            translated.append(f"{items[match[2]]}（绑定）×{match[1]}")
        return "内含协助守护者战斗的奖励。\n\n" + "\n".join(translated)
    # Do not reuse TW wings: Steam changed flight power and has different combat
    # attributes. Translate every actual stat and preserve numbers and order.
    wing = re.fullmatch(r"Grants \[(Lesser|Intermediate|Ultimate) Daeva Wings \(Bound\)\]\.\n\n(.+)", source, re.DOTALL)
    if wing:
        names = {"Lesser": "下级", "Intermediate": "中级", "Ultimate": "最上级"}
        stats = {"HP": "生命力", "MP": "精神力", "Penetration": "贯穿",
                 "Critical Hit": "暴击", "Flight Power": "飞行力", "Accuracy Bonus": "额外命中",
                 "Attack Bonus": "额外攻击力", "Defense Bonus": "额外防御力",
                 "Front Critical Hit Resist": "正面暴击抵抗"}
        sections = {"[Equipped Effect]": "[装备效果]", "[Owned Effect]": "[持有效果]"}
        lines = []
        for line in wing[2].split("\n"):
            if line in sections:
                lines.append(sections[line])
                continue
            match = re.fullmatch(r"(.+): ([\d,]+)", line)
            if not match or match[1] not in stats:
                return None
            lines.append(f"{stats[match[1]]}：{match[2]}")
        return f"获得[守护者{names[wing[1]]}翅膀（绑定）]。\n\n" + "\n".join(lines)
    return None


def replacement(key, source, official, english):
    reviewed_update = steam_update_replacement(source)
    if reviewed_update is not None:
        return reviewed_update
    if key.startswith("ServerName_"):
        # Server IDs are reused for different names between clients. Match the
        # actual name, never reuse TW text just because the numeric ID matches.
        candidates = {official[k]["translation"] for k, v in english.items()
                      if k.startswith("ServerName_") and v.casefold() == source.casefold()}
        if len(candidates) == 1:
            return candidates.pop()
        names = {"Gauss": "高斯", "Tassin": "塔辛", "GAU": "高斯", "TAS": "塔辛",
                 "HEL": "赫尔", "LAM": "拉姆", "TIE": "提耶",
                 "마족Dev": "魔族开发服", "인터Dev": "跨服开发服"}
        return names.get(source)
    match = re.fullmatch(r"Collect (\d+) Types? of (Expedition|Shugo Festival) Artwork", source)
    if match:
        return f"收集{match[1]}种{'远征' if match[2] == 'Expedition' else '树古庆典'}画作"
    match = re.fullmatch(r"(Resurrection Spiritstone|Instant Clear Ticket: Daily Dungeon|Instant Clear Ticket: Nightmare|Key: Hidden Cube|Customization Voucher Chest) \((\d+) Days\) \(Bound\)", source)
    if match:
        names = {"Resurrection Spiritstone": "复活精灵石", "Instant Clear Ticket: Daily Dungeon": "每日副本扫荡券",
                 "Instant Clear Ticket: Nightmare": "噩梦扫荡券", "Key: Hidden Cube": "隐藏立方体钥匙",
                 "Customization Voucher Chest": "外形变更券箱"}
        return f"{names[match[1]]}（{match[2]}天）（绑定）"
    exact = {
        "Title granted to Daeva who opened the way to a new world.": "授予开辟通往新世界道路的守护者的称号。",
        "Vanguard of Atreia": "亚特雷亚先遣者",
        "Mysterious traces that can be used to make a special Artwork.": "可用于制作特殊画作的神秘痕迹。",
        "A mysterious mirror that remembers a specific appearance and allows you to use it at any time.\nEnables you to extract gear skins.": "记住特定外形，让你随时使用该外形的神秘镜子。\n可用于提取装备外形。",
        "<Lobby_CharDelete_Warning>Once the 24-hour grace period expires, it will be impossible to recover your character.</>": "<Lobby_CharDelete_Warning>24小时等待期结束后，将无法恢复角色。</>",
        "Elements": "元素",
    }
    if source in exact:
        return exact[source]
    # Remaining reviewed changes are grammar, punctuation, rich-text repairs,
    # or English terminology for the same official meaning. These rules cannot
    # run against other snapshots; the per-row source digest also binds runtime.
    reviewed = (
        "InputKeyMapping_EquipAllPreset", "NoteData_Note_Seal_Altgard_03",
        "NpcTalk_B9E7C9E6D27B487F98AE7A5548BCA9AB_", "QuestString_STR_HQ210",
        "SkillAbnormalString_", "SkillString_", "String_STR_ARCANA_MATERIAL_",
        "String_STR_RULE_DESC_FE_", "String_STR_ITEM_MATERIAL_REGION_CRAFT_SPECIFIC_",
        "String_STR_ITEM_BOX_ARCANA_", "String_UI_", "Message_MSG_ENCHANT_UPGRADE_",
        "Title_L_Achievement_107_", "Title_D_Achievement_107_",
        "AchievementString_Archieve_STR_Group_D_Dungeon_Citadel_",
        "AchievementString_Archieve_STR_Group_L_Dungeon_Citadel_",
        "AchievementString_Archieve_STR_Onboarding_",
    )
    if key.startswith(reviewed) and key in official:
        return official[key]["translation"]
    return None


def build(official, english, steam, keys):
    variants = {key: [entry] for key, entry in official.items()}
    added, rejected = 0, []
    for key in keys:
        source = steam[key]
        text = replacement(key, source, official, english)
        if text is None or sorted(PARAMETERS.findall(source)) != sorted(PARAMETERS.findall(text)):
            rejected.append(key)
            continue
        variants.setdefault(key, []).append({"source_sha256": hashlib.sha256(source.encode()).hexdigest(), "translation": text})
        added += 1
    if rejected:
        raise ValueError(f"Unreviewed variants: {rejected}")
    return {"format": 2, "origin": "local official TW with reviewed Steam variants", "entries": variants}, added


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("official", "purple", "steam", "probe", "engine", "root", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output must be new")
    english, steam = snapshots(args.purple, args.steam)
    with gzip.open(args.official, "rt", encoding="utf-8") as stream:
        official = json.load(stream)
    if official["format"] != 1:
        raise ValueError("Expected format-1 official additions")
    report = json.loads(subprocess.check_output([str(args.probe.resolve()), str(args.engine.resolve()), str(args.root.resolve())], encoding="utf-8-sig"))
    payload, count = build(official["entries"], english, steam, report["RemainingEnglishCandidateKeys"])
    with gzip.open(args.output, "xb") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
    print(f"Added {count} reviewed Steam variants; original PURPLE translations preserved")
