"""Atreia-authored, narrowly matched Japanese UI/skill reviews.

No upstream translation payload is read. Unknown prose remains unresolved.
The caller binds each result to the complete Japanese and English source hashes.
"""
import re
import unicodedata
from functools import lru_cache

SKILL_PROPERTIES = {
    'ノンターゲット': '非锁定',
    '移動可能': '可移动施放',
    'チャージ スキル': '蓄力技能',
}
SKILL_NAMES = {'昇天打': '升天击', '連環拳': '连环拳', '回転脚': '回旋踢', '幻影脚': '幻影踢',
               '疾風撃': '疾风击', '緊急回避': '紧急回避', '元素融合': '元素融合'}

# Exact UI labels, additionally bound to the full source hashes by the caller.
UI_LABELS = {
    'HERO': '英雄', 'ELITE': '精英', 'LEGEND': '传说',
    'FAIL': '失败', 'TOUCH': '点击', 'All': '全部',
    'ACCESSORIES': '饰品', 'Headphone': '耳机', 'BOOST': '增强',
    'SET': '套装', '[OFF]': '[关闭]', '(MAX)': '（最大）',
    'AUTO': '自动', 'Bonus': '加成', 'Round': '回合',
    'COMBO': '连击', 'PASSIVE': '被动', 'ACTIVE': '主动',
    'Level Up': '等级提升', 'Point': '点数', 'Part {0}': '第{0}部分',
}

REGIONS = {
    'AS': ('アジア', '日本(東京)', '東北アジア', '亚洲', '日本（东京）', '东北亚'),
    'JP': ('日本', '韓国', '日本', '日本', '韩国', '日本'),
    'NAE': ('北米 - 東部', 'アメリカ(バージニア)', 'アメリカ東部地域', '北美东部', '美国（弗吉尼亚州）', '美国东部'),
    'NAW': ('北米 - 西部', 'アメリカ(オレゴン)', 'アメリカ西部地域', '北美西部', '美国（俄勒冈州）', '美国西部'),
    'EU': ('ヨーロッパ', 'ドイツ(フランクフルト)', 'ドイツ、アイルランド、イギリス、フランス、スウェーデン、イタリア、スペイン、スイス',
           '欧洲', '德国（法兰克福）', '德国、爱尔兰、英国、法国、瑞典、意大利、西班牙、瑞士'),
}

QUEST_CLAUSES = {
    '「それじゃ、私たちの最初の共同作戦を始めましょうか？」': '“那么，就开始我们的第一次联合行动吧？”',
    'クロリスと協力して、アーティファクトを探すことにした。': '决定与克萝莉丝合作，寻找神器。',
    'クロリス団は、エルテネン結界塔廃墟にアーティファクトがあると推測し、そこに野営地を設けてアーティファクトの調査を続けているという。': '据说克萝莉丝团推测埃尔特内结界塔废墟中藏有神器，因此在那里设立营地，持续展开调查。',
    'しかし、実際に廃墟調査の野営地を守っているクロリス団は、レパル団との勢力争いのため、アーティファクトの調査が思うように進んでいなかった。': '然而，驻守废墟调查营地的克萝莉丝团正与龙信徒争夺势力范围，神器调查迟迟没有进展。',
    'クロリス団はレパル団との勢力争いのため、アーティファクトの調査が思うように進んでいなかった。': '克萝莉丝团正与龙信徒争夺势力范围，神器调查迟迟没有进展。',
    '何の情報もない中、エルテネン結界塔廃墟を捜索していたところ、謎の遺物を発見した。': '在毫无线索的情况下搜索埃尔特内结界塔废墟时，发现了一件神秘遗物。',
}

