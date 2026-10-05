import unittest
from auto_capture import prepare_auto_capture
from connections import DiscoveryReport, GameConnection
from connection_scope import ConnectionScope, scopes_filter


def candidate(port=50000, pid=100, local="127.0.0.1", remote="127.0.0.1"):
    scope = ConnectionScope(local, port, remote, 1111)
    return GameConnection(pid, remote, 1111, "path_restricted", scope)


class AutoCaptureTests(unittest.TestCase):
    devices = [("ordinary", "Network"), (r"\Device\NPF_Loopback", "Loopback")]

    def report(self, candidates):
        return DiscoveryReport(candidates, 1, 1, len(candidates))

    def test_shared_proxy_connections_get_one_precise_plan_without_brand_detection(self):
        report = self.report([candidate(), candidate(50001)])
        plan = prepare_auto_capture(report, self.devices)
        self.assertEqual(plan.device, r"\Device\NPF_Loopback")
        self.assertEqual(len(plan.scopes), 2)
        self.assertTrue(plan.identity_restricted)
        plan.verify(report)
        expression = scopes_filter(plan.scopes)
        self.assertIn("src port 50000", expression)
        self.assertIn("dst port 50001", expression)
        with self.assertRaisesRegex(ValueError, "连接已变化"):
            plan.verify(self.report([candidate()]))

    def test_mirrored_process_internal_connections_are_not_duplicated(self):
        first = candidate()
        reverse = ConnectionScope(*first.scope.remote, *first.scope.local)
        second = GameConnection(100, reverse.remote_ip, reverse.remote_port, "unknown", reverse)
        plan = prepare_auto_capture(self.report([first, second]), self.devices)
        self.assertEqual(len(plan.scopes), 1)

    def test_windivert_plan_needs_no_nic_even_for_mixed_routes(self):
        report = self.report([candidate(), candidate(local="10.0.0.1", remote="10.0.0.2")])
        plan = prepare_auto_capture(report, [], provider="windivert")
        self.assertEqual(plan.device, "windivert")
        self.assertEqual(len(plan.scopes), 2)
        plan.verify(report)

    def test_ambiguous_or_incomplete_environment_does_not_guess_or_broaden(self):
        for records in ([], [candidate(), candidate(pid=101)],
                        [candidate(), candidate(local="10.0.0.1", remote="10.0.0.2")],
                        [GameConnection(100, "127.0.0.1", 1111, "unknown")],
                        [candidate(50000 + i) for i in range(17)]):
            with self.assertRaises(ValueError):
                prepare_auto_capture(self.report(records), self.devices)
        with self.assertRaises(ValueError):
            prepare_auto_capture(self.report([candidate(local="10.0.0.1", remote="10.0.0.2")]),
                [("one", "One"), ("two", "Two")])
