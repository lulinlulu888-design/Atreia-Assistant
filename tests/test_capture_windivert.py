import ctypes as c
import threading
import unittest
from unittest.mock import Mock
from capture_windivert import Address, WinDivertReader, exact_filter, SNIFF_RECV_ONLY
from capture_live import CaptureError
from connection_scope import ConnectionScope


class WinDivertTests(unittest.TestCase):
    scopes = (ConnectionScope("127.0.0.1", 50000, "127.0.0.1", 1111),)

    def reader(self):
        reader = WinDivertReader.__new__(WinDivertReader)
        reader.dll = Mock()
        reader.dll.WinDivertOpen.return_value = 7
        reader.dll.WinDivertHelperCompileFilter.return_value = 1
        reader.error = lambda: 5
        reader.frequency = 10_000_000
        return reader

    def test_official_address_layout_and_exact_filter(self):
        self.assertEqual(c.sizeof(Address), 80)
        self.assertEqual(Address.data.offset, 16)
        expression = exact_filter(self.scopes)
        self.assertIn("tcp.SrcPort == 50000", expression)
        self.assertIn("tcp.DstPort == 50000", expression)
        self.assertNotIn("processId", expression)
        with self.assertRaises(ValueError):
            exact_filter(())

    def test_cancellation_before_open_never_loads_driver(self):
        reader, cancelled = self.reader(), threading.Event()
        cancelled.set()
        self.assertEqual(list(reader.packets_for_scopes(self.scopes, cancelled)), [])
        reader.dll.WinDivertOpen.assert_not_called()

    def test_failed_open_never_reads_or_closes_invalid_handle(self):
        reader = self.reader()
        reader.dll.WinDivertOpen.return_value = c.c_void_p(-1).value
        with self.assertRaisesRegex(CaptureError, "管理员"):
            list(reader.packets_for_scopes(self.scopes, threading.Event()))
        reader.dll.WinDivertRecv.assert_not_called()
        reader.dll.WinDivertClose.assert_not_called()

    def test_sniff_only_copy_timestamp_and_generator_cleanup(self):
        reader = self.reader()
        def receive(handle, buffer, capacity, length, address):
            c.memmove(buffer, b"E" + b"\x00" * 19, 20)
            c.cast(length, c.POINTER(c.c_uint32))[0] = 20
            c.cast(address, c.POINTER(Address)).contents.timestamp = 10_000_000
            return 1
        reader.dll.WinDivertRecv.side_effect = receive
        generator = reader.packets_for_scopes(self.scopes, threading.Event())
        packet = next(generator)
        self.assertEqual(packet.timestamp_ns, 1_000_000_000)
        self.assertEqual(packet.link_type, 101)
        self.assertEqual(reader.dll.WinDivertOpen.call_args.args[3], SNIFF_RECV_ONLY)
        generator.close()
        reader.dll.WinDivertClose.assert_called_once_with(7)
        reader.dll.WinDivertSend.assert_not_called()

    def test_truncation_and_receive_errors_close_handle(self):
        reader = self.reader()
        reader.dll.WinDivertRecv.return_value = 0
        with self.assertRaises(CaptureError):
            list(reader.packets_for_scopes(self.scopes, threading.Event()))
        reader.dll.WinDivertClose.assert_called_once_with(7)

    def test_invalid_native_filter_never_opens_driver(self):
        reader = self.reader()
        reader.dll.WinDivertHelperCompileFilter.return_value = 0
        with self.assertRaisesRegex(CaptureError, "过滤表达式"):
            list(reader.packets_for_scopes(self.scopes, threading.Event()))
        reader.dll.WinDivertOpen.assert_not_called()

    def test_cancel_unblocks_receive_without_sending(self):
        reader, cancelled, wake = self.reader(), threading.Event(), threading.Event()
        entered = threading.Event()
        reader.error = lambda: 232
        def receive(*args):
            entered.set()
            if not wake.wait(2):
                raise AssertionError("mock blocking receive was not stopped")
            return 0
        reader.dll.WinDivertRecv.side_effect = receive
        reader.dll.WinDivertShutdown.side_effect = lambda *args: wake.set() or 1
        failures = []
        def run():
            try:
                list(reader.packets_for_scopes(self.scopes, cancelled))
            except Exception as error:
                failures.append(error)
        worker = threading.Thread(target=run)
        worker.start()
        self.assertTrue(entered.wait(1))
        cancelled.set()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertFalse(failures)
        reader.dll.WinDivertShutdown.assert_called_once_with(7, 1)
        reader.dll.WinDivertClose.assert_called_once_with(7)