WING_STATS = {
    'HP': '生命力', 'MP': '精神力', 'HP回復': '生命力恢复', 'MP回復': '精神力恢复',
    'HP自然回復': '生命力自然恢复', 'MP自然回復': '精神力自然恢复',
    'HPポーション回復': '生命力药水恢复', 'HPポーション回復増加': '生命力药水恢复增幅',
    'MP消耗減少': '精神力消耗减少', '飛行力': '飞行力',
    '追加攻撃力': '额外攻击力', '追加防御力': '额外防御力', '追加命中': '额外命中', '追加回避': '额外回避',
    '前方攻撃力': '正面攻击力', '後方攻撃力': '背面攻击力', '後方クリティカル抵抗': '背面致命一击抵抗',
    'クリティカル': '致命一击', 'クリティカル攻撃力': '致命一击攻击力', 'クリティカル抵抗': '致命一击抵抗',
    'ガード': '盾牌防御', 'ガード貫通': '盾牌防御贯穿', '貫通': '贯穿',
    '状態異常抵抗': '异常状态抵抗', '状態異常的中': '异常状态命中',
    '再使用時間減少': '冷却时间缩减', '受ける治癒量増加': '所受治疗量增加',
    'ダメージ増幅': '伤害增幅', 'ダメージ耐性': '伤害抗性',
    'ボス攻撃力': '首领攻击力', 'ボス防御力': '首领防御力',
    'ボス ダメージ増幅': '首领伤害增幅', 'ボス ダメージ耐性': '首领伤害抗性',
    'PvE攻撃力': 'PvE攻击力', 'PvEダメージ増幅': 'PvE伤害增幅', 'PvEダメージ耐性': 'PvE伤害抗性',
    'PvP防御力': 'PvP防御力', 'PvPダメージ増幅': 'PvP伤害增幅', 'PvPダメージ耐性': 'PvP伤害抗性',
}
WING_STATS.update({
    'HP増加': '生命力增加', 'MP増加': '精神力增加', '行動力': '行动力', '行動力自然回復': '行动力自然恢复',
    '戦闘時のHP自然回復': '战斗中生命力自然恢复', '戦闘時のMP自然回復': '战斗中精神力自然恢复',
    '戦闘時の行動力自然回復': '战斗中行动力自然恢复', '非戦闘時のHP自然回復': '非战斗时生命力自然恢复',
    '非戦闘時のMP自然回復': '非战斗时精神力自然恢复', '非戦闘時の行動力自然回復': '非战斗时行动力自然恢复',
    'PvE命中': 'PvE命中', 'PvE回避': 'PvE回避', 'PvE防御力': 'PvE防御力',
    'PvP命中': 'PvP命中', 'PvP回避': 'PvP回避', 'PvP攻撃力': 'PvP攻击力',
    'PvPクリティカル': 'PvP致命一击', 'PvPクリティカル抵抗': 'PvP致命一击抵抗',
    'クリティカル防御力': '致命一击防御力', 'クリティカル ダメージ増幅': '致命一击伤害增幅',
    'クリティカル ダメージ耐性': '致命一击伤害抗性', '前方クリティカル': '正面致命一击',
    '後方クリティカル': '背面致命一击', '前方防御力': '正面防御力', '後方防御力': '背面防御力',
    '後方ダメージ増幅': '背面伤害增幅', '後方ダメージ耐性': '背面伤害抗性',
    '多段ヒット抵抗': '多段攻击抵抗', '多段ヒット的中': '多段攻击命中', '完璧抵抗': '完美抵抗',
    '封魂石追加ダメージ': '封魂石追加伤害', '強打抵抗': '强击抵抗', '鉄壁': '铁壁', '鉄壁貫通': '铁壁贯穿',
    '再生': '再生', '戦闘速度': '战斗速度', '移動速度': '移动速度', '飛行速度': '飞行速度',
})


def reviewed_item_stats(key, japanese, own):
    """Keep our source-matched item name; rebuild every stat from Japanese.

    Unknown labels or any nonnumeric stat value refuse the entire block. The
    caller must prove the item's English name/description source is unchanged.
    """
    wing = key.startswith('String_STR_ITEM_WING_')
    title_item = key.startswith('String_STR_ITEM_TITLE_')
    if not (wing or title_item) or not key.endswith('_DESC_body'):
        return None
    lines = japanese.splitlines()
    jp_end = 'を獲得します。' if wing else 'のタイトルを獲得します。'
    cn_end = '。' if wing else '称号。'
    if not lines or not re.fullmatch(r'\[[^\[\]<>\n]+\]' + re.escape(jp_end), lines[0]):
        return None
    name = re.fullmatch(r'获得\[([^\[\]<>\n]+)\]' + re.escape(cn_end), own.split('\n', 1)[0])
    if not name or not re.search(r'[\u3400-\u9fff]', name[1]):
        return None
    title = name[1].removesuffix('（绑定）').removesuffix('(绑定)')
    if '(刻印)' in lines[0]:
        title += '（绑定）'
    output = ['获得[' + title + ']' + cn_end]
    headings = []
    for line in lines[1:]:
        if not line:
            output.append('')
        elif line in ('[装着効果]', '[保有効果]'):
            headings.append(line)
            output.append('[装备效果]' if line == '[装着効果]' else '[持有效果]')
        else:
            match = re.fullmatch(r'(.+?)[：:]?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?%?)', line)
            if not headings or not match or match[1] not in WING_STATS:
                return None
            output.append(WING_STATS[match[1]] + '：' + match[2])
    if headings != (['[装着効果]', '[保有効果]'] if wing else ['[保有効果]', '[装着効果]']):
        return None
    return '\n'.join(output)


def reviewed_wing_stats(key, japanese, own):
    return reviewed_item_stats(key, japanese, own) if key.startswith('String_STR_ITEM_WING_') else None

