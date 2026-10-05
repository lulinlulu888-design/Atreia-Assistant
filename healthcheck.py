"""Synthetic local bundle smoke test. No driver, network or game operations."""
import struct
from pathlib import Path
import tempfile
from pipeline import BackendBridge, ConnectionRouter, ScopedConnectionRouter
from transport import Packet
from connection_scope import ConnectionScope


def check_localization(engine):
    """Call only Inspect on a synthetic temporary installation, never a game."""
    from localization_paths import PAK, inspect_installation
    with tempfile.TemporaryDirectory(prefix="atreia-inspect-") as fixture:
        root = Path(fixture)
        pak = root / PAK
        pak.parent.mkdir(parents=True)
        pak.write_bytes(b"synthetic language package; not a real game")
        def contents():
            return {str(path.relative_to(root)): path.read_bytes()
                    for path in root.rglob("*") if path.is_file()}
        before = contents()
        response = engine.execute("inspect", inspect_installation(root, "steam"))
        if (response.get("ok") is not True or response.get("state") != "not_installed"
                or response.get("engine_version") != "2.4.0" or contents() != before):
            raise RuntimeError("汉化组件只读隔离检查未通过")
    return "passed_read_only_fixture"


def packet(payload, sequence, flags):
    tcp = struct.pack("!HHIIBBHHH", 1234, 7777, sequence, 0, 0x50, flags, 4096, 0, 0) + payload
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 0, 0x4000, 64, 6, 0,
                     b"\x0a\x00\x00\x01", b"\x0a\x00\x00\x02")
    return Packet(1_000_000_000, 101, ip + tcp)


def check_backend(executable):
    payload = bytes.fromhex("0f053878026400d007000032")
    checked = []
    loopback_checked = []
    group_checked = []
    for client in ("steam", "purple"):
        with BackendBridge(executable, client) as backend:
            router = ConnectionRouter(backend, 7777)
            router.feed(packet(b"", 99, 2))
            router.feed(packet(payload[:4], 100, 0x18))
            result = router.feed(packet(payload[4:], 104, 0x18))
            if result["targets"][0]["damage"] != 50 or result["compatibility"] != "unverified":
                raise RuntimeError("合成伤害解析或兼容性标记异常")
            if router.feed(packet(payload, 100, 0x18)) is not None:
                raise RuntimeError("重传去重测试失败")
            reset = backend.reset_encounter()
            if reset["status"] != "no_combat_detected" or reset["previous_encounter"]["targets"][0]["damage"] != 50:
                raise RuntimeError("分场归档测试失败")
            scope = ConnectionScope("127.0.0.1", 50000, "127.0.0.1", 1111)
            loopback = ConnectionRouter(backend, 1111, server_ip="127.0.0.1", scope=scope)
            def loopback_packet(local_port):
                data = bytearray(packet(payload, 100, 0x18).data)
                data[12:20] = b"\x7f\x00\x00\x01" * 2
                data[20:22] = local_port.to_bytes(2, "big")
                data[22:24] = (1111).to_bytes(2, "big")
                return Packet(1_000_000_000, 0, struct.pack("<I", 2) + bytes(data))
            if loopback.feed(loopback_packet(50001)) is not None or loopback.segments:
                raise RuntimeError("回环无关连接过滤失败")
            result = loopback.feed(loopback_packet(50000))
            if result["targets"][0]["damage"] != 50 or result["compatibility"] != "unverified":
                raise RuntimeError("回环精确连接解析失败")
            if loopback.feed(loopback_packet(50000)) is not None or loopback.payload_bytes != len(payload):
                raise RuntimeError("回环重传去重失败")
            loopback_checked.append(client)
            backend.reset_encounter()
            scopes = (scope, ConnectionScope("127.0.0.1", 50001, "127.0.0.1", 1111))
            group = ScopedConnectionRouter(backend, scopes)
            if group.feed(loopback_packet(50002)) is not None:
                raise RuntimeError("自动范围包含了无关连接")
            group.feed(loopback_packet(50000))
            result = group.feed(loopback_packet(50001))
            if result["targets"][0]["damage"] != 100 or group.diagnostics()["payload_bytes"] != 2 * len(payload):
                raise RuntimeError("自动多连接分流失败")
            group_checked.append(client)
            checked.append(client)
    return {"synthetic_profiles": checked, "compatibility": "unverified",
            "synthetic_scoped_loopback_profiles": loopback_checked,
            "synthetic_auto_group_profiles": group_checked,
            "real_game_tested": False, "packet_capture_started": False}
