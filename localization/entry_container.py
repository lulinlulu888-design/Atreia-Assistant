"""Write our reviewed mapping in the current official Japanese DAT envelope.

No installation, network access or upstream translation payload is involved.
The official Japanese prefix and exact key order are retained. This is a format
check only; a successful roundtrip does not prove game-client acceptance.
"""
import struct
import lz4.block
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from locale_codec import decrypt, digest

LIMIT = 256 * 1024 * 1024


def configuration(locale):
    if locale != 'ja-JP':
        raise ValueError('This writer only supports the Japanese entry')
    seed = digest(('L10NString_' + locale).encode('ascii'))[:8]
    root = digest(struct.pack('<Q', 0xCD02190910CE83F6))[:8]
    return seed, digest(root + seed + struct.pack('<II', 3, 0))[:16]


def unpack(data, manifest, locale='ja-JP'):
    seed, mask = configuration(locale)
    if len(data) < 68 or len(data) > LIMIT or data[:4] != struct.pack('<i', 2):
        raise ValueError('Unsupported container')
    header = bytes(a ^ b for a, b in zip(data[4:20], mask))
    packed, encryption, aligned, raw_size = struct.unpack('<iiii', header)
    if encryption != 2 or aligned != len(data) - 20 or aligned % 16 or not 0 < packed <= aligned - 32 or not 0 < raw_size <= LIMIT:
        raise ValueError('Invalid container bounds')
    clear = decrypt(data[20:], manifest[seed])
    raw = lz4.block.decompress(clear[32:32 + packed], uncompressed_size=raw_size)
    if len(raw) != raw_size:
        raise ValueError('Invalid expanded size')
    return clear[:32], raw


def fstring(text):
    if '\0' in text:
        raise ValueError('Embedded string terminator')
    if not text:
        return bytes(4)
    if text.isascii():
        encoded = text.encode('ascii') + b'\0'
        return struct.pack('<i', len(encoded)) + encoded
    encoded = text.encode('utf-16-le') + b'\0\0'
    return struct.pack('<i', -(len(encoded) // 2)) + encoded


def encode(mapping, manifest, prefix, locale='ja-JP'):
    seed, mask = configuration(locale)
    if len(prefix) != 32 or not mapping or len(mapping) > 1000000:
        raise ValueError('Invalid prefix or entry count')
    chunks = [struct.pack('<i', 1), fstring('AION2'), struct.pack('<i', len(mapping))]
    for key, value in mapping.items():
        if not key:
            raise ValueError('Empty key')
        chunks.extend((fstring(key), fstring(value)))
    chunks.append(bytes(4))
    raw = b''.join(chunks)
    if len(raw) > LIMIT:
        raise ValueError('Expanded table too large')
    packed = lz4.block.compress(raw, mode='high_compression', compression=12, store_size=False)
    clear = prefix + packed
    clear += bytes((-len(clear)) % 16)
    header = struct.pack('<iiii', len(packed), 2, len(clear), len(raw))
    encrypted_header = bytes(a ^ b for a, b in zip(header, mask))
    encryptor = Cipher(algorithms.AES(manifest[seed]), modes.ECB()).encryptor()
    result = struct.pack('<i', 2) + encrypted_header + encryptor.update(clear) + encryptor.finalize()
    if unpack(result, manifest, locale) != (prefix, raw):
        raise ValueError('Container roundtrip mismatch')
    return result
