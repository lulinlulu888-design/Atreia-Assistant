import json
import unittest
from unittest.mock import patch
import subprocess
from connections import parse_connections, parse_discovery, find_game_connections, DISCOVERY_SCRIPT


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
        run.return_value = subprocess.CompletedProcess([], 0, b'{"processes":[],"connections":[]}', b"")
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

    def test_restricted_game_with_loopback_is_not_reported_absent(self):
        report = parse_discovery(json.dumps(dict(
            processes=[dict(pid=100, executable=None)],
            connections=[connection(executable=None, server_ip="127.0.0.1", server_port=1111)])))
        self.assertEqual(report.connections, [])
        self.assertEqual((report.process_count, report.restricted_paths, report.loopback_connections), (1, 1, 1))
        self.assertIn("读取受限", report.message())
        self.assertIn("本地回环", report.message())
        self.assertNotIn("未发现", report.message())

    def test_process_without_connections_remains_visible(self):
        report = parse_discovery(json.dumps(dict(processes=[dict(pid=100, executable=None)], connections=[])))
        self.assertEqual(report.process_count, 1)
        self.assertIn("不代表游戏未运行", report.message())
        self.assertIn("未发现", parse_discovery('{"processes":[],"connections":[]}').message())

    def test_proxy_candidates_preserve_each_local_endpoint_and_unverified_identity(self):
        records = [connection(executable=None, server_ip="127.0.0.1", server_port=1111,
                              local_ip="127.0.0.1", local_port=port) for port in (50000, 50001)]
        report = parse_discovery(json.dumps(dict(processes=[dict(pid=100, executable=None)],
                                                 connections=records + records)))
        self.assertEqual(len(report.connections), 2)
        self.assertEqual([c.scope.local_port for c in report.connections], [50000, 50001])
        self.assertTrue(all(c.client_hint == "path_restricted" for c in report.connections))

    def test_verified_direct_candidate_is_upgraded_to_full_scope(self):
        record = connection(local_ip="10.1.2.4", local_port=50000)
        report = parse_discovery(json.dumps(dict(processes=[dict(pid=100, executable=record["executable"])],
                                                 connections=[record])))
        self.assertEqual(len(report.connections), 1)
        self.assertEqual(report.connections[0].scope.local_port, 50000)
        self.assertEqual(report.connections[0].client_hint, "steam")

    def test_inconsistent_process_report_rejected(self):
        for processes in ([], [dict(pid=100, executable=None)], [dict(pid=True)],
                          [dict(pid=100), dict(pid=100)]):
            with self.assertRaises(ValueError):
                parse_discovery(json.dumps(dict(processes=processes, connections=[connection()])))
