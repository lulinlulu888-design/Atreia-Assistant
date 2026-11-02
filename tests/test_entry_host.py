from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'localization'))
from entry_host import execute
from entry_bundle import write_bundle, sha
from entry_container import encode, configuration
from entry_transaction import NAMES
from legacy_english import EN_NAMES
import json


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

    def legacy_english_fixture(self):
        paks = self.game / 'Aion2/Content/Paks/L10N/Text/en-US'
        paks.mkdir(parents=True)
        hashes = {}
        for name in EN_NAMES:
            data = ('official English ' + name).encode()
            (paks / name).write_bytes(data)
            hashes[name] = sha(data)
        backup = paks / (EN_NAMES[0] + '.aion2cn.v2.backup')
        backup.write_bytes((paks / EN_NAMES[0]).read_bytes())
        (paks / EN_NAMES[0]).write_bytes(b'AION2CN 2.4.0 payload=test\r\n')
        dat_dir = self.game / 'Aion2/Content/L10N/Text/en-US'
        dat_dir.mkdir(parents=True)
        (dat_dir / 'L10NString.dat').write_bytes(b'old translation')
        (dat_dir / 'Aion2CNTool.state').write_text('format=2\nstatus=installed\nhad_dat=False\npre_pak_hash=' + hashes[EN_NAMES[0]] + '\npayload_hash=' + sha(b'old translation'), encoding='utf-8')
        path = self.bundle / 'bundle.json'
        metadata = json.loads(path.read_text(encoding='utf-8'))
        metadata['legacy_english_package_sha256'] = hashes
        path.write_text(json.dumps(metadata), encoding='utf-8')
        self.bindings['steam'] = sha(path.read_bytes())
        return paks, dat_dir, backup

    def test_host_recovers_owned_english_entry_before_japanese_install(self):
        paks, dat_dir, backup = self.legacy_english_fixture()
        execute('inspect', self.game, 'steam', self.bundles, self.bindings,
                lambda: self.fail('Inspection must not mutate'))
        self.assertTrue((dat_dir / 'L10NString.dat').exists())
        self.assertFalse((self.game / 'Atreia_English_Entry_Recovery').exists())
        result = execute('install', self.game, 'steam', self.bundles, self.bindings, lambda: None)
        self.assertEqual(result['state'], 'installed')
        self.assertEqual((paks / EN_NAMES[0]).read_bytes(), backup.read_bytes())
        self.assertFalse((dat_dir / 'L10NString.dat').exists())

    def test_bad_english_backup_prevents_any_japanese_mutation(self):
        _, _, backup = self.legacy_english_fixture()
        backup.write_bytes(b'wrong version')
        with self.assertRaises(ValueError):
            execute('install', self.game, 'steam', self.bundles, self.bindings, lambda: None)
        self.assertFalse((self.game / 'Atreia_Japanese_Entry_Backup').exists())
        self.assertTrue(self.originals[NAMES[0]].stat().st_size)

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

    def legacy_layout(self):
        safe = self.game / 'Aion2_Japanese_Backup_Safe'
        safe.mkdir()
        for name, path in self.originals.items():
            (safe / name).write_bytes(path.read_bytes())
            if name == NAMES[0]:
                path.write_bytes(b'')
            else:
                path.unlink()
        dat = self.game / 'Aion2/Content/L10N/Text/ja-JP/L10NString.dat'
        dat.parent.mkdir(parents=True)
        dat.write_bytes(b'previous experimental translation')
        return safe, dat

    def test_verified_legacy_inspection_is_read_only_then_migrates_and_restores(self):
        safe, dat = self.legacy_layout()
        result = execute('inspect', self.game, 'steam', self.bundles, self.bindings,
                         lambda: self.fail('Inspection must be read-only'))
        self.assertEqual(result['state'], 'legacy_ready_to_migrate')
        self.assertFalse((self.game / 'Atreia_Japanese_Entry_Backup').exists())
        self.assertTrue((safe / NAMES[0]).exists())
        result = execute('install', self.game, 'steam', self.bundles, self.bindings, lambda: None)
        self.assertEqual(result['state'], 'installed')
        state_path = self.game / 'Atreia_Japanese_Entry_Backup/state.json'
        import json
        state = json.loads(state_path.read_text(encoding='utf-8'))
        archived = state_path.parent / state['generation'] / 'legacy-L10NString.dat'
        self.assertEqual(archived.read_bytes(), b'previous experimental translation')
        execute('restore', self.game, 'steam', self.bundles, {}, lambda: None)
        self.assertFalse(dat.exists())
        for name, path in self.originals.items():
            self.assertEqual(path.read_bytes(), (safe / (name + '.bak')).read_bytes())

    def test_legacy_migration_rejects_wrong_original_and_running_game(self):
        safe, dat = self.legacy_layout()
        (safe / NAMES[1]).write_bytes(b'wrong version signature')
        with self.assertRaises(ValueError):
            execute('install', self.game, 'steam', self.bundles, self.bindings, lambda: None)
        self.assertEqual(dat.read_bytes(), b'previous experimental translation')
        self.assertFalse((self.game / 'Atreia_Japanese_Entry_Backup').exists())
        (safe / NAMES[1]).write_bytes(('official ' + NAMES[1]).encode())
        def running():
            raise RuntimeError('Game is running')
        with self.assertRaises(RuntimeError):
            execute('install', self.game, 'steam', self.bundles, self.bindings, running)
        self.assertFalse((self.game / 'Atreia_Japanese_Entry_Backup').exists())

    def test_legacy_can_be_restored_without_installing_new_payload(self):
        safe, dat = self.legacy_layout()
        result = execute('restore', self.game, 'steam', self.bundles, self.bindings, lambda: None)
        self.assertEqual(result['state'], 'restored')
        self.assertFalse(dat.exists())
        self.assertEqual(self.originals[NAMES[0]].read_bytes(), (safe / (NAMES[0] + '.bak')).read_bytes())

    def test_reference_tool_bak_layout_is_readable_without_mutating_detection(self):
        safe, dat = self.legacy_layout()
        for name in NAMES:
            (safe / name).rename(safe / (name + '.bak'))
        result = execute('inspect', self.game, 'steam', self.bundles, self.bindings,
                         lambda: self.fail('Inspection must be read-only'))
        self.assertEqual(result['state'], 'legacy_ready_to_migrate')
        execute('install', self.game, 'steam', self.bundles, self.bindings, lambda: None)
        execute('inspect', self.game, 'steam', self.bundles, self.bindings,
                lambda: self.fail('Inspection must be read-only'))
        execute('restore', self.game, 'steam', self.bundles, self.bindings, lambda: None)
        self.assertFalse(dat.exists())


if __name__ == '__main__':
    unittest.main()