# Complete Japanese clauses only. Slots stand for original runtime parameters
# or literal numbers, never arbitrary Japanese prose. Unknown clauses block the
# entire description; there is no partial Japanese/Chinese publication path.
CLAUSES = (
    ('{0}m内の最大{1}体の敵に<chat_combat>{2}～{3}</>のダメージを与えます。',
     '对{0}米范围内最多{1}名敌人造成<chat_combat>{2}～{3}</>伤害。'),
    ('スキル使用中はガードが{0}増加します。', '技能施放期间，盾牌防御提高{0}。'),
    ('スキル クリティカルが{0}%増加します。', '技能致命一击提高{0}%。'),
    ('スキル速度が{0}%増加します。', '技能速度提高{0}%。'),
    ('スキル速度が{0}%、スキル クリティカルが{1}%増加します。', '技能速度提高{0}%，技能致命一击提高{1}%。'),
    ('的中時に[連環拳]の再使用時間が{0}減少します。', '命中时，[连环拳]的冷却时间减少{0}。'),
    ('グロッキー ゲージ ダメージ量{0}', '失衡值伤害{0}'),
    ('{0}回重複時に爆発ダメージ', '叠加{0}次时造成爆炸伤害'),
    ('HP{0}%吸収', '吸收{0}%生命力'),
    ('特化効果は暴走状態でも同様に適用されます。', '特化效果在暴走状态下同样生效。'),
    ('対象がNPCの場合、{0}%の確率で気絶が的中します。', '目标为非玩家单位时，眩晕的命中概率为{0}%。'),
    ('{0}m内の最大{1}体の敵に<chat_combat>{2}～{3}</>のダメージを与えて、怒りを{4}回復します。',
     '对{0}米范围内最多{1}名敌人造成<chat_combat>{2}～{3}</>伤害，并恢复{4}怒气。'),
    ('怒り回復効果が適用されません。', '怒气恢复效果不生效。'),
    ('最大{0}段階チャージ スキル', '最多可蓄力{0}阶段的技能'),
    ('対象がNPCの場合、{0}%の確率で空中束縛が的中します。', '目标为非玩家单位时，空中束缚的命中概率为{0}%。'),
    ('{0}m内の対象を中心に最大{1}体の敵に<chat_combat>{2}～{3}</>のダメージを与えて、{4}%の確率で{5}間、気絶状態にします。',
     '以{0}米内的目标为中心，对最多{1}名敌人造成<chat_combat>{2}～{3}</>伤害，并有{4}%的概率使其眩晕，持续{5}。'),
    ('即時発動スキル', '瞬发技能'),
    ('{0}m内の対象に<chat_combat>{1}～{2}</>のダメージを与えて、疾風撃ダメージを受けた対象を自分の近くに引き寄せます。',
     '对{0}米内的目标造成<chat_combat>{1}～{2}</>伤害，并将受到疾风击伤害的目标拉至自身附近。'),
    ('最大{0}回まで重複します。', '最多可叠加{0}次。'),
    ('PvEダメージ増幅{0}%増加', 'PvE伤害增幅提高{0}%'),
    ('PvPダメージ増幅{0}%増加', 'PvP伤害增幅提高{0}%'),
    ('対象に{0}秒間、連続スキル[幻影脚]が活性化されます。', '可对目标施放连续技[幻影踢]，有效时间为{0}秒。'),
    ('クリティカル的中条件が削除されます。', '移除致命一击命中的触发条件。'),
    ('[緊急回避]使用または飛行状態の場合、{0}m内の対象に突進し、<chat_combat>{1}～{2}</>のダメージを与えて、{3}%の確率で{4}間、気絶状態にします。',
     '使用[紧急回避]后或处于飞行状态时，冲向{0}米内的目标，造成<chat_combat>{1}～{2}</>伤害，并有{3}%的概率使其眩晕，持续{4}。'),
    ('最大チャージ時に{0}%の確率で{1}間、空中束縛状態にします。', '蓄力至最大阶段时，有{0}%的概率使目标陷入空中束缚，持续{1}。'),
    ('怒りを{0}回復します。', '恢复{0}怒气。'),
    ('HPを{0}%吸収します。', '吸收{0}%生命力。'),
    ('{0}m内の対象に突進し、<chat_combat>{1}～{2}</>のダメージを与えます。', '冲向{0}米内的目标，造成<chat_combat>{1}～{2}</>伤害。'),
    ('{0}m内の対象に突進し、最大{1}体の敵に<chat_combat>{2}～{3}</>のダメージを与えて、クリティカルで的中します。',
     '冲向{0}米内的目标，对最多{1}名敌人造成<chat_combat>{2}～{3}</>伤害，并以致命一击命中。'),
    ('スキル命中が{0}%増加します。', '技能命中提高{0}%。'),
    ('行動不可免疫状態の場合、ダメージが{0}%増加します。', '目标处于无法行动免疫状态时，伤害提高{0}%。'),
    ('ガードと回避を無視して的中します。', '命中时无视盾牌防御和回避。'),
    ('的中時に{0}間、自分のクリティカル ダメージ増幅が{1}%増加します。', '命中后，自身致命一击伤害增幅提高{1}%，持续{0}。'),
    ('{0}m内の対象の前方に突進し、<chat_combat>{1}～{2}</>のダメージを与えます。', '冲至{0}米内的目标前方，造成<chat_combat>{1}～{2}</>伤害。'),
    ('必ず多段ヒットで的中します。', '必定以多段攻击命中。'),
    ('ガード成功時に{0}m内の対象に<chat_combat>{1}～{2}</>のダメージを与えて、{3}%の確率で{4}間、気絶状態にします。',
     '盾牌防御成功时，对{0}米内的目标造成<chat_combat>{1}～{2}</>伤害，并有{3}%的概率使其眩晕，持续{4}。'),
    ('{0}m内の最大{1}体の敵に<chat_combat>{2}～{3}</>のダメージを与えて、怒りを{4}～{5}回復します。',
     '对{0}米范围内最多{1}名敌人造成<chat_combat>{2}～{3}</>伤害，并恢复{4}～{5}怒气。'),
    ('{0}m内の対象に突進し、最大{1}体の敵に<chat_combat>{2}～{3}</>のダメージを与えます。',
     '冲向{0}米内的目标，对最多{1}名敌人造成<chat_combat>{2}～{3}</>伤害。'),
    ('{0}m内の対象に突進し、最大{1}体の敵に<chat_combat>{2}～{3}</>のダメージを与えて、{4}%の確率で{5}間、空中束縛状態にします。',
     '冲向{0}米内的目标，对最多{1}名敌人造成<chat_combat>{2}～{3}</>伤害，并有{4}%的概率使其陷入空中束缚，持续{5}。'),
    ('状態異常抵抗{0}%増加', '异常状态抵抗提高{0}%'),
    ('強打{0}%増加', '强击提高{0}%'),
    ('前方ダメージ増幅<chat_combat>{0}%</>増加', '正面攻击伤害增幅提高<chat_combat>{0}%</>'),
    ('戦闘速度<desc_point>{0}%</>増加', '战斗速度提高<desc_point>{0}%</>'),
    ('前方ダメージ増幅<desc_point>{0}%</>増加', '正面攻击伤害增幅提高<desc_point>{0}%</>'),
    ('連続で最大{0}回まで発動できます。', '最多可连续发动{0}次。'),
    ('精霊がスキルを使用するたびにスピリットマスターは元素を獲得します。', '精灵每次使用技能时，精灵星都会获得元素。'),
    ('元素が{0}重複になると{1}元素状態になり、[元素融合]スキルを使うことができます。',
     '元素叠加至{0}层时，进入{1}元素状态，可以使用[元素融合]技能。'),
    ('{0}元素効果を獲得した状態でのみ[元素融合]を使用できます。', '仅在获得{0}元素效果时可以使用[元素融合]。'),
    ('[元素融合]を使用すると{0}元素は即座に削除されます。', '使用[元素融合]后，立即移除{0}元素。'),
    ('{0}元素状態になると追加で元素を獲得できません。', '进入{0}元素状态后，无法继续获得元素。'),
    ('暴走状態に入ります。', '进入暴走状态。'),
    ('毎秒ごとに怒りを消耗し、怒りが{0}になると暴走状態が終了します。', '每秒消耗怒气；怒气降至{0}时，暴走状态结束。'),
    ('戦闘速度<chat_combat>{0}%</>増加', '战斗速度提高<chat_combat>{0}%</>'),
    ('すべてのスキルの暴走状態適用', '所有技能均获得暴走状态效果'),
    ('自分の気絶、転倒、空中束縛、掴み、氷結、恐怖状態を解除し、{0}間、強靭さ状態になります。',
     '解除自身眩晕、倒地、空中束缚、擒拿、冰冻和恐惧状态，并进入强韧状态，持续{0}。'),
    ('再使用時間減少効果に影響されません。', '不受冷却时间缩减效果影响。'),
    ('多段ヒットで的中する確率が{0}%増加し、HPを{1}%吸収します。', '多段攻击命中概率提高{0}%，并吸收{1}%生命力。'),
    ('クリティカル的中時に活性化され、{0}m内の最大{1}体の敵に<chat_combat>{2}～{3}</>のダメージを与えます。',
     '致命一击命中后可发动，对{0}米内最多{1}名敌人造成<chat_combat>{2}～{3}</>伤害。'),
    ('的中時に{0}%の確率で[回転脚]が活性化されます。', '命中时，有{0}%的概率激活[回旋踢]。'),
    ('{0}間、対象の状態異常抵抗を{1}%減少させます。', '使目标的异常状态抵抗降低{1}%，持续{0}。'),
    ('最初の打撃と最後の打撃時に対象の前方に突進します。', '首次和最后一次攻击时，会冲至目标前方。'),
    ('暴走状態では怒り回復効果が適用されません。', '暴走状态下，怒气恢复效果不生效。'),
    ('前方的中時にダメージ量が{0}%増加します。', '从正面命中时，伤害提高{0}%。'),
    ('的中時にクリティカルで的中します。', '命中时必定为致命一击。'),
    ('ガード成功時に{0}m内の最大{1}体の敵に<chat_combat>{2}～{3}</>のダメージを与えて、{4}%の確率で{5}間、気絶状態にします。',
     '盾牌防御成功时，对{0}米内最多{1}名敌人造成<chat_combat>{2}～{3}</>伤害，并有{4}%的概率使其眩晕，持续{5}。'),
    ('敵は対象を中心に引き寄せられます。', '将敌人拉向目标所在位置。'),
    ('バリアを破壊します。', '击破护盾。'),
    ('{0}間、自分の前方ダメージ増幅が{1}%増加します。', '自身正面攻击伤害增幅提高{1}%，持续{0}。'),
    ('{0}m内の最大{1}体の敵に<chat_combat>{2}～{3}</>のダメージを与えて、{4}後に<chat_combat>{5}～{6}</>の追加ダメージを与えます。',
     '对{0}米内最多{1}名敌人造成<chat_combat>{2}～{3}</>伤害，并在{4}后造成<chat_combat>{5}～{6}</>追加伤害。'),
    ('敵を{0}%の確率で{1}間、空中束縛状態にします。', '有{0}%的概率使敌人陷入空中束缚，持续{1}。'),
    ('自分の行動力を{0}回復します。', '恢复自身{0}行动力。'),
    ('的中時に[昇天打]の再使用時間が{0}減少します。', '命中时，[升天击]的冷却时间减少{0}。'),
)
CLAUSES += (
    ('防具の回避が増加します。', '增加防具回避。'),
    ('防具の魔法回避が増加します。', '增加防具魔法回避。'),
    ('防具の物理回避が増加します。', '增加防具物理回避。'),
    ('キャラクターの追加回避です。', '角色的额外回避。'),
    ('キャラクターの追加魔法回避です。', '角色的额外魔法回避。'),
    ('キャラクターの追加物理回避です。', '角色的额外物理回避。'),
    ('キャラクターの魔法攻撃を回避します。', '回避其他角色的魔法攻击。'),
    ('キャラクターの物理攻撃を回避します。', '回避其他角色的物理攻击。'),
    ('キャラクターの攻撃を回避します。', '回避其他角色的攻击。'),
    ('攻撃を回避するとダメージを受けません。', '回避攻击时，不会受到伤害。'),
    ('魔法攻撃を回避するとダメージを受けません。', '回避魔法攻击时，不会受到伤害。'),
    ('物理攻撃を回避するとダメージを受けません。', '回避物理攻击时，不会受到伤害。'),
    ('スキルを回避するとダメージを受けません。', '回避技能时，不会受到伤害。'),
    ('物理スキル回避です。', '物理技能回避。'),
    ('物理スキルを回避するとダメージを受けません。', '回避物理技能时，不会受到伤害。'),
    ('魔法スキル抵抗です。', '魔法技能抵抗。'),
    ('魔法スキルを抵抗するとダメージを受けません。', '抵抗魔法技能时，不会受到伤害。'),
    ('回避率は最大<Mythic>{0}%</>です。', '回避率上限为<Mythic>{0}%</>。'),
    ('抵抗は最大<Mythic>{0}%</>です。', '抵抗率上限为<Mythic>{0}%</>。'),
    ('ガード ダメージ{0}%減少', '格挡伤害减少{0}%'),
    ('確定武器ガード', '必定触发武器防御'),
    ('一時的にすべてのダメージを確定で回避します。', '短时间内必定回避所有伤害。'),
    ('回避成功時に{0}間、移動速度が{1}%増加し、MPと行動力を<chat_combat>{2}</>、HPの{3}%を{4}回、回復します。', '回避成功时，移动速度提高{1}%，持续{0}，并恢复{4}次精神力和行动力<chat_combat>{2}</>、生命力{3}%。'),
    ('[緊急回避]使用または飛行状態の場合、{0}m内の対象に移動して、<chat_combat>{1}～{2}</>のダメージを与えて、{3}%の確率で{4}間、気絶状態にします。', '使用[紧急回避]后或处于飞行状态时，移动至{0}米内的目标，造成<chat_combat>{1}～{2}</>伤害，并有{3}%的概率使其眩晕，持续{4}。'),
    ('多段ヒットで的中する確率が{0}%増加し、行動力を{1}回復します。', '多段攻击命中概率提高{0}%，并恢复{1}行动力。'),
    ('{0}m内の対象を中心に{1}m内の最大{2}体の敵に<chat_combat>{3}～{4}</>のダメージを与えて、{5}%の確率で{6}間、空中束縛状態にします。', '以{0}米内的目标为中心，对{1}米范围内最多{2}名敌人造成<chat_combat>{3}～{4}</>伤害，并有{5}%的概率使其陷入空中束缚，持续{6}。'),
    ('対象が氷結、鈍化状態の場合、空中束縛確率が{0}倍で適用されます。', '目标处于冰冻或减速状态时，空中束缚概率提高至{0}倍。'),
    ('<desc_point>{0}</>間、攻撃を受けるたびに<desc_point>{1}</>ずつ、最大<desc_point>{2}</>の衝撃を吸収するバリアを生成します。', '生成护盾，持续<desc_point>{0}</>，每次受到攻击时吸收<desc_point>{1}</>伤害，最多吸收<desc_point>{2}</>伤害。'),
    ('アビス下層の入場中は利用時間が消費されます。', '进入欧比斯下层期间会消耗使用时间。'),
    ('基本利用時間は毎週{0}時間に初期化されます。', '每周将基本使用时间重置为{0}小时。'),
    ('移動速度{0}%増加', '移动速度提高{0}%'),
    ('行動不可状態の時に怒り消耗量が{0}%減少します。', '无法行动时，怒气消耗量减少{0}%。'),
    ('すべてのスキル再使用時間{0}%減少', '所有技能的冷却时间缩短{0}%'),
    ('一時的にガード ダメージ減少が{0}%増加し、確定武器ガードをします。', '暂时使格挡伤害减免提高{0}%，并必定触发武器防御。'),
    ('ガード成功時に{0}回、怒りを<chat_combat>{1}</>、行動力を<chat_combat>{2}</>回復します。', '防御成功时，恢复{0}次怒气<chat_combat>{1}</>和行动力<chat_combat>{2}</>。'),
    ('連続で最大{0}回まで発動することができ、ガード成功時に{1}回、怒りを<chat_combat>{2}</>、行動力を<chat_combat>{3}</>回復します。', '最多可连续发动{0}次；防御成功时，恢复{1}次怒气<chat_combat>{2}</>和行动力<chat_combat>{3}</>。'),
    ('連続で最大{0}回まで発動することができ、ガード成功時に{1}回、怒りを<chat_combat>{2}</>、行動力を<chat_combat>{3}</>回復し、{4}間、移動速度が{5}%増加します。', '最多可连续发动{0}次；防御成功时，恢复{1}次怒气<chat_combat>{2}</>和行动力<chat_combat>{3}</>，并使移动速度提高{5}%，持续{4}。'),
    ('連続で最大{0}回まで発動することができ、ガード成功時に{1}回、怒りを<chat_combat>{2}</>、行動力を<chat_combat>{3}</>、HPを{4}%回復し、{5}間、移動速度が{6}%増加します。', '最多可连续发动{0}次；防御成功时，恢复{1}次怒气<chat_combat>{2}</>、行动力<chat_combat>{3}</>和生命力{4}%，并使移动速度提高{6}%，持续{5}。'),
    ('{0}m内の対象を中心に{1}m内の最大{2}体の敵に<chat_combat>{3}～{4}</>のダメージを与えて、{5}%の確率で{6}間、気絶状態にします。', '以{0}米内的目标为中心，对{1}米范围内最多{2}名敌人造成<chat_combat>{3}～{4}</>伤害，并有{5}%的概率使其眩晕，持续{6}。'),
    ('{0}m内の対象を中心に{1}m内の最大{2}体の敵に<chat_combat>{3}～{4}</>のダメージと{5}のMPダメージを与えて、{6}%の確率で{7}間、気絶状態にします。', '以{0}米内的目标为中心，对{1}米范围内最多{2}名敌人造成<chat_combat>{3}～{4}</>伤害和{5}精神力伤害，并有{6}%的概率使其眩晕，持续{7}。'),
    ('的中時に{0}間、攻撃力が{1}%増加します。', '命中时，攻击力提高{1}%，持续{0}。'),
    ('的中人数に比例して、防御力が最大{0}%増加します。', '根据命中人数提高防御力，最多提高{0}%。'),
    ('状態異常持続中は怒り消耗{0}%減少', '异常状态持续期间，怒气消耗减少{0}%。'),
    ('再使用時間{0}%減少', '冷却时间缩短{0}%。'),
)
HEADINGS = {'<chat_combat>[暴走状態]</>': '<chat_combat>[暴走状态]</>',
            '<chat_combat>[幻影脚]</>': '<chat_combat>[幻影踢]</>', '暴走状態': '暴走状态'}
