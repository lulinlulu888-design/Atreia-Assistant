"""Experimental WinDivert 2.2 reader; opening may load a system driver.

Only call packets_for_scopes after human capture/driver consent. Construction
does not open a handle, install a driver, elevate, or capture traffic.
"""
import ctypes as c
import os
from pathlib import Path
import threading
from connection_scope import validate_scopes
from capture_live import CaptureError
from transport import Packet

SNIFF_RECV_ONLY = 0x0001 | 0x0004


class Address(c.Structure):
    # Official 2.2 WINDIVERT_ADDRESS layout; NETWORK union is opaque here.
    _fields_ = [("timestamp", c.c_int64), ("flags", c.c_uint32),
                ("reserved", c.c_uint32), ("data", c.c_ubyte * 64)]


def exact_filter(scopes):
    expressions = []
    for scope in validate_scopes(scopes):
        forward = (f"ip.SrcAddr == {scope.local_ip} and tcp.SrcPort == {scope.local_port} and "
                   f"ip.DstAddr == {scope.remote_ip} and tcp.DstPort == {scope.remote_port}")
        reverse = (f"ip.SrcAddr == {scope.remote_ip} and tcp.SrcPort == {scope.remote_port} and "
                   f"ip.DstAddr == {scope.local_ip} and tcp.DstPort == {scope.local_port}")
        expressions.append(f"(({forward}) or ({reverse}))")
    return "ip and tcp and (" + " or ".join(expressions) + ")"


class WinDivertReader:
    def __init__(self, directory):
        if os.name != "nt" or c.sizeof(c.c_void_p) != 8:
            raise CaptureError("WinDivert 入口仅支持 64 位 Windows")
        directory = Path(directory).resolve()
        if not all((directory / name).is_file() for name in ("WinDivert.dll", "WinDivert64.sys")):
            raise CaptureError("开发包尚未包含经验证的 WinDivert 组件")
        self.dll = c.WinDLL(str(directory / "WinDivert.dll"), winmode=0x100 | 0x800,
                            use_last_error=True)
        # Deliberately no WinDivertSend binding or blocking/divert flags.
        signatures = {
            "WinDivertOpen": ([c.c_char_p, c.c_int, c.c_int16, c.c_uint64], c.c_void_p),
            "WinDivertRecv": ([c.c_void_p, c.c_void_p, c.c_uint32,
                                c.POINTER(c.c_uint32), c.POINTER(Address)], c.c_int),
            "WinDivertShutdown": ([c.c_void_p, c.c_int], c.c_int),
            "WinDivertClose": ([c.c_void_p], c.c_int),
            "WinDivertHelperCompileFilter": ([c.c_char_p, c.c_int, c.c_void_p, c.c_uint32,
                                               c.POINTER(c.c_char_p), c.POINTER(c.c_uint32)], c.c_int),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.dll, name)
            function.argtypes, function.restype = arguments, result
        self.error = c.get_last_error
        kernel = c.WinDLL("kernel32", use_last_error=True)
        kernel.QueryPerformanceFrequency.argtypes = [c.POINTER(c.c_int64)]
        kernel.QueryPerformanceFrequency.restype = c.c_int
        frequency = c.c_int64()
        if not kernel.QueryPerformanceFrequency(c.byref(frequency)) or frequency.value <= 0:
            raise CaptureError("无法读取 Windows 封包时钟")
        self.frequency = frequency.value

    def validate_filter(self, scopes):
        expression = exact_filter(scopes).encode("ascii")
        error, position = c.c_char_p(), c.c_uint32()
        # User-mode parser only; does not open/install the driver.
        if not self.dll.WinDivertHelperCompileFilter(expression, 0, None, 0,
                                                    c.byref(error), c.byref(position)):
            raise CaptureError(f"WinDivert 精确连接过滤表达式无效（位置 {position.value}）")
        return expression

    def packets_for_scopes(self, scopes, cancelled):
        expression = self.validate_filter(scopes)
        if cancelled.is_set():
            return
        # NETWORK=0, priority=0. SNIFF copies instead of diverting originals;
        # RECV_ONLY disables injection even if another caller tried to send.
        handle = self.dll.WinDivertOpen(expression, 0, 0, SNIFF_RECV_ONLY)
        if handle in (None, 0, c.c_void_p(-1).value):
            code = self.error()
            raise CaptureError(f"WinDivert 无法开启（Windows 错误 {code}）；需要管理员权限，"
                               "也可能受驱动签名或安全软件限制。不会自动提权或关闭安全保护。")
        done = threading.Event()
        def cancel_receive():
            while not done.wait(0.05):
                if cancelled.is_set():
                    # Cancels blocking receive; never stops other applications.
                    self.dll.WinDivertShutdown(handle, 1)
                    return
        watcher = threading.Thread(target=cancel_receive, daemon=True)
        watcher.start()
        try:
            buffer = c.create_string_buffer(65535)
            while not cancelled.is_set():
                length, address = c.c_uint32(), Address()
                if not self.dll.WinDivertRecv(handle, buffer, len(buffer), c.byref(length), c.byref(address)):
                    code = self.error()
                    if cancelled.is_set() and code in (232, 995):
                        return
                    raise CaptureError(f"WinDivert 读取失败（Windows 错误 {code}），统计已停止")
                if not 20 <= length.value <= len(buffer) or address.timestamp < 0:
                    raise CaptureError("WinDivert 返回的封包长度或时钟无效")
                if cancelled.is_set():
                    return
                yield Packet(address.timestamp * 1_000_000_000 // self.frequency,
                             101, bytes(buffer.raw[:length.value]))
        finally:
            done.set()
            watcher.join()
            self.dll.WinDivertClose(handle)
