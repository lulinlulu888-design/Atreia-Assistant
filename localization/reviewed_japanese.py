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
    if key.startswith('String_'):
        if japanese in UI_LABELS:
            return UI_LABELS[japanese]
        maximum = re.fullmatch(r'MAX ([0-9]+(?:\.[0-9]+)?%)', japanese)
        if key.startswith('String_UI_NPCSHOP_ITEMLIST_BUTTON_ADDMAX') and maximum:
            return '最大' + maximum[1]
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
