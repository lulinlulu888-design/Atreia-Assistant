"""Audit local official sources against our provenance-bound Chinese snapshot."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from japanese_mapping import build, numbers, signature


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('english', 'japanese', 'previous_english', 'own_chinese', 'destination'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--reviews', type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        parser.error('Destination must be new')
    inputs = {name: getattr(args, name) for name in ('english', 'japanese', 'previous_english', 'own_chinese')}
    tables = {name: json.loads(path.read_text(encoding='utf-8-sig')) for name, path in inputs.items()}
    reviews = json.loads(args.reviews.read_text(encoding='utf-8')) if args.reviews else {}
    result, report = build(tables['english'], tables['japanese'], tables['previous_english'], tables['own_chinese'], reviews)
    report['input_sha256'] = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()}
    report['categories'] = dict(Counter(item['reason'] for item in report['unresolved']))
    samples = defaultdict(list)
    tokens = Counter()
    numeric = Counter()
    for item in report['unresolved']:
        key, reason = item['key'], item['reason']
        ja, cn = tables['japanese'][key], tables['own_chinese'].get(key, '')
        if len(samples[reason]) < 30:
            samples[reason].append({**item, 'japanese': ja, 'own_chinese': cn,
                                    'english': tables['english'].get(key)})
        if reason == 'japanese_runtime_tokens_or_markup_changed':
            tokens.update(signature(ja) - signature(cn))
        elif reason == 'japanese_numeric_values_need_review':
            numeric[(str(numbers(ja)), str(numbers(cn)))] += 1
    args.destination.mkdir(parents=True)
    for name, value in [('report', report), ('samples', samples), ('mapping-preview', result),
                        ('token-differences', tokens.most_common()), ('numeric-differences', numeric.most_common())]:
        (args.destination / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('total', 'reused', 'reviewed', 'publishable', 'categories')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
