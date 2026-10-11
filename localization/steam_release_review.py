"""Authored translations for the pinned Steam 25800038 release review.

Names unique to AION2 are descriptive translations, not claims of AION1 canon.
Only the release builder may use this data after validating the source snapshot.
"""
import re

ARMOR_NAMES = {
    "Anguish": "苦痛", "Apex": "巅峰", "Armorsmith": "制甲师",
    "Armorsmith Splendent": "制甲师闪光", "Artisan Armorsmith": "达人制甲师",
    "Artisan Armorsmith Splendent": "达人制甲师闪光", "Bakarma": "巴卡尔玛",
    "Basilus": "巴西鲁斯", "Black Claw": "黑爪", "Celestial Dragon Armorsmith": "天龙制甲师",
    "Chaos": "混沌", "Comet": "彗星", "Corrupted Judicator": "堕落审判官",
    "Crimson Dragon Armorsmith": "赤龙制甲师", "Dark Dragon Armorsmith": "暗龙制甲师",
    "Defender": "守卫", "Demonic Dragon Armorsmith": "魔龙制甲师", "Destruction": "破灭",
    "Discipline": "纪律", "Divine Canyon": "神圣峡谷", "Division": "分裂",
    "Dramata": "龙母", "Durvati": "杜尔瓦提", "Earth": "大地",
    "Ebony Dragon Armorsmith": "乌木龙制甲师", "Elder": "长老", "Ethereal": "缥缈",
    "Expert Armorsmith": "匠人制甲师", "Expert Armorsmith Splendent": "匠人制甲师闪光",
    "Faith": "信仰", "Fantasy": "幻想", "Forgotten": "遗忘", "Frontline": "前线",
    "Holy Spirit": "圣灵", "Illusion": "幻象", "Intruder": "入侵者", "Judicator": "审判官",
    "Luminous": "光辉", "Mysterious": "神秘", "Nuakum": "努阿库姆",
    "Obsidian Dragon Armorsmith": "黑曜龙制甲师", "Order": "秩序", "Pact-bound": "契约",
    "Phantasm": "幻影", "Rainy Forest": "雨林", "Red Agate": "赤玛瑙",
    "Relic Seeker": "遗物探寻者", "Riverside": "河畔", "Shade": "暗影", "Sorrow": "悲哀",
    "Spectral": "幽魂", "Star Dragon Armorsmith": "星龙制甲师", "Tempest": "风暴",
    "Temple Guardian": "神殿守护者", "Transcendent": "超越", "True Dragon Armorsmith": "真龙制甲师",
    "Unyielding": "不屈", "Vagabond": "流浪者", "Vakron": "巴克隆", "Vowed": "誓约",
    "White Dragon Armorsmith": "白龙制甲师", "Wisdom": "智慧", "Wise Dragon Armorsmith": "鸣龙制甲师",
}

