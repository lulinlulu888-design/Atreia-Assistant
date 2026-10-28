"""Pinned Steam 26262663 / PURPLE TW 127 update, retaining reviewed variants."""
import argparse
from collections import defaultdict
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

from build_official_additions import build as official_build, PARAMETERS
from client_20261028_review import replacement

HASHES = {
    'baseline': '88b8049771d99582b7513359057f4975e207d670e79d89e4d56df6dd1df4581a',
    'steam': '37fb7ea8bc04abf35a671101a431a196192706c9aa6f331049f71acf086f73c5',
    'previous_steam': '6cf9e9c06cf7377654fdaf0ca685a55bf1673a81caa294b545d11d9526d677d6',
    'english': '017e180fb47b3d51c3de7510781887fe5205c0f0dbc23c228aaf1ce492455a02',
    'traditional': '0829937316c9636617059c28b73ada2df536fa24a2a7a8f537101b95b3b08ccd',
    'previous_purple': '275173f15d13479dcd4ce156467d2fded8976cd6441bc41e34dfb8149da43f79',
}
PURPLE_REVIEWED = {
    **{'String_UI_ABYSSOUTLAND_PHASE_DESC_01_{:02d}_body'.format(n + 1):
       ('Phase ' + str(n), '第' + str(n) + '阶段') for n in range(1, 7)},
    'String_UI_ABYSS_OUTLAND_RESULT_RANK_TITLE_body': ('Rank', '排名'),
}


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def append_variant(result, key, source, translation):
    variants = result['entries'].setdefault(key, [])
    previous = [v for v in variants if v['source_sha256'] == sha(source)]
    if previous:
        if len({v['translation'] for v in previous}) != 1:
            raise ValueError('Conflicting reviewed variants: ' + key)
        return False
    if sorted(PARAMETERS.findall(source)) != sorted(PARAMETERS.findall(translation)):
        raise ValueError('Runtime parameters changed: ' + key)
    variants.append({'source_sha256': sha(source), 'translation': translation})
    return True


def build(baseline, steam, previous_steam, english, traditional, previous_purple):
    if baseline.get('format') != 3 or english.keys() - traditional.keys():
        raise ValueError('Unsupported baseline or missing official translations')
    result = deepcopy(baseline)
    purple_changes = {k: v for k, v in english.items() if previous_purple.get(k) != v}
    official, rejected = official_build(purple_changes, {k: traditional[k] for k in purple_changes})
    if rejected:
        raise ValueError('Unreviewed official format changes: ' + str(rejected))
    purple_added = 0
    for key, variant in official['entries'].items():
        text = variant['translation']
        if key in PURPLE_REVIEWED:
            source, reviewed = PURPLE_REVIEWED[key]
            if english[key] != source:
                raise ValueError('PURPLE reviewed source changed: ' + key)
            text = reviewed
        purple_added += append_variant(result, key, english[key], text)

    # A matching English sentence is transferable only when current official
    # Chinese translations agree across every occurrence, never merely by key.
    index = defaultdict(set)
    for key, text in english.items():
        index[text].add(traditional[key])
    steam_changes = {k: v for k, v in steam.items() if previous_steam.get(k) != v}
    paired, chinese = {}, {}
    for key, text in steam_changes.items():
        if english.get(key) == text:
            paired[key], chinese[key] = text, traditional[key]
        elif len(index[text]) == 1:
            paired[key], chinese[key] = text, next(iter(index[text]))
    transferred, rejected = official_build(paired, chinese)
    if rejected:
        raise ValueError('Unreviewed Steam format changes: ' + str(rejected))
    added = reviewed = retained = 0
    remaining = []
    for key, text in steam_changes.items():
        existing = [v for v in result['entries'].get(key, []) if v['source_sha256'] == sha(text)]
        if existing:
            if len({v['translation'] for v in existing}) != 1:
                raise ValueError('Conflicting Steam variants: ' + key)
            retained += 1
            continue
        translated = transferred['entries'].get(key, {}).get('translation')
        if translated is None:
            translated = replacement(key, text)
            reviewed += translated is not None
        if translated is None:
            remaining.append(key)
        else:
            added += append_variant(result, key, text, translated)
    report = {'steam_keys': len(steam), 'purple_keys': len(english),
              'steam_changed': len(steam_changes), 'purple_changed': len(purple_changes),
              'purple_added_variants': purple_added, 'steam_added_variants': added,
              'steam_manual_reviewed': reviewed, 'steam_retained_variants': retained,
              'remaining_review_keys': remaining}
    result['origin'] = 'Reviewed Steam 26262663 and PURPLE TW 127 source-bound update, 2026-10-28'
    return result, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (*HASHES, 'destination'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        raise ValueError('Destination must be new')
    tables = {}
    for name, expected in HASHES.items():
        raw = getattr(args, name).read_bytes()
        if name == 'baseline':
            raw = gzip.decompress(raw)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Unreviewed source snapshot: ' + name)
        tables[name] = json.loads(raw.decode('utf-8-sig'))
    result, report = build(**tables)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if report['remaining_review_keys']:
        raise ValueError('Unreviewed Steam text remains; no output written')
    args.destination.mkdir(parents=True)
    encoded = json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    (args.destination / 'additions.json.gz').write_bytes(gzip.compress(encoded, mtime=0))
    report['inputs'] = HASHES
    (args.destination / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
