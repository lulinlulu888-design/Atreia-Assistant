"""Read-only Windows game connection discovery. Never captures packets."""
from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import PureWindowsPath
import subprocess


@dataclass(frozen=True)
class GameConnection:
    pid: int
    server_ip: str
    server_port: int
    client_hint: str


# Fixed script: no user text, process arguments, credentials or packet contents.
DISCOVERY_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$result = @()
foreach ($game in @(Get-CimInstance Win32_Process -Filter "Name='AION2.exe'")) {
    foreach ($connection in @(Get-NetTCPConnection -State Established -OwningProcess $game.ProcessId -ErrorAction SilentlyContinue)) {
        $result += [PSCustomObject]@{pid=[int]$game.ProcessId; executable=$game.ExecutablePath;
            server_ip=$connection.RemoteAddress; server_port=[int]$connection.RemotePort}
    }
}
ConvertTo-Json -InputObject @($result) -Compress
"""


def parse_connections(text):
    records = json.loads(text)
    if not isinstance(records, list) or len(records) > 512:
        raise ValueError("连接检测返回了无效或过多的记录")
    candidates = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("连接检测记录必须为对象")
        pid, port = record.get("pid"), record.get("server_port")
        if type(pid) is not int or pid <= 0 or type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("连接检测返回了无效进程或端口")
        executable = record.get("executable")
        # Access-denied paths must not be silently treated as a verified game.
        if not isinstance(executable, str) or PureWindowsPath(executable).name.lower() != "aion2.exe":
            continue
        try:
            address = ipaddress.ip_address(record.get("server_ip", ""))
        except ValueError:
            continue
        if address.version != 4 or address.is_loopback or address.is_multicast or address.is_unspecified or address.is_link_local:
            continue
        components = [part.lower() for part in PureWindowsPath(executable).parts]
        # Non-Steam locations are NOT automatically assumed to be PURPLE.
        hint = "steam" if "steamapps" in components and "common" in components else "unknown"
        candidates.add(GameConnection(pid, str(address), port, hint))
    return sorted(candidates, key=lambda candidate: (candidate.pid, candidate.server_ip, candidate.server_port))


def find_game_connections():
    if os.name != "nt":
        raise RuntimeError("游戏连接检测目前仅支持 Windows")
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    powershell = str(PureWindowsPath(system_root) / "System32/WindowsPowerShell/v1.0/powershell.exe")
    completed = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-Command",
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new();" + DISCOVERY_SCRIPT],
        capture_output=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if completed.returncode:
        raise RuntimeError("无法读取游戏连接；可以继续手动填写 IP 和端口，不需要自动提权")
    if len(completed.stdout) > 256 * 1024:
        raise RuntimeError("连接检测结果超过大小限制")
    return parse_connections(completed.stdout.decode("utf-8-sig"))