EXACT = {
    "Absorbs damage": "吸收伤害",
    "Mysterious traces that can be used to make a special Artwork.": "可用于制作特殊画作的神秘痕迹。",
    "Open the chest to earn 100,000 Kina (Bound).": "打开箱子可获得100,000基纳（绑定）。",
    "A mysterious mirror that remembers a specific appearance and allows you to use it at any time.\nEnables you to extract gear skins.": "能记住特定外形、让你随时使用该外形的神秘镜子。\n可用于提取装备外形。",
    "Title granted to Daeva who opened the way to a new world.": "授予开辟新世界道路的守护者的称号。",
    "Vanguard of Atreia": "亚特雷亚先遣者",
    "Defeat Idris, the Ruler of Ru": "击败鲁城统治者伊德里斯",
    "Solve the puzzle to find the Relic of Ru": "解开谜题，找到鲁城遗物",
    "Destroy the Ru Follower Statue": "摧毁鲁城追随者雕像",
    "Destroy the second Ru Follower Statue": "摧毁第二座鲁城追随者雕像",
    "Agnita": "阿格尼塔", "Atiel": "亚提埃尔", "Gauss": "高斯", "Rotan": "罗坦", "Tassin": "塔辛",
    "마족Dev": "魔族开发服", "인터Dev": "跨服开发服",
    "Binding Materials": "绑定材料", "Elements": "元素",
    "On Every Failed Roll": "每次判定失败时",
    "Adjusts Spirits' volume.": "调整精灵的音量。",
    "Basic reward available upon subscription\nApplied to the character it was subscribed on": "订阅后可领取基础奖励\n奖励发放给进行订阅的角色",
    "CharacterName obtained <Epic>Heroic Gear</>.": "角色名获得了<Epic>英雄装备</>。",
    "Your game session has been terminated by an administrator.\nFor more information, please contact Customer Support.\nPress [Confirm] to exit the game.": "管理员已终止你的游戏连接。\n详情请联系客服。\n点击[确认]退出游戏。",
    "Cannot perform Amplified Enhance due to insufficient Kina.": "基纳不足，无法进行增幅强化。",
    "I'd say our friend {pcname} has earned it. Besides, we need all the help we can get.": "我认为我们的朋友{pcname}已经赢得了这个资格。况且，现在任何帮助对我们都很重要。",
    "Ignored Kromede and laid down on the floor.": "无视克罗梅内，躺倒在地。",
    "Clear Toward the Nightmare Layer": "完成“向噩梦深处进发”",
    "Citadel of the Fallen Daeva Exploration Clear II": "通关堕落守护者要塞探索II",
    "Frame Material: Lucky Wings": "画框材料：幸运之翼",
    "A bundle containing Common-grade Arcana of Vigor.\nSelect the Arcana you need.": "内含普通品质活力阿尔卡纳的包裹。\n可选择所需的阿尔卡纳。",
    "A bundle containing Rare-grade Arcana of Vigor.\nSelect the Arcana you need.": "内含稀有品质活力阿尔卡纳的包裹。\n可选择所需的阿尔卡纳。",
    "A bundle containing Epic-grade Arcana of Vigor.\nSelect the Arcana you need.": "内含英雄品质活力阿尔卡纳的包裹。\n可选择所需的阿尔卡纳。",
    "<Lobby_CharDelete_Warning>Once the 24-hour grace period expires, it will be impossible to recover your character.</>": "<Lobby_CharDelete_Warning>24小时等待期结束后，角色将无法恢复。</>",
    "+ How many points can you earn with your flying skills?\n+ Use your flying skills to collect as many Odyle Drops as possible before time runs out.\n+ Fly through acceleration rings to boost your speed and restore your Flight Power.": "+ 用你的飞行技巧挑战更高分数！\n+ 在限定时间内飞行，尽可能多地收集奥德水滴。\n+ 穿过加速环可提高速度并恢复飞行力。",
    "+ Dodge the lasers and collect the festival balloons!\n+ Earn points for every balloon you collect.\n+ Watch out! Touching a laser will cost you points.": "+ 躲避激光，收集庆典气球！\n+ 每收集一个气球即可获得积分。\n+ 小心！碰到激光会扣除积分。",
    "+ Defeat waves of enemies and defend the Shugo Merchants!\n+ Using a Petrification Chest will immobilize enemies.\n+ Exploding insectoids have low HP, but are immune to petrification and deal heavy damage when they explode, so stay alert!": "+ 击退一波波敌人，保护树古商人！\n+ 使用石化箱可使敌人无法移动。\n+ 爆炸虫的生命值较低，但免疫石化，爆炸时会造成大量伤害，请保持警惕！",
}