SLOTS = re.compile(r'\{(\d+)\}')
VALUES = re.compile(r'\{[^{}]*\}|[0-9]+(?:[.,][0-9]+)*')


@lru_cache(maxsize=4096)
def clause_translation(source):
    for japanese, chinese in CLAUSES:
        pattern, position = '', 0
        for match in SLOTS.finditer(japanese):
            pattern += re.escape(japanese[position:match.start()]) + r'(?P<p' + match[1] + r'>§\d+§)'
            position = match.end()
        pattern += re.escape(japanese[position:])
        found = re.fullmatch(pattern, source)
        if found:
            ordered = [found.group('p' + str(index)) for index in range(len(found.groupdict()))]
            return chinese.format(*ordered)
    return None


def skill_description(japanese):
    if '§' in japanese:
        return None
    values = []
    def protect(match):
        values.append(match.group())
        return '§' + str(len(values) - 1) + '§'
    protected = VALUES.sub(protect, japanese)
    output = []
    for line in protected.splitlines(keepends=True):
        body = line.rstrip('\r\n')
        ending = line[len(body):]
        if not body:
            output.append(ending)
            continue
        if body in HEADINGS:
            output.append(HEADINGS[body] + ending)
            continue
        pieces = re.findall(r'[^。]*。|[^。]+$', body)
        translated = [clause_translation(piece) for piece in pieces]
        if not pieces or any(piece is None for piece in translated):
            return None
        output.append(''.join(translated) + ending)
    return re.sub(r'§(\d+)§', lambda m: values[int(m[1])], ''.join(output))


