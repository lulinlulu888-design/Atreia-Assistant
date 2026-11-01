from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'localization'))
from legacy_english import LegacyEnglishRecovery, EN_NAMES
from entry_transaction import digest


class LegacyEnglishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.hashes = {name: digest(('official ' + name).encode()) for name in EN_NAMES}
        self.recovery = LegacyEnglishRecovery(self.root, lambda: None, self.hashes)
        paks = self.recovery.paks
        paks.mkdir(parents=True)
        for name in EN_NAMES:
            (paks / name).write_bytes(('official ' + name).encode())
        self.recovery.paths['legacy_state'].parent.mkdir(parents=True)
        self.payload = b'our old translated English entry'
        self.state = {'format': '2', 'status': 'installed', 'tool_version': '2.4.0', 'had_dat': 'False',
                      'pre_pak_hash': self.hashes[EN_NAMES[0]], 'pre_dat_hash': '', 'payload_hash': digest(self.payload)}
        self.backup = paks / (EN_NAMES[0] + '.aion2cn.v2.backup')
        self.backup.write_bytes(self.recovery.paths['pak'].read_bytes())
        self.recovery.paths['pak'].write_bytes(b'AION2CN 2.4.0 payload=test\r\n')
        self.recovery.paths['dat'].write_bytes(self.payload)
        self.write_state()

    def write_state(self):
        self.recovery.paths['legacy_state'].write_text('\n'.join(k + '=' + v for k, v in self.state.items()), encoding='utf-8')

    def test_inspect_is_read_only_then_restore_and_repeat_preserve_backup(self):
        self.assertEqual(self.recovery.inspect()['status'], 'restore_required')
        self.assertFalse(self.recovery.recovery.exists())
        self.assertEqual(self.recovery.recover()['status'], 'restored')
        self.assertEqual(self.recovery.paths['pak'].read_bytes(), self.backup.read_bytes())
        self.assertFalse(self.recovery.paths['dat'].exists())
        self.assertIn('status=restored', self.recovery.paths['legacy_state'].read_text(encoding='utf-8'))
        self.assertEqual(self.recovery.recover()['status'], 'official_unchanged')
        self.assertTrue(self.backup.exists())

    def test_preexisting_user_dat_is_restored(self):
        data = b'user-owned original loose file'
        self.state.update(had_dat='True', pre_dat_hash=digest(data))
        self.write_state()
        self.recovery.paths['dat'].with_name('L10NString.dat.aion2cn.v2.backup').write_bytes(data)
        self.recovery.recover()
        self.assertEqual(self.recovery.paths['dat'].read_bytes(), data)

    def test_running_game_and_bad_backups_do_not_write(self):
        def running():
            raise RuntimeError('running')
        blocked = LegacyEnglishRecovery(self.root, running, self.hashes)
        with self.assertRaises(RuntimeError):
            blocked.recover()
        self.assertFalse(blocked.recovery.exists())
        self.backup.write_bytes(b'wrong build')
        with self.assertRaises(ValueError):
            self.recovery.recover()
        self.assertEqual(self.recovery.paths['dat'].read_bytes(), self.payload)
        self.assertFalse(self.recovery.recovery.exists())

    def test_user_changed_payload_is_not_deleted(self):
        self.recovery.paths['dat'].write_bytes(b'user edit')
        with self.assertRaises(ValueError):
            self.recovery.recover()
        self.assertEqual(self.recovery.paths['dat'].read_bytes(), b'user edit')

    def test_write_failure_rolls_back_before_retry(self):
        before = {name: path.read_bytes() for name, path in self.recovery.paths.items()}
        atomic = self.recovery.io._atomic
        failed = False
        def fail_state(path, data):
            nonlocal failed
            if path == self.recovery.paths['legacy_state'] and not failed:
                failed = True
                raise OSError('simulated state failure')
            return atomic(path, data)
        with patch.object(self.recovery.io, '_atomic', fail_state):
            with self.assertRaises(OSError):
                self.recovery.recover()
        self.assertEqual({n: p.read_bytes() for n, p in self.recovery.paths.items()}, before)
        self.assertEqual(json.loads(self.recovery.journal.read_text())['status'], 'rolled_back')
        self.assertEqual(self.recovery.recover()['status'], 'restored')

    def interrupted_fixture(self):
        self.recovery.recover()
        plan = json.loads(self.recovery.journal.read_text())
        before = self.recovery._material(plan, 'before')
        for name, data in before.items():
            self.recovery.paths[name].write_bytes(data)
        # Model process/power loss after restoring the package, before DAT and
        # legacy state are updated. All immutable snapshots already exist.
        self.recovery.paths['pak'].write_bytes(self.backup.read_bytes())
        plan['status'] = 'preparing'
        self.recovery.journal.write_text(json.dumps(plan), encoding='utf-8')

    def test_interrupted_partial_restore_resumes_to_official_files(self):
        self.interrupted_fixture()
        self.assertEqual(self.recovery.recover()['status'], 'restored')
        self.assertFalse(self.recovery.paths['dat'].exists())

    def test_interrupted_restore_refuses_unrelated_game_change(self):
        self.interrupted_fixture()
        self.recovery.paths['pak'].write_bytes(b'new game update')
        with self.assertRaises(ValueError):
            self.recovery.recover()
        self.assertEqual(self.recovery.paths['pak'].read_bytes(), b'new game update')
        self.assertEqual(self.recovery.paths['dat'].read_bytes(), self.payload)


if __name__ == '__main__':
    unittest.main()