# Narrative and long UI text are matched against the entire pinned source row.
KEYED = {
    "String_UI_SERVER_TRANSFER_RULE_CONTENT_body": "1. 角色数据会与永恒宝石、红利一同转移，原服务器的服务器级数据将重置。\n- 商店及玩法使用次数等账号级数据由所有服务器共用，不受转服影响。\n\n2. 无法转移的内容\n- 服务器级现金商城购买记录不转移。\n- 仓库内的物品和货币不转移。\n- 邮箱不转移。\n- 交易所内容不转移。\n- 角色栏位不转移。\n- 竞技场与战场最近10场对战记录将重置。\n\n3. 原服务器与目标服务器同步的内容\n- NPC商店：服务器级购买次数以原服务器为准进行调整。\n- 每周累计游玩奖励：参与次数及奥德能量宝箱的基纳获取量以原服务器为准进行调整。\n- 服务器级玩法：每日副本、树古庆典、次元入侵、剩余未领取宝箱数量及新芽徽章奖励次数，以原服务器为准进行调整。\n- 物质变化：服务器级变化次数以原服务器为准进行调整。\n- 个人交易：每日交易次数以原服务器为准进行调整。\n\n4. 分别处理的内容\n- 签到：服务器级签到随角色转移，原服务器的签到重置。目标服务器的签到重置后，应用原服务器的签到进度。\n- 订阅：随角色转移，原服务器重置。剩余订阅时长累加至目标服务器。\n- 会员通行证：随角色转移，原服务器重置。原服务器正在使用的会员通行证按已完成处理并发放奖励，尚未启用的通行证转移至目标服务器。\n- 守护者通行证：随角色转移，原服务器重置。已购买服务器级守护者通行证的角色转服时，购买次数累加至目标服务器，并从原服务器扣除。\n- 成长支援：随角色转移，原服务器重置。\n- 每日使命任务进度次数：角色有进行中的使命任务时，其进度次数累加至目标服务器，并从原服务器扣除。累加后的次数可能超过上限。\n- 成就：随角色转移，原服务器重置。服务器级成就比较两服进度后取较高等级；只有两服均未领取的服务器级成就奖励，转服后才可领取。\n- 宠物成就：属于例外，两服均保留。合并原服务器与目标服务器的宠物成就后，对两服同时应用。\n- 衣柜：随角色转移并合并，原服务器重置。收藏效果按合并结果生效。\n- 宠物：随角色转移并合并，原服务器重置。达到最高等级的宠物，其经验值转换为灵魂结晶。持有效果与收藏效果按合并结果生效；只有两服均未领取的收藏进度奖励，转服后才可领取。可选择保留原服务器或目标服务器的种族洞察，但无论选择哪一方，原服务器的种族洞察都会重置。使用现金或永恒宝石购买的重复特殊宠物，转换为宠物兑换券；在通行证商店购买的重复特殊宠物，转换为守护者通行证商店代币：返还。\n- 赛季任务：随角色转移，原服务器重置。目标服务器的共享赛季任务重置后，应用原服务器的进度。\n- 神石：随角色转移并合并，原服务器重置。\n- 主神痕迹共鸣：随角色转移，同时在原服务器保留。合并两服的主神痕迹共鸣数据后，对两服同时应用。\n- 服务器仓库扩展栏位：原服务器保留。比较两服栏位数量，目标服务器取较高值。\n- 代币商店：保留原服务器的购买记录。比较两服购买次数，目标服务器取较高值。",
    "NoteData_Note_Seal_Verteron_012_01_text": "鲁古城史\n\n大崩坏发生前，鲁城曾是古代亚特雷亚的一座巨城，后来被卷入了深渊。\n\n在深渊上层的西南部，人们发现了拉米兰要塞、寂静之岛、残骸之岛、亡者庭园、加尔齐坎据点，以及地下神殿的遗迹。\n\n永恒之塔崩塌后，留在深渊中的鲁城遗迹进一步散落各处。\n时至今日，修利曼探险队仍在深渊中航行，寻找鲁古城的踪迹。",
    "NoteData_Note_Seal_Altgard_038_01_text": "鲁古城探险队队员留下的记录。\n\n<鲁古城遗迹>\n大崩坏前，守护者和平共处的黄金时代，鲁城曾繁荣一时。如今，<QK>修利曼探险队</>仍不知疲倦地探索深渊，寻找这座失落古城的隐秘入口。\n\n<符文族圣域遗迹>\n符文族圣域最初是为符文族贵族修建的陵墓，既象征着他们的权势，也埋藏着无数文化珍宝。\n后来，普通符文族人也开始进入圣域。贵族担心权威受损，便修建了复杂的迷宫阻挡闯入者。错综复杂的通道也使这里成为理想的宝库，更多珍宝随之被封存其中。\n这些珍宝不仅有金银，还包括<QK>运用伊德凝胶的技术</>等珍贵的符文族知识。\n\n得知这些隐秘遗物后，一伙树古和舒拉克盗墓者组织了大规模探险，企图夺取符文族失落的遗产。\n\n<鲁纳迪姆遗迹>\n这里是遭符文族人诅咒的魔女<QK>葛兰达·耶罗内</>的居所。\n此地原是一座充满强大伊德能量的地下洞窟，后来成为符文族法师聚集、研究和磨炼魔法的圣所。\n\n<鲁纳图利姆遗迹>\n鲁纳图利姆是一座巨大的圆形竞技场。符文族人让被伊德侵蚀的生物在这里相互厮杀，以此取乐。\n其中一只生物被侵蚀带来的痛苦逼疯，开始吞食被自己击败的对手。每吞食一个猎物，它都会吸收更多伊德，变得更加强大。\n然而，这股力量也加剧了侵蚀。它的血肉不断扭曲，最终彻底失去自我，沦为只知杀戮的嗜血野兽。\n\n<知识殿堂旧址>\n这座宏伟的图书馆曾保存着符文族人关于<QK>伊德、伊德石</>和<QK>伊德凝胶</>的古老知识，后来遭龙帝布里特拉亵渎，成为储藏伊德凝胶和囚禁实验对象的场所。\n布里特拉的情报部队在寻找伊德凝胶的线索时，发现了知识殿堂以及希鲁斯要塞地下的隐秘储藏，随后将这里改造成生物实验室。时至今日，墙壁上仍残留着酷刑与暴行的痕迹。",
    "NoteData_Note_Seal_Altgard_037_01_text": "鲁古城重要人物志\n\n\n<<QK>葛兰达·耶罗内</>，被诅咒的魔女>\n徘徊在鲁纳迪姆的符文族死灵法师。葛兰达原本是一位才华出众、备受尊敬的法师，但恋人的不幸离世使她的人生逐渐崩塌。\n她试图在鲁纳迪姆施展强大的死灵法术，召回恋人的灵魂，却最终失败，反而使自己受到了诅咒。\n不久后，她被族人驱逐。她回到鲁纳迪姆，与恶灵为伴，对世人与同族的憎恨也日益加深。\n\n<<QK>伊德里斯</>，鲁城的迷途之子>\n他是一位执政官的儿子，以剑术闻名，自幼立誓守护鲁城。为了获得保护城市的力量，他痴迷于<QK>主神伊斯拉佩尔</>的力量，遍寻深渊，寻找能让自己穿越次元的伊斯拉佩尔遗物。\n永恒之塔崩塌、鲁城坠入深渊后，迷途之子伊德里斯也逐渐被人遗忘。",
    "NoteData_Note_D2_HQ2103500_01_text": "发件人：私人书记官戈德温\n收件人：库尔帕克前线指挥官\n\n致库尔帕克部队前线指挥官：\n\n立即将伊拉尔西格部队调往穆斯佩尔。\n\n西格伯特大人正在追捕从浮空神殿盗走重要物品的恶女克罗梅内。务必尽快与他会合，协助追捕。\n\n若不立即出动，此事将上报龙帝法夫尼尔。",
    "QuestString_STR_HQ2102120_quest_summary_journal_complete": "“最近，龙族和背叛的守护者似乎正在吉凯尔圣所策划着什么。”\n\n准备妥当后，你盘问了驻守圣所的龙战士，却未得到有价值的线索。幸好，乌尔贡找到了几名藏在临时避难处的军团兵。\n\n失踪的獠牙军团兵说，他们曾在吉凯尔圣所附近见到一群可疑人物，但仍有其他同伴下落不明。为了继续搜寻，你紧急修复了一台塞尔维斯，试图找到其余失踪士兵。",
    "QuestString_STR_HQ2101040_quest_summary_journal_complete": "“你的灵魂会被封进法夫尼石，肉体则会像那些仆从一样，成为龙帝法夫尼尔的武器！”\n\n佩莱尔担心魔女动过守护村庄的宝玉，便请你和村庄自警团一同检查。\n\n你触碰宝玉的瞬间，周围响起了神秘的声音，一群来历不明的袭击者也突然现身。混乱中，艾尔维达再次出现，坚持要求摧毁宝玉。宝玉最终被击碎后，诡异的声音与袭击者都消失得无影无踪。\n\n艾尔维达表明自己是命运三女神的弟子，再次警告你村民面临的危险，并让你前往她的藏身处了解真相。",
    "String_UI_SETTING_TAB_GRAPHIC_SUBTAB_OPTIMIZE_UPSCALER_DESC_body": "以低于显示器分辨率的分辨率渲染3D画面，以提高游戏运行性能。\nTAA - 基础抗锯齿技术，可减少画面锯齿，以较低的性能开销提供适中的画质，保证游戏稳定运行。\nTSR - Epic Games集成于虚幻引擎的超分辨率技术，兼顾画面一致性、兼容性与性能。\nDLSS - NVIDIA基于AI的超分辨率技术。在支持的显卡上，可显著提高性能，并改善清晰度、噪点及拖影。\nFSR - AMD的通用超分辨率技术，兼容多种硬件，兼顾稳定的画质与性能。\n\n※ 使用RTX 5000系列笔记本显卡时，请先在NVIDIA控制面板关闭G-SYNC并开启垂直同步，再启用DLSS帧生成功能。",
}