def reviewed_translation(key, japanese):
    if key == 'String_STR_ITEM_TITLE_D_C_SEALDUNGEON_017_B_body' and japanese == 'タイトル：リンゴの木を1本植える':
        return '称号：种下1棵苹果树'
    if key == 'String_STR_ITEM_TITLE_D_C_SEALDUNGEON_017_B_DESC_body' and japanese == '[リンゴの木を1本植える]のタイトルを獲得します。\n\n[保有効果]\nPvE回避5\n\n[装着効果]\n封魂石追加ダメージ7':
        return '获得[种下1棵苹果树]称号。\n\n[持有效果]\nPvE回避：5\n\n[装备效果]\n封魂石追加伤害：7'
    exact_labels = {
        'String_STR_sub_N_CLB01_body': ('プロミスナイン', 'fromis_9组合'),
        'String_STR_ITEM_TOOLTIP_Cash_body': ('Cash', '付费道具'),
        'String_UI_HUD_TARGETINFO_TAG_MANNER_body': ('MANNER', '礼让'),
        'String_UI_RIFT_SKIRMISH_PVP_MODE_ICON_TEXT_body': ('S-PvP', 'S-PvP'),
        'String_UI_DAMAGEANALYZER_SKILL_RESTORATION_COUNT_body': ('RSTO', '恢复'),
        'String_UI_DAMAGEANALYZER_SKILL_IRONWALL_COUNT_body': ('ENDR', '铁壁'),
        'String_UI_DAMAGEANALYZER_SKILL_HARDHIT_COUNT_body': ('DOUB', '强击'),
        'String_UI_DAMAGEANALYZER_SKILL_FRONTATTACK_COUNT_body': ('FRNT', '正面攻击'),
        'String_UI_DAMAGEANALYZER_SKILL_ADDITIONALHIT_COUNT_body': ('MULT', '追加攻击'),
    }
    if key in exact_labels and japanese == exact_labels[key][0]:
        return exact_labels[key][1]
    if key in {'SkillString_SkillString_ETC_9351_skill_desc_effect', 'SkillString_SkillString_ETC_9351_skill_name'} and japanese == 'EndCastSkillByCasterをDispel':
        return '驱散EndCastSkillByCaster效果'
    if key.startswith('NpcTalk_'):
        if japanese == '…':
            return '……'
        if japanese == 'それじゃ、私たちの最初の共同作戦を始めましょうか？\n新しい仲間になったんだから、もう少し喜んでほしいわ。':
            return '那么，就开始我们的第一次联合行动吧？\n既然已经成为新的伙伴，就表现得高兴一点嘛。'
        if japanese == 'いつの話をしてるの？\nレパル団が真っ先に占領したのが神秘の泉なのよ。':
            return '你说的都是什么时候的事了？\n龙信徒最先占领的就是神秘之泉。'
    if key.startswith('QuestString_STR_HQ1103280_quest_summary_'):
        lines = japanese.split('\n')
        if all(not line or line in QUEST_CLAUSES for line in lines):
            return '\n'.join(QUEST_CLAUSES.get(line, '') for line in lines)
    if key == 'NpcTalk_6B632FCDECEE4325928285141BB9B30F_cv_text' and japanese == '待て！\n最初の文字だけ見ると<QK>湖の中の洞窟</>という言葉になる。':
        return '等等！\n只看每句开头的字，连起来就是<QK>湖中的洞窟</>。'
    if key.startswith('String_'):
        if key.startswith('String_UI_desc_'):
            return skill_description(japanese)
        if key.startswith('String_STR_ITEM_SOCIALACTION_'):
            actions = {'視線固定': '视线锁定', 'ムード': '氛围', 'ときめく': '心动', 'レディ': '准备就绪',
                       '躊躇う': '犹豫', '優雅': '优雅', '安定': '冷静', '生意気': '嚣张'}
            match = re.fullmatch(r'エモート\[([^\[\]]+)\]が追加されます。\nチャット ウィンドウに「/\1」を入力するとエモートを使用できます。', japanese)
            if match and match[1] in actions:
                return '习得情感动作[' + actions[match[1]] + ']。\n在聊天窗口输入“/' + match[1] + '”可使用该动作。'
        region = key.removeprefix('String_UI_GLOBAL_SERVICE_SERVER_REGION_DESC_').removesuffix('_body')
        if key.startswith('String_UI_GLOBAL_SERVICE_SERVER_REGION_DESC_') and region in REGIONS:
            name, location, recommended, cn_name, cn_location, cn_recommended = REGIONS[region]
            tag = '<ref style="Lobby_GlobalRegionTooltip_Etc" attr="color">'
            expected = name + tag + 'サーバー位置：' + location + ' - 推奨地域：' + recommended + '</>'
            if japanese == expected:
                return cn_name + tag + '服务器位置：' + cn_location + ' - 推荐地区：' + cn_recommended + '</>'
        if japanese in UI_LABELS:
            return UI_LABELS[japanese]
        maximum = re.fullmatch(r'MAX ([0-9]+(?:\.[0-9]+)?%)', japanese)
        if key.startswith('String_UI_NPCSHOP_ITEMLIST_BUTTON_ADDMAX') and maximum:
            return '最大' + maximum[1]
        if key.startswith('String_STR_G_ITEM_'):
            season = re.fullmatch(r'グローバル シーズン(\d+)(月間パス|パス)( アンロック|経験値)_(天族|魔族)(?:_(無償|有償))?', japanese)
            if season:
                text = '全球第' + season[1] + '赛季' + ('月度通行证' if season[2] == '月間パス' else '通行证')
                text += ('解锁' if season[3] == ' アンロック' else '经验') + '_' + season[4]
                if season[5]:
                    text += '_' + ('免费' if season[5] == '無償' else '付费')
                return text
        if key.startswith(('String_STR_DESC_Contents_Ticket_', 'String_STR_ITEM_')):
            return skill_description(japanese)
    if key == 'Message_MSG_GET_VEHICLE_CREATURE_SOUL_POINT_body' and japanese == '魂結晶を{1}個獲得しました。':
        return '获得了{1}个灵魂结晶。'
    if key.startswith(('SkillString_', 'SkillAbnormalString_')) and key.endswith(('_skill_name', '_desc_name')):
        if japanese in SKILL_NAMES:
            return SKILL_NAMES[japanese]
    if key.startswith('AchievementString_'):
        plain = unicodedata.normalize('NFKC', japanese)
        pet = re.fullmatch(r'(野性|自然|変形|知性)ペット(\d+)体レベル(\d+)達成', plain)
        if pet:
            kind = {'野性': '野性', '自然': '自然', '変形': '变形', '知性': '知性'}[pet[1]]
            return '使' + pet[2] + '只' + kind + '宠物达到' + pet[3] + '级'
        score = re.fullmatch(r'覚醒戦最終ポイント([0-9,]+)達成', plain)
        if score:
            return '飞升试炼最终积分达到' + score[1] + '分'
        ranks = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5', '六': '6', '七': '7', '八': '8', '九': '9'}
        kill = re.fullmatch(r'(天族|魔族)?\[([一二三四五六七八九1-9])(等|星)[~〜]([一二三四五六七八九1-9])(?:等兵|星将校)\](\d+)回KILL', plain)
        if kill:
            low, high = ranks.get(kill[2], kill[2]), ranks.get(kill[4], kill[4])
            target = (low + '等兵至' + high + '等兵') if kill[3] == '等' else (low + '星~' + high + '星军官')
            return '击败' + (kill[1] or '') + '[' + target + ']' + kill[5] + '次'
    if key.startswith('SkillString_') and key.endswith('_skill_spec_effect'):
        match = re.fullmatch(r'<(unique|Unique)>([^<>]+)</>', japanese)
        if match:
            parts = match[2].split('|')
            if parts and all(part in SKILL_PROPERTIES for part in parts):
                return '<' + match[1] + '>' + '|'.join(SKILL_PROPERTIES[part] for part in parts) + '</>'
    if key.startswith('SkillString_') and japanese == 'None':
        return '无'
    if key.startswith(('SkillString_', 'SkillAbnormalString_')):
        return skill_description(japanese)
    return None
