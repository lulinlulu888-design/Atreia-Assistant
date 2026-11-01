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

TOKENS = re.compile(r'<[^>]*>|\{[^}]*\}|%\d*\$?[a-zA-Z]|\\[nrt]')
NUMBERS = re.compile(r'(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?:万|萬|千)?%?')
HAN_DIGITS = {'零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


def small_han_number(text):
    if text in HAN_DIGITS:
        return HAN_DIGITS[text]
    if text.count('十') == 1:
        high, low = text.split('十')
        if (not high or high in HAN_DIGITS) and (not low or low in HAN_DIGITS):
            return HAN_DIGITS.get(high, 1) * 10 + HAN_DIGITS.get(low, 0)
    return None


def fingerprint(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def signature(text):
    return Counter(TOKENS.findall(text))


def numbers(text):
    text = unicodedata.normalize('NFKC', TOKENS.sub('', text))
    def ordinal(match):
        value = small_han_number(match.group(1))
        return match.group() if value is None else '第' + str(value)
    # Compare known number spellings without rewriting the translated text.
    text = re.sub(r'第([零〇一二两三四五六七八九十]+)(?=阶段|階段|段階|级|級|层|層|章)', ordinal, text)
    text = re.sub(r'([一二三四五六七八九])(?=星(?:[~～\]将军官]|$)|等兵)', lambda m: str(HAN_DIGITS[m.group()]), text)
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
            elif numbers(translation) != numbers(japanese):
                reason = 'japanese_numeric_values_need_review'
            elif english and translation == english and re.search(r'[A-Za-z]{3}', TOKENS.sub('', english)):
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
