"""Prepare a bounded game-only capture plan. Never starts capture or consents."""
from dataclasses import dataclass
import ipaddress
from connection_scope import ConnectionScope, validate_scopes


@dataclass(frozen=True)
class AutoCapturePlan:
    pid: int
    device: str
    scopes: tuple
    identity_restricted: bool

    def __post_init__(self):
        if type(self.pid) is not int or self.pid <= 0 or not isinstance(self.device, str) or not self.device:
            raise ValueError("自动采集计划的进程或接口无效")
        object.__setattr__(self, "scopes", validate_scopes(self.scopes))

    def verify(self, report):
        current = {candidate.scope for candidate in report.connections if candidate.pid == self.pid}
        if not all(scope in current for scope in self.scopes):
            raise ValueError("游戏连接已变化，请重新点击开启；没有开始采集")


def prepare_auto_capture(report, devices):
    candidates = report.connections
    if not candidates:
        raise ValueError("尚未发现可用游戏连接，请确认游戏已进入服务器")
    pids = {candidate.pid for candidate in candidates}
    if len(pids) != 1:
        raise ValueError("发现多个游戏进程，需要先确认要统计的游戏窗口")
    unique = {}
    for candidate in candidates:
        if not isinstance(candidate.scope, ConnectionScope):
            raise ValueError("连接信息不完整，请重新检测；不会退回宽泛端口过滤")
        unique.setdefault(frozenset((candidate.scope.local, candidate.scope.remote)), candidate.scope)
    scopes = validate_scopes(tuple(unique.values()))
    loopbacks = [ipaddress.IPv4Address(scope.local_ip).is_loopback and
                 ipaddress.IPv4Address(scope.remote_ip).is_loopback for scope in scopes]
    if any(loopbacks) and not all(loopbacks):
        raise ValueError("游戏连接跨回环与普通网卡，当前不能自动合并，请使用高级设置；未开始采集")
    if all(loopbacks):
        eligible = [name for name, _ in devices if name == r"\Device\NPF_Loopback"]
    else:
        eligible = [name for name, _ in devices if name != r"\Device\NPF_Loopback"]
    if len(eligible) != 1:
        raise ValueError("无法唯一确定采集接口，请检查驱动或在高级设置选择网卡；未开始采集")
    return AutoCapturePlan(next(iter(pids)), eligible[0], scopes,
                           any(candidate.client_hint == "path_restricted" for candidate in candidates))
