"""Synthetic local bundle smoke test. No driver, network or game operations."""
import struct
from pipeline import BackendBridge, ConnectionRouter
from transport import Packet


def packet(payload, sequence, flags):
    tcp = struct.pack("!HHIIBBHHH", 1234, 7777, sequence, 0, 0x50, flags, 4096, 0, 0) + payload
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 0, 0x4000, 64, 6, 0,
                     b"\x0a\x00\x00\x01", b"\x0a\x00\x00\x02")
    return Packet(1_000_000_000, 101, ip + tcp)


def check_backend(executable):
    payload = bytes.fromhex("0f053878026400d007000032")
    checked = []
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
            checked.append(client)
    return {"synthetic_profiles": checked, "compatibility": "unverified",
            "real_game_tested": False, "packet_capture_started": False}
