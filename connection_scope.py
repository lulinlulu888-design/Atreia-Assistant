"""Exact bidirectional TCP scope, independent of proxy/accelerator brands."""
from dataclasses import dataclass
import ipaddress


@dataclass(frozen=True)
class ConnectionScope:
    local_ip: str
    local_port: int
    remote_ip: str
    remote_port: int

    def __post_init__(self):
        for field in ("local_ip", "remote_ip"):
            if not isinstance(getattr(self, field), str):
                raise ValueError("连接地址必须为 IPv4 文本")
            address = ipaddress.IPv4Address(getattr(self, field))
            if address.is_unspecified or address.is_multicast or address.is_link_local:
                raise ValueError("连接端点必须为明确的单播 IPv4 地址")
            object.__setattr__(self, field, str(address))
        for port in (self.local_port, self.remote_port):
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError("连接端口必须为 1—65535")
        if self.local == self.remote:
            raise ValueError("连接两端不能相同")

    @property
    def local(self):
        return self.local_ip, self.local_port

    @property
    def remote(self):
        return self.remote_ip, self.remote_port

    def matches(self, source, destination):
        return ((source == self.local and destination == self.remote) or
                (source == self.remote and destination == self.local))

    def filter_expression(self):
        forward = (f"src host {self.local_ip} and src port {self.local_port} and "
                   f"dst host {self.remote_ip} and dst port {self.remote_port}")
        reverse = (f"src host {self.remote_ip} and src port {self.remote_port} and "
                   f"dst host {self.local_ip} and dst port {self.local_port}")
        return f"ip and tcp and (({forward}) or ({reverse}))"


def validate_scopes(scopes):
    if not isinstance(scopes, (list, tuple)) or not 1 <= len(scopes) <= 16:
        raise ValueError("自动采集需 1—16 条精确游戏连接")
    seen = set()
    for scope in scopes:
        if not isinstance(scope, ConnectionScope):
            raise ValueError("采集范围必须是精确连接")
        key = frozenset((scope.local, scope.remote))
        if key in seen:
            raise ValueError("采集连接重复")
        seen.add(key)
    return tuple(scopes)


def scopes_filter(scopes):
    return " or ".join(f"({scope.filter_expression()})" for scope in validate_scopes(scopes))
