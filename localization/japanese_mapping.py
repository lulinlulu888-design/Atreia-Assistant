"""Source-bound Chinese reuse for a Japanese entry; never load upstream DATs.

Inputs are current official tables, our own reviewed English/Chinese snapshot,
and explicit reviews bound to both current source texts. This module only builds
an audit mapping; installation and container serialization are separate steps.
"""
from collections import Counter
import hashlib
import re
import unicodedata
from decimal import Decimal

TOKENS = re.compile(r'''</>|<[A-Za-z_][A-Za-z0-9_.-]*(?:\s+[A-Za-z_]\w*=(?:"[^"]*"|'[^']*'|[^<>\s]+))*\s*/?>|\{[^{}]*\}|%\d*\$?[a-zA-Z]|\\[nrt]''')
NUMBERS = re.compile(r'(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?:万|萬|千)?%?')
HAN_DIGITS = {'零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


def small_han_number(text):
    if text in HAN_DIGITS:
        return HAN_DIGITS[text]
    for unit, multiplier in (('千', 1000), ('百', 100)):
        if text.count(unit) == 1:
            high, low = text.split(unit)
            if high in HAN_DIGITS and HAN_DIGITS[high] > 0:
                tail = small_han_number(low.lstrip('零〇')) if low.lstrip('零〇') else 0
                if tail is not None and tail < multiplier:
                    return HAN_DIGITS[high] * multiplier + tail
    if text.count('十') == 1:
        high, low = text.split('十')
        if (not high or high in HAN_DIGITS) and (not low or low in HAN_DIGITS):
            return HAN_DIGITS.get(high, 1) * 10 + HAN_DIGITS.get(low, 0)
    return None


def fingerprint(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def signature(text):
    return Counter(TOKENS.findall(text))


def numbers(text, written=False):
    text = unicodedata.normalize('NFKC', TOKENS.sub('', text))
    # Unique is an item grade, not the number one. Likewise a Chinese idiom
    # meaning "go further" does not introduce a literal floor count.
    text = text.replace('唯一', '独特').replace('更上一层', '更进一步').replace('更上一層', '更进一步')
    # A band's proper name is not a quest count. Japanese spells the same
    # name without an Arabic digit; stripping only this name retains all
    # actual quantities elsewhere in the sentence.
    text = re.sub(r'(?i)(?<![A-Za-z0-9_])fromis_?9(?![A-Za-z0-9_])', 'fromisnine', text)
    # The named four-element state and a per-second interval have explicit
    # numeric counterparts in Japanese. These are not new gameplay values.
    text = text.replace('四元素', '4元素').replace('每秒', '每1秒').replace('毎秒', '毎1秒').replace('每小时', '每1小时')
    text = text.replace('五星増幅石', '5星増幅石').replace('五星增幅石', '5星增幅石')
    text = text.replace('四大祭壇', '4大祭壇').replace('四大祭坛', '4大祭坛')
    def quantity(match):
        value = small_han_number(match.group())
        return match.group() if value is None else ' ' + str(value) + ' '
    # Written Chinese quantities are equivalent to Arabic digits; prose itself
    # stays unchanged. Requiring an explicit classifier avoids parsing names.
    if written:
        text = re.sub(r'[零〇一二两三四五六七八九十百千]+(?=分钟|分鐘|小时|小時|時間|阶段|階段|等兵|个人|個人|種類|守护者|个|個|种|種|只|名|次|秒|分間|天|日|年|位|级|級|层|層|颗|顆|枚|件|项|項|回|度|瓶|条|條|米|段|つ|人|体|匹|本)', quantity, text)
        text = re.sub(r'(?<![\u3400-\u9fff])([一二三四五六七八九十]+(?:、[一二三四五六七八九十]+)+)(?=[.…。!?]|$)',
                      lambda m: '、'.join(str(small_han_number(v)) for v in m[1].split('、')), text)
    def ordinal(match):
        value = small_han_number(match.group(1))
        return match.group() if value is None else '第' + str(value)
    # Compare known number spellings without rewriting the translated text.
    text = re.sub(r'第([零〇一二两三四五六七八九十]+)(?=阶段|階段|段階|级|級|层|層|章|幕|赛季|賽季|个|個)', ordinal, text)
    text = re.sub(r'([一二三四五六七八九])(?=[~～〜]?[一二三四五六七八九]?(?:等兵|星将校|星军官|星軍官))', lambda m: ' ' + str(HAN_DIGITS[m.group()]) + ' ', text)
    text = re.sub(r'([一二三四五六七八九])(?=星(?:[~～\]将军官]|$)|等(?:兵|[~～\]]))', lambda m: ' ' + str(HAN_DIGITS[m.group()]) + ' ', text)
    if written:
        text = text.replace('百日', '100日').replace('一整年', '1年')
    result = []
    for token in NUMBERS.findall(text):
        percentage = token.endswith('%')
        value = token.rstrip('%')
        multiplier = 10000 if value.endswith(('万', '萬')) else 1000 if value.endswith('千') else 1
        if multiplier != 1:
            value = value[:-1]
        value = Decimal(value.replace(',', '')) * multiplier
        canonical = format(value.normalize(), 'f')
        result.append(canonical + ('%' if percentage else ''))
    return Counter(result)


def numeric_equivalent(first, second):
    # An additional written-number interpretation can prove equivalence, but
    # must not reclassify grade names or literary idioms as new numeric errors.
    if numbers(first) == numbers(second) or numbers(first, written=True) == numbers(second, written=True):
        return True
    # Explicitly spelled concepts can carry the same count without a digit.
    # Keep this as a separate interpretation so an idiom cannot create a new
    # mismatch in prose which was already numerically equivalent.
    def semantic(text):
        text = text.replace('独自', '1人').replace('ソロ', '1人').replace('最初の', '第1个').replace('最初に', '第1次')
        text = text.replace('每件', '每1件').replace('单件', '1件').replace('每个栏位', '每1个栏位')
        text = text.replace('逐一', '1つずつ')
        return text
    return numbers(semantic(first), written=True) == numbers(semantic(second), written=True)


def literal_identifier(key, english, japanese, translation):
    if ''.join(english.split()) != ''.join(japanese.split()) or ''.join(english.split()) != ''.join(translation.split()):
        return False
    if re.fullmatch(r'[IVXLCDM★☆\d\s.+-]+', english):
        return True
    if key.startswith('InputKeyText_') and re.fullmatch(r'[A-Za-z0-9_+ .-]+', english):
        return True
    if re.fullmatch(r'NpcTalk_[A-F0-9]{32}_cv_text', key) and re.fullmatch(r'Default(?:_Zoom_IN[23]?)?(?:_(?:UP|Down))?|(?:Left|Right)_(?:UP|Down|30)', english):
        return True
    if re.fullmatch(r'ServerName_\d+_(?:short_)?desc', key) and re.fullmatch(r'Dev_(?:Reporting_)?(?:Light|Dark|InterServer)|RelQA02_(?:Light|Dark)_[1-3]|Dist2_[1-3]_(?:Light|Dark)|StandAlone_(?:Light|Dark|InterServer)|Review_(?:Siel|Israpel)|RV[LD]', english):
        return True
    if key in {'QuestString_TestQuest_All_District_None_037_step2_obj_2', 'QuestString_TestQuest_All_District_None_037_step2_obj_3'} and english in {'AskNPC', 'KillNPC'}:
        return True
    if key.startswith(('SkillString_', 'SkillAbnormalString_')):
        if re.fullmatch(r'(?:HP|MP|SP|OP|DP)Heal(?:Ratio)?(?:_Item)?|IgnorePenaltyLoss_(?:Item|Exp)_PvE|Extending_Weapon|OnLanding|Abnormal_TRUE|Ground_(?:UnMovable|Movable)|EnvObj_Spawn|SpawnLocation_(?:SpawnDirection|CasterDirection)|Movable_In_Use=(?:TRUE|FALSE)|SoftMove (?:RingArc|Ring|Rectangle)_(?:Push|Pull)', english):
            return True
        if re.fullmatch(r'abnormal effect type = ForceKill(?:ByGetDamage)? (?:skill_damage_type = Magic|skill_attribute_type = Fire|skill_type Active|Abrnoaml Effect Type = Stun|need_condition)', english):
            return True
        if english in {'System', 'SelfDamage', 'EndCastSkillByCasterをDispel'} or re.fullmatch(r'movable_in_use=(?:true|false),overlap=none(?:,(?:charging|casting))?', ''.join(english.split())):
            return True
    if key.startswith('String_STR_N_') and (key.removeprefix('String_').removesuffix('_body') == english or re.fullmatch(r'SEQ(?:2273|2311)', english)):
        return True
    if key in {'String_STR_ITEM_Currency_CASH_body', 'String_STR_ITEM_Currency_DIVINESHARD_body'} and english in {'#Cash', '#DivineShard'}:
        return True
    if key.startswith('String_STR_Test_Object_Terrain_Type_') and english in {'Ground', 'Water', 'Air'}:
        return True
    if key == 'String_UI_HUD_CONTROL_VIRTUALPAD_TAB_body' and english == 'TAB':
        return True
    if key in {'String_UI_SNAPSHOT_OPTIONS_BUTTON_NAMEPLATE_NPC_body', 'String_UI_SNAPSHOT_OPTIONS_BUTTON_SHOW_NPC_body'} and english == 'NPC':
        return True
    if key.startswith('String_STR_Desc_Map_') and key.removeprefix('String_').removesuffix('_body') == english:
        return True
    # An English quotation is deliberately identical in the official locales.
    # Keep it source-bound without storing the quoted text in source control.
    if key == 'NoteData_T_Note_Collect_Verteron_002_text' and fingerprint(english) == '6e7dddc0673556f909825ee4e60a05591fc4086abafdee53352cb5eea0289e94':
        return True
    if key.startswith('String_UI_SETTING_') and (english in {'NVIDIA Reflex', 'TSR', 'TAA', 'FXAA', 'NCAO', 'GTAO', 'MSAA', 'HBAO', 'GFF', 'Auro 3D', 'Resonance'} or re.fullmatch(r'(?:DLSS|FSR)(?: [0-9.]+)?', english)):
        return True
    if re.fullmatch(r'ServerName_\d+_short_desc', key) and english in {'RUT', 'TAS', 'RED', 'HIT', 'GAU', 'LAM', 'TIE', 'HEL'}:
        return True
    return english in {'NVIDIA', 'DLSS', 'AMD FSR', 'Intel XeSS', 'DirectX 12', 'FPS', 'UTC', 'DPS', 'PNG', 'JPG'}


def build(official_english, official_japanese, previous_english, own_chinese, reviews=None):
    """Keep Japanese order and refuse stale, ambiguous, or unsafe translations.

    A returned unresolved list is a publication blocker, not a reason to silently
    keep Japanese. No arbitrary prefix/cap is used to make a partial build pass.
    """
    if previous_english.keys() != own_chinese.keys():
        raise ValueError('Own translation snapshot must match its English source')
    reviews = reviews or {}
    output, unresolved = {}, []
    reused = reviewed = 0
    for key, japanese in official_japanese.items():
        english = official_english.get(key)
        review = reviews.get(key)
        translation = None
        reason = 'missing_or_changed_english_source'
        if review is not None:
            if english is None or review.get('english_sha256') != fingerprint(english) or review.get('japanese_sha256') != fingerprint(japanese):
                raise ValueError('Review source mismatch: ' + key)
            translation = review['translation']
        elif english is not None and previous_english.get(key) == english and key in own_chinese:
            translation = own_chinese[key]
        if translation is not None:
            if signature(translation) != signature(japanese):
                reason = 'japanese_runtime_tokens_or_markup_changed'
            elif not numeric_equivalent(translation, japanese):
                reason = 'japanese_numeric_values_need_review'
            elif re.fullmatch(r'[\s?？]*', TOKENS.sub('', translation)) and not re.fullmatch(r'[\s?？]*', TOKENS.sub('', japanese)):
                reason = 'missing_chinese_translation'
            elif english and translation == english and re.search(r'[A-Za-z]{3}', TOKENS.sub('', english)) and not literal_identifier(key, english, japanese, translation):
                reason = 'untranslated_english_needs_review'
            else:
                output[key] = translation
                if review is None:
                    reused += 1
                else:
                    reviewed += 1
                continue
        unresolved.append({'key': key, 'reason': reason,
                           'english_sha256': fingerprint(english) if english is not None else None,
                           'japanese_sha256': fingerprint(japanese)})
    return output, {'total': len(official_japanese), 'reused': reused,
                    'reviewed': reviewed, 'unresolved': unresolved,
                    'publishable': not unresolved}


def require_complete(official_japanese, mapping, report):
    if not report['publishable'] or report['unresolved']:
        raise ValueError('Unreviewed Japanese-entry text blocks publication')
    if list(mapping) != list(official_japanese):
        raise ValueError('Japanese-entry key order or coverage changed')