def patterned(key, source):
    if key.startswith("String_STR_ITEM_"):
        match = re.fullmatch(r"(Resurrection Spiritstone|Instant Clear Ticket: Daily Dungeon|Instant Clear Ticket: Nightmare|Key: Hidden Cube|Customization Voucher Chest) \((7|10|30) Days\) \(Bound\)", source)
        if match:
            names = {"Resurrection Spiritstone": "复活灵石", "Instant Clear Ticket: Daily Dungeon": "每日副本扫荡券", "Instant Clear Ticket: Nightmare": "噩梦扫荡券", "Key: Hidden Cube": "隐藏宝箱钥匙", "Customization Voucher Chest": "外形变更券箱"}
            return names[match[1]] + "（" + match[2] + "天）（绑定）"
    if "PERIOD_COLLECTION" in key:
        match = re.fullmatch(r"(Retrieve )?(.+) Armor (I|II)", source)
        if match and match[2] in ARMOR_NAMES:
            return ("收集" if match[1] else "") + ARMOR_NAMES[match[2]] + "防具" + match[3]
    if key.startswith("AchievementString_"):
        match = re.fullmatch(r"Collect (\d+) Types? of (Expedition|Shugo Festival) Artwork", source)
        if match:
            return "收集" + match[1] + "种" + {"Expedition": "远征", "Shugo Festival": "树古庆典"}[match[2]] + "画作"
    if key.startswith("InputKeyMapping_"):
        match = re.fullmatch(r"Batch equip Set ([123])\.", source)
        if match:
            return "一键装备第" + match[1] + "套预设。"
    if key.startswith("String_STR_ARCANA_MATERIAL"):
        match = re.fullmatch(r"Can be registered as a material when enhancing Arcana\.\nIncreases Enhance EXP by (\d+)\.", source)
        if match:
            return "可作为阿尔卡纳强化材料。\n增加" + match[1] + "点强化经验值。"
    if key.startswith("Title_"):
        match = re.fullmatch(r"Cleared Sealed Dungeon: \[Ruins of the Ancient City of Ru\]\nFollowed various clues in (Altgard|Verteron) and arrived at the ruins of Ru\.\nFought past what traces of life remain to reach the gate\.", source)
        if match:
            place = {"Altgard": "阿尔特盖德", "Verteron": "贝尔特伦"}[match[1]]
            return "通关封印副本：[鲁古城遗迹]\n循着" + place + "的各种线索，抵达鲁古城遗迹。\n击退遗迹中的残存生物，抵达大门。"
    return None
