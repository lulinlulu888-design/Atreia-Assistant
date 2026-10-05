"""Maintainer-only decoder for user-owned language files; no game writes.

Format reference: CUE4Parse GameTypes/Aion2 (Apache-2.0).
https://github.com/FabianFG/CUE4Parse/tree/master/CUE4Parse/GameTypes/Aion2
Dependencies: blake3, cryptography, lz4.
"""
import argparse
import json
import struct
from pathlib import Path

import blake3
import lz4.block
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def digest(data):
    return blake3.blake3(data).digest()


def decrypt(data, key):
    cipher = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    return cipher.update(data) + cipher.finalize()


def read_manifest(path):
    encoded = Path(path).read_bytes()
    if len(encoded) < 8 or (len(encoded) - 8) % 48:
        raise ValueError("Invalid key manifest size")
    # Public format derivation constant; not an account credential.
    constant = bytes.fromhex("eb0bc09728475ab5196af8ce785d8a79df18d2148f51cbef8b39e43b2a1d4056")
    clear = decrypt(encoded[8:], digest(constant))
    keys = {}
    for offset in range(0, len(clear), 48):
        seed = clear[offset:offset + 8]
        # The official manifest may repeat seeds; the last record wins,
        # matching the game's manifest reader.
        keys[seed] = clear[offset + 8:offset + 40]
    return keys


def decode(path, manifest, locale):
    data = Path(path).read_bytes()
    if len(data) < 36 or struct.unpack_from("<I", data)[0] != 2:
        raise ValueError("Unsupported localization container")
    seed = digest(("L10NString_" + locale).encode())[:8]
    root = digest(struct.pack("<Q", 0xCD02190910CE83F6))[:8]
    header_key = digest(root + seed + struct.pack("<II", 3, 0))
    header = bytes(a ^ b for a, b in zip(data[4:20], header_key))
    packed, encryption, aligned, raw_size = struct.unpack("<iiii", header)
    if encryption != 2 or aligned != len(data) - 20 or aligned % 16 or packed <= 0 or packed > aligned - 32 or not 0 < raw_size <= 256 * 1024 * 1024:
        raise ValueError("Invalid localization header")
    clear = decrypt(data[20:], manifest[seed])
    raw = lz4.block.decompress(clear[32:32 + packed], uncompressed_size=raw_size)
    if len(raw) != raw_size:
        raise ValueError("Decompressed size mismatch")
    offset = 4
    if struct.unpack_from("<i", raw)[0] != 1:
        raise ValueError("Unsupported table version")

    def string():
        nonlocal offset
        size = struct.unpack_from("<i", raw, offset)[0]
        offset += 4
        if size == 0:
            return ""
        byte_size = size if size > 0 else -size * 2
        terminator = 1 if size > 0 else 2
        if byte_size > 8 * 1024 * 1024 or offset + byte_size > len(raw):
            raise ValueError("Invalid string size")
        value = raw[offset:offset + byte_size]
        offset += byte_size
        if value[-terminator:] != bytes(terminator):
            raise ValueError("Invalid string terminator")
        return value[:-terminator].decode("utf-8" if size > 0 else "utf-16-le")

    if string() != "AION2":
        raise ValueError("Unknown table namespace")
    count = struct.unpack_from("<i", raw, offset)[0]
    offset += 4
    if not 0 < count <= 1000000:
        raise ValueError("Invalid row count")
    rows = {}
    for _ in range(count):
        key, value = string(), string()
        if not key or key in rows:
            raise ValueError("Empty or duplicate localization key")
        rows[key] = value
    if raw[offset:] not in (b"", bytes(4)):
        raise ValueError("Invalid table trailer")
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("table", type=Path)
    parser.add_argument("locale", choices=("en-US", "zh-TW", "ko-KR"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output must be new")
    rows = decode(args.table, read_manifest(args.manifest), args.locale)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(rows, output, ensure_ascii=False)
    print(f"Decoded {len(rows)} {args.locale} rows")
