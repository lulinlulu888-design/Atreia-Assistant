"""Version-bound local Japanese payload bundles; never download translations.

Only complete reviewed mappings can be packaged. A bundle binds its generated
DAT to the exact four original Japanese package files and source-table hashes.
No game file is written by this module.
"""
import hashlib
import json
import tempfile
from pathlib import Path
from entry_transaction import NAMES
from japanese_mapping import require_complete
from locale_codec import decode
from entry_container import unpack, with_official_references, REFERENCE_PREFIX
from legacy_english import EN_NAMES


def sha(data):
    return hashlib.sha256(data).hexdigest()


def valid_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def write_bundle(destination, client, official_paths, japanese, mapping, report, payload, source_hashes,
                 *, codec_manifest, official_japanese_container, official_english_paths=None):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Bundle destination must be new')
    if client not in ('steam', 'purple'):
        raise ValueError('Unknown client')
    require_complete(japanese, mapping, report)
    if set(official_paths) != set(NAMES):
        raise ValueError('All four official Japanese package files are required')
    if set(source_hashes) != {'official_japanese', 'official_english', 'own_chinese', 'review_manifest'} or not all(valid_hash(value) for value in source_hashes.values()):
        raise ValueError('Missing source provenance')
    if len(payload) < 68 or payload[:4] != bytes((2, 0, 0, 0)):
        raise ValueError('Invalid DAT container')
    official_japanese_container = Path(official_japanese_container)
    official_data = official_japanese_container.read_bytes()
    if sha(official_data) != source_hashes['official_japanese']:
        raise ValueError('Official Japanese container provenance mismatch')
    actual_japanese = decode(official_japanese_container, codec_manifest, 'ja-JP')
    if list(actual_japanese.items()) != list(japanese.items()):
        raise ValueError('Official Japanese source does not match the reviewed table')
    with tempfile.TemporaryDirectory(prefix='atreia-entry-payload-audit-') as temporary:
        path = Path(temporary) / 'generated.dat'
        path.write_bytes(payload)
        actual_mapping = decode(path, codec_manifest, 'ja-JP')
    expected_table = with_official_references(mapping, japanese)
    if list(actual_mapping.items()) != list(expected_table.items()):
        raise ValueError('Generated DAT differs from the reviewed UI or official references')
    if unpack(payload, codec_manifest)[0] != unpack(official_data, codec_manifest)[0]:
        raise ValueError('Official Japanese envelope prefix changed')
    package_hashes = {}
    for name in NAMES:
        data = Path(official_paths[name]).read_bytes()
        if not data:
            raise ValueError('Official source package cannot be empty')
        package_hashes[name] = sha(data)
    metadata = {'format': 2, 'entry': 'ja-JP', 'text_language': '日本語', 'client': client,
                'keys': len(japanese), 'payload_sha256': sha(payload), 'package_sha256': package_hashes,
                'reference_keys': len(japanese), 'table_keys': len(expected_table),
                'reference_prefix': REFERENCE_PREFIX,
                'source_sha256': source_hashes, 'translation_origin': 'atreia_mainland_reviewed'}
    if official_english_paths is not None:
        if set(official_english_paths) != set(EN_NAMES):
            raise ValueError('Complete official English packages required for legacy migration')
        english_hashes = {}
        for name in EN_NAMES:
            data = Path(official_english_paths[name]).read_bytes()
            if not data:
                raise ValueError('Official English source package cannot be empty')
            english_hashes[name] = sha(data)
        metadata['legacy_english_package_sha256'] = english_hashes
    destination.mkdir(parents=True)
    (destination / 'L10NString.dat').write_bytes(payload)
    (destination / 'bundle.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return metadata


def load_bundle(directory, client, expected_metadata_hash):
    directory = Path(directory)
    data = (directory / 'bundle.json').read_bytes()
    if len(data) > 65536 or sha(data) != expected_metadata_hash:
        raise ValueError('Bundled metadata hash mismatch')
    metadata = json.loads(data.decode('utf-8'))
    if metadata.get('format') != 2 or metadata.get('entry') != 'ja-JP' or metadata.get('client') != client:
        raise ValueError('Wrong bundled entry or client')
    keys = metadata.get('keys')
    if (type(keys) is not int or not 0 < keys <= 500000
            or metadata.get('reference_keys') != keys or metadata.get('table_keys') != keys * 2
            or metadata.get('reference_prefix') != REFERENCE_PREFIX):
        raise ValueError('Incomplete official reference metadata')
    if metadata.get('translation_origin') != 'atreia_mainland_reviewed':
        raise ValueError('Unknown translation origin')
    if set(metadata.get('package_sha256', {})) != set(NAMES) or not all(valid_hash(value) for value in metadata['package_sha256'].values()):
        raise ValueError('Invalid original package binding')
    if 'legacy_english_package_sha256' in metadata:
        english_hashes = metadata['legacy_english_package_sha256']
        if set(english_hashes) != set(EN_NAMES) or not all(valid_hash(v) for v in english_hashes.values()):
            raise ValueError('Invalid legacy English package binding')
    payload = (directory / 'L10NString.dat').read_bytes()
    if sha(payload) != metadata.get('payload_sha256'):
        raise ValueError('Bundled payload hash mismatch')
    return metadata, payload


def verify_original_packages(metadata, paths):
    if set(paths) != set(NAMES):
        raise ValueError('Incomplete Japanese language installation')
    for name in NAMES:
        if sha(Path(paths[name]).read_bytes()) != metadata['package_sha256'][name]:
            raise ValueError('Current Japanese language package needs a newly reviewed bundle')
