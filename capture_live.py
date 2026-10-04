"""Opt-in Windows Npcap reader. No send/inject APIs and no packet persistence."""
import ctypes as c
import ipaddress
import os
from pathlib import Path
from transport import Packet
from connection_scope import ConnectionScope, scopes_filter, validate_scopes


class CaptureError(RuntimeError):
    pass


def capture_filter(server_ip, port, scope=None):
    address = ipaddress.IPv4Address(server_ip)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("游戏 TCP 端口应为 1—65535")
    if scope is not None:
        if not isinstance(scope, ConnectionScope) or scope.remote != (str(address), port):
            raise ValueError("连接范围与服务器端点不匹配")
        return scope.filter_expression()
    if address.is_loopback:
        raise ValueError("回环采集必须选择包含两端 IP/端口的游戏连接，不能仅按代理端口采集")
    return f"ip and tcp and host {address} and port {port}"


class Device(c.Structure):
    pass


Device._fields_ = [("next", c.POINTER(Device)), ("name", c.c_char_p),
                   ("description", c.c_char_p), ("addresses", c.c_void_p), ("flags", c.c_uint)]


class Header(c.Structure):
    _fields_ = [("seconds", c.c_long), ("microseconds", c.c_long),
                ("captured", c.c_uint), ("original", c.c_uint)]


class BpfProgram(c.Structure):
    _fields_ = [("length", c.c_uint), ("instructions", c.c_void_p)]


