import unittest
from connection_scope import ConnectionScope
from capture_live import capture_filter


class ScopeTests(unittest.TestCase):
    def test_both_directions_but_not_other_clients_of_shared_proxy(self):
        scope = ConnectionScope("127.0.0.1", 50000, "127.0.0.1", 1111)
        self.assertTrue(scope.matches(scope.local, scope.remote))
        self.assertTrue(scope.matches(scope.remote, scope.local))
        self.assertFalse(scope.matches(("127.0.0.1", 50001), scope.remote))
        self.assertFalse(scope.matches(scope.remote, ("127.0.0.1", 50001)))
        expression = capture_filter("127.0.0.1", 1111, scope)
        self.assertEqual(expression,
            "ip and tcp and ((src host 127.0.0.1 and src port 50000 and dst host 127.0.0.1 and dst port 1111) "
            "or (src host 127.0.0.1 and src port 1111 and dst host 127.0.0.1 and dst port 50000))")

    def test_invalid_scope_cannot_inject_bpf_or_change_requested_endpoint(self):
        for address in ("any", "::1", "127.0.0.1 or tcp", "0.0.0.0", "224.0.0.1"):
            with self.assertRaises(ValueError):
                ConnectionScope(address, 1234, "192.0.2.1", 7777)
        for port in (0, 65536, True, "1234"):
            with self.assertRaises(ValueError):
                ConnectionScope("192.0.2.2", port, "192.0.2.1", 7777)
        scope = ConnectionScope("192.0.2.2", 1234, "192.0.2.1", 7777)
        for ip, port in (("192.0.2.3", 7777), ("192.0.2.1", 8888)):
            with self.assertRaises(ValueError):
                capture_filter(ip, port, scope)
        with self.assertRaises(ValueError):
            ConnectionScope("127.0.0.1", 1111, "127.0.0.1", 1111)
