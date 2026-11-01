from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'localization'))
from entry_host import execute
from entry_bundle import write_bundle, sha
from entry_container import encode, configuration
from entry_transaction import NAMES


class EntryHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'game'
        self.paks = self.game / 'Aion2/Content/Paks/L10N/Text/ja-JP'
        self.paks.mkdir(parents=True)
        self.originals = {}
        for name in NAMES:
            path = self.paks / name
            path.write_bytes(('official ' + name).encode())
            self.originals[name] = path
        manifest = {configuration('ja-JP')[0]: bytes(range(32))}
        japanese, chinese = {'key': 'イズラフェル'}, {'key': '伊斯拉佩尔'}
        official = self.root / 'official.dat'
        official.write_bytes(encode(japanese, manifest, bytes(range(32))))
        payload = encode(chinese, manifest, bytes(range(32)))
        sources = {name: sha(name.encode()) for name in ('official_japanese', 'official_english', 'own_chinese', 'review_manifest')}
        sources['official_japanese'] = sha(official.read_bytes())
        self.bundles = self.root / 'bundles'
        self.bundle = self.bundles / 'steam'
        write_bundle(self.bundle, 'steam', self.originals, japanese, chinese,
                     {'publishable': True, 'unresolved': []}, payload, sources,
                     codec_manifest=manifest, official_japanese_container=official)
        self.bindings = {'steam': sha((self.bundle / 'bundle.json').read_bytes())}

    def test_inspect_install_repeat_restore_through_host(self):
        inspect = execute('inspect', self.game, 'steam', self.bundles, self.bindings,
                          lambda: self.fail('Read-only inspection must not require closing game'))
        self.assertEqual(inspect['entry'], 'ja-JP')
        self.assertIn('日本語', inspect['message'])
        for _ in range(2):
            result = execute('install', self.game, 'steam', self.bundles, self.bindings, lambda: None)
            self.assertEqual(result['state'], 'installed')
        restored = execute('restore', self.game, 'steam', self.bundles, {}, lambda: None)
        self.assertEqual(restored['state'], 'restored')
        self.assertEqual(self.originals[NAMES[0]].read_bytes(), ('official ' + NAMES[0]).encode())
        self.assertFalse((self.game / 'Aion2/Content/L10N/Text/ja-JP/L10NString.dat').exists())
        self.assertFalse((self.game / 'Aion2/Content/L10N/Text/en-US').exists())

    def test_game_update_is_rejected_before_writing(self):
        self.originals[NAMES[0]].write_bytes(b'new update')
        with self.assertRaises(ValueError):
            execute('install', self.game, 'steam', self.bundles, self.bindings, lambda: None)
        self.assertEqual(self.originals[NAMES[0]].read_bytes(), b'new update')
        self.assertFalse((self.game / 'Atreia_Japanese_Entry_Backup').exists())

    def test_missing_client_bundle_is_not_guessed(self):
        with self.assertRaises(ValueError):
            execute('install', self.game, 'purple', self.bundles, self.bindings, lambda: None)
        self.assertTrue(self.originals[NAMES[0]].stat().st_size)


if __name__ == '__main__':
    unittest.main()
