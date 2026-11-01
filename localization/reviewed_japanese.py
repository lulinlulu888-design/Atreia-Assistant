"""Atreia-authored, narrowly matched Japanese UI/skill reviews.

No upstream translation payload is read. Unknown prose remains unresolved.
The caller binds each result to the complete Japanese and English source hashes.
"""
import re

SKILL_PROPERTIES = {
    'ノンターゲット': '非锁定',
    '移動可能': '可移动施放',
    'チャージ スキル': '蓄力技能',
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
)
HEADINGS = {'<chat_combat>[暴走状態]</>': '<chat_combat>[暴走状态]</>'}
SLOTS = re.compile(r'\{(\d+)\}')
VALUES = re.compile(r'\{[^{}]*\}|[0-9]+(?:[.,][0-9]+)*')


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
