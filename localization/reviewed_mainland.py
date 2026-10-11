"""Small, exact-source reviews; do not infer meaning from reused numeric IDs."""
import hashlib

from mainland_names import MAINLAND_NAMES

# AION 1 geography, cross-checked against the CN references in MAINLAND_AUDIT.md.
PLACE_NAMES = {
    "Poeta": "普埃塔", "Verteron": "贝尔特伦", "Eltnen": "埃尔特内",
    "Interdikah": "因特尔蒂卡", "Theobomos": "泰奥勃莫斯",
    "Ishalgen": "伊斯夏尔肯", "Altgard": "阿尔特盖德", "Morheim": "莫尔海姆",
    "Beluslan": "贝鲁斯兰", "Brusthonin": "布鲁斯特豪宁",
    "Inggison": "英吉斯温", "Gelkmaros": "格尔克马洛斯",
    "Sanctum": "极乐世界", "Pandaemonium": "伏魔殿",
}

UI_TEXT = {
    "Server List": "服务器列表", "Class": "职业", "Level Up": "等级提升",
    "WIN": "胜利", "LOSE": "失败", "DRAW": "平局",
    "START": "开始", "FINISH": "结束", "SKIP": "跳过", "HOLD": "长按",
    "AUTO": "自动", "Auto": "自动", "OFF": "关闭",
    "MAX": "最大", "MIN": "最小", "ALL": "全部", "None": "无",
    "NEW": "新", "GET": "领取", "EMPTY": "空位", "SELF": "自身",
    "LEFT": "左", "RIGHT": "右", "RED": "红队", "BLUE": "蓝队",
    "WEAPON": "武器", "ARMOR": "防具", "SUCCESS": "成功",
    "TIME": "时间", "RANK": "排名", "EXP": "经验值",
    "{0} EXP": "{0} 经验值", "EPISODE {0}": "第 {0} 章",
    "(Currently {0})": "（当前：{0}）", "Coming soon": "敬请期待",
    "Guest": "游客", "Vertical Sync": "垂直同步", "Tattoo Design": "纹身图案",
    'Step "{1}" of "{0}" Complete': '完成“{0}”的“{1}”阶段',
    "The Elyos/Asmodian servers are separated. They cannot meet under normal circumstances.":
        "天族与魔族分属不同的服务器，通常情况下无法相遇。",
    "Daeva of Elysea living in the South of Atreia\nAn elegant and sacred faction":
        "生活在亚特雷亚南部的天族守护者\n优雅而神圣的种族",
    "Daeva of Asmodae living in the North of Atreia\nA rough, wild, and ambitious faction":
        "生活在亚特雷亚北部的魔族守护者\n粗犷、野性且雄心勃勃的种族",
    "You can place up to 30 Map Pins. When all 30 Map Pins are placed, you must remove an existing Map Pin before adding a new one.":
        "最多可设置30个地图标记。达到上限后，需先删除已有标记，才能添加新标记。",
}

KEYED_TEXT = {
    "String_UI_LOBBY_GAMESERVER_LIST_CHECKBUTTON_AVAILABLE_body": ("Available", "可连接"),
    "String_UI_SERVER_STATE_CONGESTION_FREE_body": ("Normal", "流畅"),
    "String_UI_SERVER_STATE_CONGESTION_FULL_body": ("Full", "已满"),
    "String_UI_GLOBAL_SERVICE_SERVER_REGION_PING_SLOW_body": ("Slow", "较慢"),
    "CutsceneSubtitle_S2230_Nemon_04_cv_text": ("Where is the Empyrean Lord Zikel's Core?", "主神吉凯尔的根源在哪里？"),
    "CutsceneSubtitle_S2101_Urd_01_cv_text": ("Hystan, high priest of Zikel.", "吉凯尔的大神官，希斯坦。"),
    "CutsceneSubtitle_S2241_Nemon_01_cv_text": ("Zikel, I am here for your Core.", "吉凯尔，我是来寻找你的根源的。"),
    "NpcTalk_04F2387009154749A67CB077B752EAE3_cv_text": (
        "If we cannot obtain the cores of the Empyrean Lords, we cannot cross the Bulwark. But without the high priestess, we can't find Kaisinel's Core.",
        "没有主神的根源，我们就无法越过防壁。但找不到大神官，就无法得知凯西内尔根源的下落。"),
}

EXACT_TEXT = {
    "Reached Level 10 of [Ereshkigal's Monolith]\nYou are growing skilled at finding Empyrean Traces.":
        "[艾莱休奇卡独石柱]达到10级\n你寻找主神痕迹的本领越发娴熟了。",
}

# Long source reviews are digest-bound to avoid shipping whole English documents.
KEYED_DIGEST_TEXT = {
    "QuestString_STR_AQ1602020_quest_summary_journal_complete": (
        "056fc48fadda9509d4c2726c9e234fdf663dafdfb1b5f3e50c7dd1411478ce2f",
        "“战胜主神凯西内尔带来的恐惧，证明你有资格掌握永恒之塔的力量。”\n\n"
        "天界与魔界的主神如今虽已对立，他们的力量却都传承自<QK>永恒之塔</>。\n"
        "阿萨尔告诉我，只要与永恒之塔的力量共鸣，就能将主神之力化为己用。\n\n"
        "我在魔界面对吉凯尔之梦，接受了他的考验，并意识到自己有能力觉醒为神圣守护者，与永恒之塔共鸣，驾驭主神之力。\n\n"
        "通过考验后，我借助<QK>吉凯尔之梦碎片</>，开始了成为真正守护者的觉醒。"),
    "QuestString_STR_AQ1602020_quest_summary_popup_complete": (
        "40bed4476702031f6f55e82417bf0b4dd044d3a97570773aba901bcad6873aed",
        "“战胜主神凯西内尔带来的恐惧，证明你有资格掌握永恒之塔的力量。”\n\n"
        "魔界与天界主神的力量都传承自永恒之塔。\n"
        "我借助魔界主神吉凯尔的梦之碎片，开始了成为真正守护者的觉醒。"),
    "NoteData_Note_Dungeon_D_0021_01_text": (
        "97c178a45cc8ed6ed75ce61e56bbc3208af4e9b9993ead9538cdbf311fcdeba4",
        "有事求见者，须通过我的随行官胡基侬通报。\n\n"
        "你们为修复这座浮空神殿所经历的艰辛，我都知道。\n再坚持片刻。\n我将改变你们的命运。\n\n"
        "你们不必再追随无能的主神马勒库坦。\n我将带领你们走向新的命运。"),
}


def reviewed_translation(key, source):
    if key in KEYED_TEXT and source == KEYED_TEXT[key][0]:
        return KEYED_TEXT[key][1]
    if key in KEYED_DIGEST_TEXT and hashlib.sha256(source.encode("utf-8")).hexdigest() == KEYED_DIGEST_TEXT[key][0]:
        return KEYED_DIGEST_TEXT[key][1]
    if source in EXACT_TEXT:
        return EXACT_TEXT[source]
    if source in MAINLAND_NAMES:
        return MAINLAND_NAMES[source]
    if key.startswith("ServerName_") and source in PLACE_NAMES:
        return PLACE_NAMES[source]
    if key.startswith("String_UI_"):
        return UI_TEXT.get(source)
    if key == "QuestString_STR_HQ2102120_step5" and source == "Hear about the legionnaires who infiltrated":
        return "听取潜入军团成员的情况"
    return None
