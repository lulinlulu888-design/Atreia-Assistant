import json
import unittest
from unittest.mock import patch
import subprocess
from connections import parse_connections, find_game_connections, DISCOVERY_SCRIPT


def connection(**overrides):
    record = dict(pid=100, server_ip="10.1.2.3", server_port=7777,
                  executable=r"D:\SteamLibrary\steamapps\common\AION2\Aion2\Binaries\Win64\AION2.exe")
    record.update(overrides)
    return record


class ConnectionTests(unittest.TestCase):
    def test_steam_and_non_steam_candidates_without_guessing_purple(self):
        records = [connection(), connection(pid=101, executable=r"D:\PURPLE\AION2\AION2.exe")]
        candidates = parse_connections(json.dumps(records + records))
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].client_hint, "steam")
        self.assertEqual(candidates[1].client_hint, "unknown")

    def test_launchers_missing_paths_and_unsupported_addresses_excluded(self):
        records = [connection(executable=None), connection(executable=r"D:\AION2Launcher.exe")]
        records += [connection(server_ip=ip) for ip in ("::1", "2001:db8::1", "127.0.0.1",
                    "224.0.0.1", "0.0.0.0", "169.254.1.1", "invalid")]
        self.assertEqual(parse_connections(json.dumps(records)), [])

    def test_invalid_shape_and_values_rejected(self):
        for value in ({}, [None], [connection(pid=True)], [connection(server_port=65536)],
                      [connection()] * 513):
            with self.assertRaises(ValueError):
                parse_connections(json.dumps(value))

    @patch("connections.os.name", "nt")
    @patch("connections.subprocess.run")
    def test_query_uses_fixed_read_only_script_and_timeout(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, b"[]", b"")
        self.assertEqual(find_game_connections(), [])
        arguments, options = run.call_args
        self.assertIn("-NonInteractive", arguments[0])
        self.assertTrue(arguments[0][-1].endswith(DISCOVERY_SCRIPT))
        self.assertEqual(options["timeout"], 10)
        self.assertNotIn("shell", options)

    @patch("connections.os.name", "nt")
    @patch("connections.subprocess.run")
    def test_query_failure_is_not_successful_empty_result(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, b"", b"restricted")
        with self.assertRaisesRegex(RuntimeError, "无法读取"):
            find_game_connections()