class Npcap:
    def __init__(self):
        if os.name != "nt" or c.sizeof(c.c_void_p) != 8:
            raise CaptureError("实时采集目前只支持 64 位 Windows")
        windows_dir = c.create_unicode_buffer(32768)
        if not c.windll.kernel32.GetWindowsDirectoryW(windows_dir, len(windows_dir)):
            raise CaptureError("无法定位 Windows 系统目录")
        dll = Path(windows_dir.value) / "System32/Npcap/wpcap.dll"
        if not dll.is_file():
            raise CaptureError("未找到系统 Npcap。请从 npcap.com 自行安装；本工具不自动安装驱动，不要求启用 WinPcap 兼容模式。")
        try:
            # cdecl API; restrict dependencies to DLL directory and System32.
            self.dll = c.CDLL(str(dll), winmode=0x100 | 0x800)
        except OSError as error:
            raise CaptureError("无法加载系统 Npcap，请检查安装与位数") from error
        signatures = {
            "pcap_init": ([c.c_uint, c.c_char_p], c.c_int),
            "pcap_findalldevs": ([c.POINTER(c.POINTER(Device)), c.c_char_p], c.c_int),
            "pcap_freealldevs": ([c.POINTER(Device)], None),
            "pcap_open_live": ([c.c_char_p, c.c_int, c.c_int, c.c_int, c.c_char_p], c.c_void_p),
            "pcap_close": ([c.c_void_p], None),
            "pcap_datalink": ([c.c_void_p], c.c_int),
            "pcap_compile": ([c.c_void_p, c.POINTER(BpfProgram), c.c_char_p, c.c_int, c.c_uint], c.c_int),
            "pcap_setfilter": ([c.c_void_p, c.POINTER(BpfProgram)], c.c_int),
            "pcap_freecode": ([c.POINTER(BpfProgram)], None),
            "pcap_setnonblock": ([c.c_void_p, c.c_int, c.c_char_p], c.c_int),
            "pcap_next_ex": ([c.c_void_p, c.POINTER(c.POINTER(Header)), c.POINTER(c.POINTER(c.c_ubyte))], c.c_int),
        }
        for name, (arguments, result) in signatures.items():
            try:
                function = getattr(self.dll, name)
            except AttributeError as error:
                raise CaptureError("Npcap API 版本过旧或安装不完整，请从官网更新") from error
            function.argtypes, function.restype = arguments, result
        error = c.create_string_buffer(256)
        if self.dll.pcap_init(1, error) != 0:  # PCAP_CHAR_ENC_UTF_8
            raise CaptureError("Npcap 初始化失败")

    def devices(self):
        head = c.POINTER(Device)()
        error = c.create_string_buffer(256)
        if self.dll.pcap_findalldevs(c.byref(head), error) != 0:
            raise CaptureError("无法枚举网卡，请检查 Npcap 和采集权限")
        result = []
        try:
            current = head
            while current:
                device = current.contents
                if device.name:
                    name = device.name.decode("ascii", errors="strict")
                    description = (device.description or device.name).decode("utf-8", errors="replace")
                    result.append((name, description))
                if len(result) > 512:
                    raise CaptureError("网卡列表异常")
                current = device.next
        finally:
            self.dll.pcap_freealldevs(head)
        return result

    def packets(self, device, server_ip, port, cancelled, scope=None):
        expression = capture_filter(server_ip, port, scope).encode("ascii")
        loopback = ipaddress.IPv4Address(server_ip).is_loopback
        if loopback and (scope is None or not ipaddress.IPv4Address(scope.local_ip).is_loopback
                         or device != r"\Device\NPF_Loopback"):
            raise CaptureError("本地代理连接需精确两端范围和 Npcap 回环接口")
        yield from self._packets(device, expression, cancelled, loopback)

    def packets_for_scopes(self, device, scopes, cancelled):
        scopes = validate_scopes(scopes)
        loopbacks = [ipaddress.IPv4Address(s.local_ip).is_loopback and
                     ipaddress.IPv4Address(s.remote_ip).is_loopback for s in scopes]
        if any(loopbacks) != all(loopbacks) or all(loopbacks) != (device == r"\Device\NPF_Loopback"):
            raise CaptureError("精确连接范围与采集接口不匹配")
        yield from self._packets(device, scopes_filter(scopes).encode("ascii"), cancelled, all(loopbacks))

    def _packets(self, device, expression, cancelled, loopback):
        if device not in {name for name, _ in self.devices()}:
            raise CaptureError("请选择当前网卡列表中的设备")
        error = c.create_string_buffer(256)
        handle = self.dll.pcap_open_live(device.encode("ascii"), 262144, 0, 200, error)
        if not handle:
            raise CaptureError("无法打开网卡，请检查采集权限。工具不会自动提升权限或修改系统设置。")
        try:
            link = self.dll.pcap_datalink(handle)
            if link not in (0, 1, 101) or (link == 0 and not loopback):
                raise CaptureError("当前网卡链路格式或连接范围尚未支持")
            program = BpfProgram()
            if self.dll.pcap_compile(handle, c.byref(program), expression, 1, 0xFFFFFFFF) != 0:
                raise CaptureError("无法编译游戏连接过滤条件")
            try:
                if self.dll.pcap_setfilter(handle, c.byref(program)) != 0:
                    raise CaptureError("无法应用游戏连接过滤条件，已停止采集")
            finally:
                self.dll.pcap_freecode(c.byref(program))
            if self.dll.pcap_setnonblock(handle, 1, error) != 0:
                raise CaptureError("无法设置可停止的非阻塞采集模式")
            while not cancelled.is_set():
                header = c.POINTER(Header)()
                data = c.POINTER(c.c_ubyte)()
                code = self.dll.pcap_next_ex(handle, c.byref(header), c.byref(data))
                if code == 0:
                    cancelled.wait(0.05)
                    continue
                if code != 1 or not header or not data:
                    raise CaptureError("网卡采集已停止或发生错误")
                packet = header.contents
                if packet.captured != packet.original or packet.captured > 262144:
                    raise CaptureError("捕获到截断或异常封包，已停止以避免错误统计")
                timestamp = packet.seconds * 1_000_000_000 + packet.microseconds * 1000
                if timestamp < 0 or not 0 <= packet.microseconds < 1_000_000:
                    raise CaptureError("采集时间戳异常")
                yield Packet(timestamp, link, c.string_at(data, packet.captured))
        finally:
            self.dll.pcap_close(handle)
