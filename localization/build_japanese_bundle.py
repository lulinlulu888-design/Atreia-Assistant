"""Generate an offline bundle from local official DATs and Atreia reviews.

This maintainer command never reads a third-party translated DAT and never
writes to the game. Official package extraction is a separate read-only step.
"""
import argparse
import json
from pathlib import Path

from entry_bundle import write_bundle, sha
from entry_container import encode, unpack
from entry_transaction import NAMES
from japanese_mapping import build, require_complete
from locale_codec import read_manifest, decode
from legacy_english import EN_NAMES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', required=True, choices=('steam', 'purple'))
    for name in ('official-english', 'official-japanese', 'manifest', 'previous-english',
                 'own-chinese', 'reviews', 'packages', 'english-packages', 'destination'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.destination.exists():
        parser.error('Destination must be new')
    manifest = read_manifest(args.manifest)
    english = decode(args.official_english, manifest, 'en-US')
    japanese = decode(args.official_japanese, manifest, 'ja-JP')
    tables = {name: json.loads(getattr(args, name).read_text(encoding='utf-8-sig'))
              for name in ('previous_english', 'own_chinese', 'reviews')}
    mapping, report = build(english, japanese, tables['previous_english'], tables['own_chinese'], tables['reviews'])
    require_complete(japanese, mapping, report)
    prefix, _ = unpack(args.official_japanese.read_bytes(), manifest)
    payload = encode(mapping, manifest, prefix)
    source_hashes = {name: sha(path.read_bytes()) for name, path in (
        ('official_japanese', args.official_japanese), ('official_english', args.official_english),
        ('own_chinese', args.own_chinese), ('review_manifest', args.reviews))}
    metadata = write_bundle(args.destination, args.client,
                            {name: args.packages / name for name in NAMES}, japanese, mapping,
                            report, payload, source_hashes, codec_manifest=manifest,
                            official_japanese_container=args.official_japanese,
                            official_english_paths={name: args.english_packages / name for name in EN_NAMES})
    report['input_sha256'] = {name: sha(getattr(args, name).read_bytes()) for name in (
        'official_english', 'official_japanese', 'manifest', 'previous_english', 'own_chinese', 'reviews')}
    source = Path(__file__).parent
    report['maintainer_source_sha256'] = {name: sha((source / name).read_bytes()) for name in (
        'build_japanese_bundle.py', 'japanese_mapping.py', 'reviewed_japanese.py',
        'japanese_manual_reviews.json', 'official_japanese_reviews.py',
        'entry_bundle.py', 'entry_container.py', 'locale_codec.py', 'legacy_english.py')}
    (args.destination / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'client': args.client, 'keys': metadata['keys'],
                      'payload_sha256': metadata['payload_sha256'], 'bytes': len(payload)}))


if __name__ == '__main__':
    main()
