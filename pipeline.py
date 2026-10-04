"""Local-only connection between TCP transport and the GPL protocol backend."""
import hashlib
import ipaddress
import json
from pathlib import Path
import queue
import subprocess
import threading
from transport import TcpStream, decode_tcp, read_pcap


class BackendError(RuntimeError):
    pass


class BackendBridge:
    def __init__(self, executable, client):
        if client not in ("steam", "purple"):
            raise ValueError("客户端必须为 steam 或 purple")
        executable = Path(executable).resolve(strict=True)
        self._responses = queue.Queue(maxsize=4)
        self._lock = threading.Lock()
        self._process = subprocess.Popen(
            [str(executable), "--client", client], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while True:
                line = self._process.stdout.readline(1024 * 1024 + 1)
                if not line:
                    raise BackendError("解析后端已退出，请检查数据格式或重新开始统计")
                if len(line) > 1024 * 1024:
                    raise BackendError("统计快照超过大小限制")
                self._responses.put(json.loads(line), timeout=2)
        except Exception as error:
            try:
                self._responses.put(error, timeout=2)
            except queue.Full:
                pass

    def feed(self, flow, timestamp_ms, payload):
        if len(payload) > 65536:
            raise BackendError("载荷超过解析后端限制")
        return self._request({"flow": flow, "timestamp_ms": timestamp_ms,
                              "payload_hex": payload.hex()})

    def close_flow(self, flow, timestamp_ms):
        return self._request({"flow": flow, "timestamp_ms": timestamp_ms,
                              "payload_hex": "", "close": True})

    def reset_encounter(self):
        return self._request({"flow": "session-control", "timestamp_ms": 0,
                              "payload_hex": "", "reset": True})

    def _request(self, fields):
        with self._lock:
            if self._process.poll() is not None:
                raise BackendError("解析后端已停止")
            record = json.dumps(fields).encode("utf-8") + b"\n"
            try:
                self._process.stdin.write(record)
                self._process.stdin.flush()
                response = self._responses.get(timeout=15)
            except (OSError, queue.Empty) as error:
                self.close()
                raise BackendError("解析后端通信失败或超时") from error
            if isinstance(response, Exception):
                self.close()
                raise BackendError(str(response)) from response
            return response

    def close(self):
        process = self._process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        for stream in (process.stdin, process.stdout):
            if stream:
                stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class ConnectionRouter:
    """Reassemble separately per direction; do not merge unrelated TCP flows.

    No automatic connection search: caller supplies the game's port. Captures
    started after SYN are flagged as partial; they cannot prove completeness.
    """
    def __init__(self, backend, server_port, max_flows=32, server_ip=None, scope=None):
        if type(server_port) is not int or not 1 <= server_port <= 65535:
            raise ValueError("需要填写真实游戏连接端口（1—65535）")
        self.backend = backend
        self.server_port = server_port
        self.server_ip = str(ipaddress.IPv4Address(server_ip)) if server_ip is not None else None
        if scope is not None:
            from connection_scope import ConnectionScope
            if not isinstance(scope, ConnectionScope) or scope.remote != (self.server_ip, server_port):
                raise ValueError("连接范围与服务器端点不匹配")
        self.scope = scope
        self.max_flows = max_flows
        self.flows = {}
        self.closed_flows = {}
        self.generation = 0
        self.partial_streams = 0
        self.closed_gaps = 0
        self.segments = 0
        self.payload_bytes = 0

    def retire(self, key, timestamp_ms):
        state = self.flows.pop(key, None)
        if state:
            # Bounded tombstones prevent delayed FIN/data retransmissions from
            # reopening a completed stream. A new SYN re-enables the tuple.
            self.closed_flows[key] = None
            if len(self.closed_flows) > 128:
                self.closed_flows.pop(next(iter(self.closed_flows)))
            if state[0]._pending:
                self.closed_gaps += 1
            return self.backend.close_flow(state[1], timestamp_ms)
        return None

    def feed(self, packet):
        segment = decode_tcp(packet)
        if segment is None or self.server_port not in (segment.source[1], segment.destination[1]):
            return None
        if self.scope is not None and not self.scope.matches(segment.source, segment.destination):
            return None
        if self.server_ip is not None and self.server_ip not in (segment.source[0], segment.destination[0]):
            return None
        key = (segment.source, segment.destination)
        reverse = (segment.destination, segment.source)
        timestamp_ms = segment.timestamp_ns // 1_000_000
        if segment.flags & 2:
            if self.scope is not None and (key in self.closed_flows or reverse in self.closed_flows):
                raise BackendError("所选连接已重新建立，请停止并重新检测以确认进程归属")
            self.closed_flows.pop(key, None)
        elif key in self.closed_flows and not segment.flags & 4:
            return None
        if segment.flags & 4:  # RST: discard both directions, not their gaps.
            response = None
            for flow_key in (key, reverse):
                retired = self.retire(flow_key, timestamp_ms)
                if retired is not None:
                    response = retired
            return response
        state = self.flows.get(key)
        if segment.flags & 2:
            if self.scope is not None and not segment.flags & 0x10 and (
                    (state is not None and state[2] != segment.sequence) or
                    (state is None and reverse in self.flows)):
                raise BackendError("所选连接疑似被重新使用，请停止并重新检测进程归属")
            if not segment.flags & 0x10 and (state is None or state[2] != segment.sequence):
                # A fresh initiating SYN replaces the entire connection,
                # including stale server-to-client parser state.
                self.retire(reverse, timestamp_ms)
            if state is not None and state[2] != segment.sequence:
                self.retire(key, timestamp_ms)
                self.closed_flows.pop(key, None)
                state = None
        if state is None:
            if not segment.payload and not segment.flags & 2:
                return None
            if len(self.flows) >= self.max_flows:
                raise BackendError("连接数超过限制，请选定游戏连接后重新开始")
            self.generation += 1
            token = hashlib.sha256(repr((key, self.generation)).encode()).hexdigest()[:24]
            state = (TcpStream(segment.payload_sequence), token,
                     segment.sequence if segment.flags & 2 else None)
            self.flows[key] = state
            if not segment.flags & 2:
                self.partial_streams += 1
        self.segments += 1
        ordered = state[0].feed(segment.payload_sequence, segment.payload)
        response = None
        if ordered:
            self.payload_bytes += len(ordered)
            response = self.backend.feed(state[1], timestamp_ms, ordered)
        if segment.flags & 1:  # FIN may carry the final payload.
            response = self.retire(key, timestamp_ms)
        return response

    def diagnostics(self):
        return {"segments": self.segments, "payload_bytes": self.payload_bytes,
                "partial_streams": self.partial_streams, "closed_gaps": self.closed_gaps,
                "pending_bytes": sum(len(s[0]._pending) for s in self.flows.values())}


class ScopedConnectionRouter:
    """Game connection group, with independent TCP/protocol state per tuple."""
    def __init__(self, backend, scopes):
        from connection_scope import validate_scopes
        self.routers = {frozenset((s.local, s.remote)): ConnectionRouter(
            backend, s.remote_port, server_ip=s.remote_ip, scope=s) for s in validate_scopes(scopes)}

    def feed(self, packet):
        segment = decode_tcp(packet)
        if segment is None:
            return None
        router = self.routers.get(frozenset((segment.source, segment.destination)))
        return router.feed(packet) if router is not None else None

    def diagnostics(self):
        values = [router.diagnostics() for router in self.routers.values()]
        return {key: sum(value[key] for value in values) for key in
                ("segments", "payload_bytes", "partial_streams", "closed_gaps", "pending_bytes")}


def replay_capture(path, backend, server_port, callback, cancelled=None):
    router = ConnectionRouter(backend, server_port)
    with open(path, "rb") as capture:
        for packet in read_pcap(capture):
            if cancelled is not None and cancelled.is_set():
                break
            snapshot = router.feed(packet)
            if snapshot is not None:
                callback(snapshot, router.diagnostics())
    return router.diagnostics()
