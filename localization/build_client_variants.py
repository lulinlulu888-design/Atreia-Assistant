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
    "steam": "c11773f7f8f443aa70eb4b4395b9ce6d2573c6bec859e9507219372e43879c03",
    "purple": "e214f8bbd7f5f4f0f292e6fffd26834b4ccce08fff8b656d25ad570757e9a21e",
}


def snapshot(path, kind):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != SNAPSHOTS[kind]:
        raise ValueError(f"Unreviewed {kind} source snapshot")
    return json.loads(data)


def replacement(key, source, official, english):
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
    english, steam = snapshot(args.purple, "purple"), snapshot(args.steam, "steam")
    with gzip.open(args.official, "rt", encoding="utf-8") as stream:
        official = json.load(stream)
    if official["format"] != 1:
        raise ValueError("Expected format-1 official additions")
    report = json.loads(subprocess.check_output([str(args.probe.resolve()), str(args.engine.resolve()), str(args.root.resolve())], encoding="utf-8-sig"))
    payload, count = build(official["entries"], english, steam, report["RemainingEnglishCandidateKeys"])
    with gzip.open(args.output, "xb") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
    print(f"Added {count} reviewed Steam variants; original PURPLE translations preserved")
