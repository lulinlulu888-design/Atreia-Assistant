"""Propose source-bound repairs from local official TW tables, never third-party DAT.

Only exact matching current English and Japanese runtime signatures/numbers can
yield a candidate. Existing accepted mainland translations are never replaced.
Every decision and its official Chinese source digest is retained for auditing.
"""
import argparse
from collections import Counter
import json
import re
from pathlib import Path
from opencc import OpenCC
from build_official_additions import mainland_terms, load_mainland_terms, transform_prose
from japanese_mapping import build, fingerprint, numbers, signature, numeric_equivalent
from japanese_mapping import TOKENS, NUMBERS
from reviewed_japanese import reviewed_translation


def english_skeleton(text):
    return re.sub(r'\s+', ' ', NUMBERS.sub(' ', TOKENS.sub(' ', text))).strip().casefold()


def propose(english, japanese, previous, own, tw_english, traditional):
    _, initial = build(english, japanese, previous, own)
    converter = OpenCC('t2s')
    terms = load_mainland_terms(converter)
    reviews, rejected = {}, []
    for item in initial['unresolved']:
        key = item['key']
        reason = None
        authored = reviewed_translation(key, japanese[key])
        if authored is not None and key in english:
            if signature(authored) != signature(japanese[key]) or not numeric_equivalent(authored, japanese[key]):
                raise ValueError('Authored Japanese review changed runtime values: ' + key)
            reviews[key] = {'english_sha256': fingerprint(english[key]),
                            'japanese_sha256': fingerprint(japanese[key]),
                            'translation': authored, 'provenance': 'atreia_authored_japanese_rule'}
            continue
        same_english = key in tw_english and key in english and tw_english[key] == english[key]
        same_prose = key in tw_english and key in english and english_skeleton(tw_english[key]) == english_skeleton(english[key]) and bool(english_skeleton(english[key]))
        unavailable_english = key in english and key in tw_english and bool(re.fullmatch(r'[\s?？]*', english[key]))
        if key not in traditional or not (same_english or same_prose or unavailable_english):
            reason = 'official_english_sources_differ'
        else:
            chinese = transform_prose(traditional[key], converter.convert)
            chinese = mainland_terms(chinese, terms, english[key])
            if re.search(r'\bHidden Cubes?\b', english[key], re.I):
                chinese = chinese.replace('隐藏背包', '隐藏宝箱')
            if unavailable_english and not same_english and not re.search(r'[\u3400-\u9fff]', chinese):
                reason = 'unavailable_english_requires_official_chinese_text'
            elif signature(chinese) != signature(japanese[key]):
                reason = 'japanese_runtime_signature_differs'
            elif not numeric_equivalent(chinese, japanese[key]):
                reason = 'japanese_numbers_differ'
            else:
                reviews[key] = {'english_sha256': fingerprint(english[key]),
                                'japanese_sha256': fingerprint(japanese[key]),
                                'traditional_sha256': fingerprint(traditional[key]),
                                'traditional_english_sha256': fingerprint(tw_english[key]),
                                'source_match': ('exact_english' if same_english else
                                                 'same_english_prose_parameter_or_number_difference' if same_prose else
                                                 'english_unavailable_official_japanese_and_tw_key_runtime_and_values'),
                                'translation': chinese, 'provenance': 'local_official_tw'}
        if reason:
            rejected.append({'key': key, 'reason': reason})
    return reviews, rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    names = ('english', 'japanese', 'previous', 'own', 'tw_english', 'traditional')
    for name in (*names, 'destination'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        parser.error('Destination must be new')
    values = {name: json.loads(getattr(args, name).read_text(encoding='utf-8-sig')) for name in names}
    reviews, rejected = propose(**values)
    args.destination.mkdir(parents=True)
    provenance = {name: fingerprint(getattr(args, name).read_text(encoding='utf-8-sig')) for name in names}
    for name, value in [('reviews', reviews), ('rejected', rejected), ('input-sha256', provenance)]:
        (args.destination / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'candidates': len(reviews), 'rejected': dict(Counter(item['reason'] for item in rejected))}))


if __name__ == '__main__':
    main()
