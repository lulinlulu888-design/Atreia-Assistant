from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'localization'))
from entry_transaction import JapaneseEntryTransaction, NAMES


class EntryTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.closed_checks = 0
        def closed():
            self.closed_checks += 1
        self.transaction = JapaneseEntryTransaction(self.root, closed)
        for name in NAMES:
            path = self.transaction.paths[name]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('original ' + name).encode())
        self.before = {name: path.read_bytes() if path.is_file() else None for name, path in self.transaction.paths.items()}
        self.payload = bytes((2, 0, 0, 0)) + bytes(range(100))
        self.english = self.root / 'Aion2/Content/L10N/Text/en-US/L10NString.dat'
        self.english.parent.mkdir(parents=True, exist_ok=True)
        self.english.write_bytes(b'English must remain unchanged')

    def assert_original(self):
        for name, path in self.transaction.paths.items():
            self.assertEqual(path.read_bytes() if path.is_file() else None, self.before[name])
        self.assertEqual(self.english.read_bytes(), b'English must remain unchanged')

    def test_install_reinstall_restore_are_japanese_only(self):
        self.assertEqual(self.transaction.install(self.payload)['status'], 'installed')
        self.assertEqual(self.transaction.paths[NAMES[0]].read_bytes(), b'')
        self.assertTrue(all(not self.transaction.paths[name].exists() for name in NAMES[1:]))
        generation = self.transaction._read_state()['generation']
        self.transaction.install(self.payload + b'next')
        self.assertEqual(self.transaction._read_state()['generation'], generation)
        self.assertEqual(self.transaction.restore()['status'], 'restored')
        self.assert_original()
        self.assertGreaterEqual(self.closed_checks, 6)

    def test_existing_loose_table_is_restored(self):
        self.transaction.dat.parent.mkdir(parents=True)
        self.transaction.dat.write_bytes(b'User existing Japanese table')
        self.before['L10NString.dat'] = self.transaction.dat.read_bytes()
        self.transaction.install(self.payload)
        self.transaction.restore()
        self.assert_original()

    def test_new_backups_have_no_loadable_package_extension(self):
        self.transaction.install(self.payload)
        state = self.transaction._read_state()
        directory = self.transaction.recovery / state['generation']
        for name in NAMES:
            self.assertFalse((directory / name).exists())
            self.assertEqual((directory / (name + '.bak')).read_bytes(), self.before[name])
        self.transaction.restore()
        self.assert_original()

    def old_backup_layout(self):
        self.transaction.install(self.payload)
        state = self.transaction._read_state()
        directory = self.transaction.recovery / state['generation']
        for name in NAMES:
            (directory / (name + '.bak')).rename(directory / name)
        return directory

    def test_old_generation_and_legacy_backups_are_isolated_without_changing_content(self):
        directory = self.old_backup_layout()
        history = self.transaction.recovery / ('f' * 32)
        history.mkdir()
        (history / NAMES[0]).write_bytes(b'old historical package')
        legacy = self.root / 'Aion2_English_Backup_Safe'
        legacy.mkdir()
        english_name = NAMES[0].replace('503000', '502000')
        (legacy / english_name).write_bytes(b'old English backup')
        self.transaction.install(self.payload + b'updated')
        self.assertFalse((history / NAMES[0]).exists())
        self.assertEqual((history / (NAMES[0] + '.bak')).read_bytes(), b'old historical package')
        self.assertEqual((legacy / (english_name + '.bak')).read_bytes(), b'old English backup')
        self.assertTrue(all((directory / (name + '.bak')).exists() for name in NAMES))
        self.transaction.restore()
        self.assert_original()

    def test_backup_conflicts_refuse_install_before_live_writes(self):
        directory = self.old_backup_layout()
        (directory / (NAMES[-1] + '.bak')).write_bytes(b'conflicting backup')
        with self.assertRaises(ValueError):
            self.transaction.install(self.payload + b'updated')
        self.assertEqual(self.transaction.dat.read_bytes(), self.payload)
        self.assertTrue(all((directory / name).exists() for name in NAMES))

    def test_interrupted_extension_migration_keeps_restore_possible(self):
        directory = self.old_backup_layout()
        original_rename = Path.rename
        def interrupt(path, target):
            if path.name == NAMES[1]:
                raise OSError('Interrupted backup rename')
            return original_rename(path, target)
        with patch.object(Path, 'rename', interrupt):
            with self.assertRaises(OSError):
                self.transaction.install(self.payload + b'updated')
        self.assertTrue((directory / (NAMES[0] + '.bak')).exists())
        self.assertTrue((directory / NAMES[1]).exists())
        self.assertEqual(self.transaction.dat.read_bytes(), self.payload)
        self.transaction.restore()
        self.assert_original()

    def test_running_game_refusal_changes_nothing(self):
        def running():
            raise RuntimeError('Game is running')
        transaction = JapaneseEntryTransaction(self.root, running)
        with self.assertRaises(RuntimeError):
            transaction.install(self.payload)
        self.assert_original()
        self.assertFalse(self.transaction.state.exists())

    def test_mid_write_failure_rolls_back(self):
        original = self.transaction._atomic
        failed = False
        def fail_once(path, data):
            nonlocal failed
            if path == self.transaction.paths[NAMES[0]] and not failed:
                failed = True
                raise OSError('Simulated write failure')
            return original(path, data)
        with patch.object(self.transaction, '_atomic', side_effect=fail_once):
            with self.assertRaises(OSError):
                self.transaction.install(self.payload)
        self.assert_original()
        self.assertEqual(self.transaction.inspect()['status'], 'rolled_back')

    def test_game_update_never_restores_stale_originals(self):
        self.transaction.install(self.payload)
        self.transaction.paths[NAMES[0]].write_bytes(b'NEW OFFICIAL PAK')
        with self.assertRaises(ValueError):
            self.transaction.restore()
        with self.assertRaises(ValueError):
            self.transaction.install(self.payload)
        self.assertEqual(self.transaction.paths[NAMES[0]].read_bytes(), b'NEW OFFICIAL PAK')

    def test_corrupt_backup_is_not_used(self):
        self.transaction.install(self.payload)
        state = self.transaction._read_state()
        (self.transaction.recovery / state['generation'] / NAMES[0]).write_bytes(b'CORRUPT')
        with self.assertRaises(ValueError):
            self.transaction.restore()
        self.assertEqual(self.transaction.dat.read_bytes(), self.payload)

    def test_unknown_legacy_empty_package_requires_recovery(self):
        self.transaction.paths[NAMES[0]].write_bytes(b'')
        with self.assertRaises(ValueError):
            self.transaction.install(self.payload)
        self.assertFalse(self.transaction.state.exists())

    def test_interrupted_restore_can_resume_but_unknown_changes_cannot(self):
        self.transaction.install(self.payload)
        state = self.transaction._read_state()
        state['status'] = 'restoring'
        self.transaction._save(state)
        self.transaction.paths[NAMES[1]].write_bytes(self.before[NAMES[1]])
        self.assertEqual(self.transaction.inspect()['status'], 'recovery_required')
        self.transaction.restore()
        self.assert_original()
        self.transaction.install(self.payload)
        state = self.transaction._read_state()
        state['status'] = 'preparing'
        self.transaction._save(state)
        self.transaction.paths[NAMES[1]].write_bytes(b'UNKNOWN NEW SIGNATURE')
        with self.assertRaises(ValueError):
            self.transaction.restore()
        self.assertEqual(self.transaction.paths[NAMES[1]].read_bytes(), b'UNKNOWN NEW SIGNATURE')

    def test_resource_change_during_preparation_is_preserved(self):
        def concurrent_update():
            self.closed_checks += 1
            if self.closed_checks == 2:
                self.transaction.paths[NAMES[0]].write_bytes(b'GAME UPDATED')
        self.transaction.ensure_closed = concurrent_update
        with self.assertRaises(ValueError):
            self.transaction.install(self.payload)
        self.assertEqual(self.transaction.paths[NAMES[0]].read_bytes(), b'GAME UPDATED')
        self.assertFalse(self.transaction.state.exists())


if __name__ == '__main__':
    unittest.main()
