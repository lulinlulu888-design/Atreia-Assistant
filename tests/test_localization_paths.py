import tempfile
from pathlib import Path
import unittest
from localization_paths import PAK, DAT, inspect_installation, discover_steam, library_paths, normalize_game_root


class LocalizationPathTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.library = Path(self.directory.name)
        self.game = self.library / "steamapps/common/AION2"
        self.pak = self.game / PAK
        self.pak.parent.mkdir(parents=True)
        self.pak.write_bytes(b"synthetic original PAK")

    def test_detection_does_not_change_files_and_does_not_prove_compatibility(self):
        before = self.pak.read_bytes()
        result, = discover_steam([self.library, self.library])
        self.assertEqual(result.root, self.game)
        self.assertTrue(result.original_pak_present)
        self.assertFalse(result.tool_marker_present)
        self.assertIn("尚未检查", result.status)
        self.assertEqual(self.pak.read_bytes(), before)
        self.assertFalse((self.game / DAT).exists())

    def test_nested_game_selection_and_no_guess_for_unrelated_directory(self):
        self.assertEqual(normalize_game_root(self.pak), self.game)
        with self.assertRaises(ValueError):
            normalize_game_root(Path(self.directory.name) / "unknown")

    def test_marker_and_backup_presence_are_not_declared_valid(self):
        self.pak.write_bytes(b"AION2CN 2.4.0")
        Path(str(self.pak) + ".aion2cn.v2.backup").write_bytes(b"not a verified backup")
        record = inspect_installation(self.game, "steam")
        self.assertTrue(record.tool_marker_present)
        self.assertTrue(record.backup_present)
        self.assertFalse(record.original_pak_present)
        self.assertIn("仍需", record.status)

    def test_library_configuration_adds_other_library_without_scanning_disks(self):
        other = self.library / "other-library"
        other.mkdir()
        value = str(self.library).replace("\\", "\\\\")
        (other / "steamapps").mkdir()
        (other / "steamapps/libraryfolders.vdf").write_text('"path" "' + value + '"', encoding="utf-8")
        record, = discover_steam([other])
        self.assertEqual(record.root, self.game)
        self.assertEqual(library_paths('"path" "D:\\\\SteamLibrary"'), [Path("D:\\SteamLibrary")])

    def test_purple_label_is_explicit_not_guessed_from_path(self):
        record = inspect_installation(self.game, "purple")
        self.assertEqual(record.client, "purple")
        self.assertIn("尚未检查", record.status)
        with self.assertRaises(ValueError):
            inspect_installation(self.game, "automatic-guess")

    def test_oversized_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            library_paths("x" * (2 * 1024 * 1024 + 1))
