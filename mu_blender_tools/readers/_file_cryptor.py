# MU Online Blender Tools - FileCryptor
#
# Implements the XOR-based FileCryptor used by BMD version 0x0C.
#
# Reference:
#   https://github.com/xulek/muonline/blob/main/Client.Data/FileCryptor.cs

from __future__ import annotations

# XOR key used by FileCryptor (16 bytes, from C# reference)
_MAP_XOR_KEY: list[int] = [
    0xD1, 0x73, 0x52, 0xF6, 0xD2, 0x9A, 0xCB, 0x27,
    0x3E, 0xAF, 0x59, 0x31, 0x37, 0xB3, 0xE7, 0xA2,
]


def decrypt(data: bytes) -> bytes:
    """Decrypt a buffer using FileCryptor (XOR + cumulative offset).

    The C# algorithm:
        dst[i] = (src[i] ^ MAP_XOR_KEY[i % 16]) - map_key;
        map_key = (src[i] + 0x3D) & 0xFF;

    Args:
        data: Encrypted bytes.

    Returns:
        Decrypted bytes.
    """
    dst = bytearray(len(data))
    map_key: int = 0x5E

    for i, b in enumerate(data):
        decrypted = (b ^ _MAP_XOR_KEY[i % 16]) - map_key
        dst[i] = decrypted & 0xFF
        map_key = (b + 0x3D) & 0xFF

    return bytes(dst)
