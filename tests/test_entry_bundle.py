from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'localization'))
from entry_bundle import write_bundle, load_bundle, verify_original_packages, sha
from entry_transaction import NAMES
from entry_container import encode, configuration


class EntryBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = {}
        for name in NAMES:
            path = self.root / name
            path.write_bytes(name.encode())
            self.paths[name] = path
        self.mapping = {'key': '伊斯拉佩尔'}
        self.japanese = {'key': 'イズラフェル'}
        self.report = {'publishable': True, 'unresolved': []}
        self.manifest = {configuration('ja-JP')[0]: bytes(range(32))}
        self.payload = encode(self.mapping, self.manifest, bytes(range(32)))
        self.official = self.root / 'official-japanese.dat'
        self.official.write_bytes(encode(self.japanese, self.manifest, bytes(range(32))))
        self.sources = {name: sha(name.encode()) for name in ('official_japanese', 'official_english', 'own_chinese', 'review_manifest')}
        self.sources['official_japanese'] = sha(self.official.read_bytes())
        self.destination = self.root / 'bundle'

    def create(self):
        return write_bundle(self.destination, 'steam', self.paths, self.japanese, self.mapping,
                            self.report, self.payload, self.sources, codec_manifest=self.manifest,
                            official_japanese_container=self.official)

    def test_bundle_binding_and_wrong_client_refusal(self):
        self.create()
        expected = sha((self.destination / 'bundle.json').read_bytes())
        metadata, payload = load_bundle(self.destination, 'steam', expected)
        self.assertEqual(payload, self.payload)
        verify_original_packages(metadata, self.paths)
        with self.assertRaises(ValueError):
            load_bundle(self.destination, 'purple', expected)
        self.paths[NAMES[1]].write_bytes(b'Updated official signature')
        with self.assertRaises(ValueError):
            verify_original_packages(metadata, self.paths)

    def test_incomplete_mapping_is_not_packaged(self):
        self.report['publishable'] = False
        with self.assertRaises(ValueError):
            self.create()
        self.assertFalse(self.destination.exists())

    def test_modified_payload_is_not_installed(self):
        self.create()
        expected = sha((self.destination / 'bundle.json').read_bytes())
        (self.destination / 'L10NString.dat').write_bytes(b'Unreviewed file')
        with self.assertRaises(ValueError):
            load_bundle(self.destination, 'steam', expected)

    def test_provenance_and_complete_official_files_are_mandatory(self):
        self.sources.pop('own_chinese')
        with self.assertRaises(ValueError):
            self.create()
        self.assertFalse(self.destination.exists())

    def test_valid_but_unreviewed_dat_is_rejected(self):
        self.payload = encode({'key': '别人的译文'}, self.manifest, bytes(range(32)))
        with self.assertRaises(ValueError):
            self.create()
        self.assertFalse(self.destination.exists())


if __name__ == '__main__':
    unittest.main()
