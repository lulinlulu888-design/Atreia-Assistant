"""Propose source-bound repairs from local official TW tables, never third-party DAT.

Only exact matching current English and Japanese runtime signatures/numbers can
yield a candidate. Existing accepted mainland translations are never replaced.
Every decision and its official Chinese source digest is retained for auditing.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
from opencc import OpenCC
from build_official_additions import mainland_terms, load_mainland_terms, transform_prose
from japanese_mapping import build, fingerprint, numbers, signature


def propose(english, japanese, previous, own, tw_english, traditional):
    _, initial = build(english, japanese, previous, own)
    converter = OpenCC('t2s')
    terms = load_mainland_terms(converter)
    reviews, rejected = {}, []
    for item in initial['unresolved']:
        key = item['key']
        reason = None
        if key not in traditional or tw_english.get(key) != english.get(key):
            reason = 'official_english_sources_differ'
        else:
            chinese = transform_prose(traditional[key], converter.convert)
            chinese = mainland_terms(chinese, terms, english[key])
            if signature(chinese) != signature(japanese[key]):
                reason = 'japanese_runtime_signature_differs'
            elif numbers(chinese) != numbers(japanese[key]):
                reason = 'japanese_numbers_differ'
            else:
                reviews[key] = {'english_sha256': fingerprint(english[key]),
                                'japanese_sha256': fingerprint(japanese[key]),
                                'traditional_sha256': fingerprint(traditional[key]),
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
