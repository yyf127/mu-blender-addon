# MU Online Blender Tools - LEA-256/ECB Cipher
#
# Pure Python implementation of the LEA block cipher (KS X 3246)
# with 256-bit key in ECB mode, matching the C# reference:
#   https://github.com/xulek/muonline/blob/main/Client.Data/LEACrypto.cs
#
# LEA is a 128-bit block cipher.  With a 256-bit key it performs
# 32 rounds.  This implementation is a direct port of the LEA
# algorithm specification.

from __future__ import annotations

import struct
from typing import Optional

# ── LEA constants ─────────────────────────────────────────────────

_BLOCK_SIZE: int = 16  # 128 bits
_ROUNDS: int = 32      # for 256-bit key

# Round constants (delta values)
_DELTA: list[int] = [
    0xc3efe9db, 0x44626b02, 0x79e27c8a, 0x78df30ec,
    0x715ea49e, 0xc785da0a, 0xe04ef22a, 0xe5c40957,
]

# MU Online LEA key (from LEACrypto.cs)
MU_LEA_KEY: bytes = bytes([
    0xcc, 0x50, 0x45, 0x13, 0xc2, 0xa6, 0x57, 0x4e,
    0xd6, 0x9a, 0x45, 0x89, 0xbf, 0x2f, 0xbc, 0xd9,
    0x39, 0xb3, 0xb3, 0xbd, 0x50, 0xbd, 0xcc, 0xb6,
    0x85, 0x46, 0xd1, 0xd6, 0x16, 0x54, 0xe0, 0x87,
])


# ── Helper functions ──────────────────────────────────────────────


def _rotl(x: int, n: int) -> int:
    """Rotate 32-bit integer left by *n* bits (n wraps at 32)."""
    n = n & 31
    if n == 0:
        return x & 0xFFFFFFFF
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF


def _rotr(x: int, n: int) -> int:
    """Rotate 32-bit integer right by *n* bits (n wraps at 32)."""
    n = n & 31
    if n == 0:
        return x & 0xFFFFFFFF
    return ((x >> n) | (x << (32 - n))) & 0xFFFFFFFF


def _bytes_to_u32(data: bytes, offset: int = 0) -> int:
    """Read a little-endian 32-bit unsigned integer."""
    return struct.unpack_from("<I", data, offset)[0]


def _u32_to_bytes(val: int, data: bytearray, offset: int = 0) -> None:
    """Write a little-endian 32-bit unsigned integer."""
    struct.pack_into("<I", data, offset, val & 0xFFFFFFFF)


# ── Key schedule ──────────────────────────────────────────────────


def _key_schedule_256(key: bytes) -> list[list[int]]:
    """Generate 32 round keys for a 256-bit LEA key.

    Each round key is 6 × uint32 (192 bits).

    Returns:
        List of 32 round keys, each a list of 6 uint32 values.
    """
    # Split the 256-bit key into 8 × 32-bit words
    t = [_bytes_to_u32(key, i * 4) for i in range(8)]

    round_keys: list[list[int]] = []
    for i in range(_ROUNDS):
        delta = _DELTA[i % 4]
        t0 = _rotl(t[0] + _rotl(delta, i), 1)
        t1 = _rotl(t[1] + _rotl(delta, i + 1), 3)
        t2 = _rotl(t[2] + _rotl(delta, i + 2), 6)
        t3 = _rotl(t[3] + _rotl(delta, i + 3), 11)
        t4 = _rotl(t[4] + _rotl(delta, i + 4), 13)
        t5 = _rotl(t[5] + _rotl(delta, i + 5), 17)
        t6 = _rotl(t[6] + _rotl(delta, i + 6), 19)
        t7 = _rotl(t[7] + _rotl(delta, i + 7), 23)

        # Update the key state
        t = [t0, t1, t2, t3, t4, t5, t6, t7]

        # Round key: 6 words (t0..t5)
        round_keys.append([t0, t1, t2, t3, t4, t5])

    return round_keys


# ── Block decryption ──────────────────────────────────────────────


def _decrypt_block(block: bytes, rk: list[list[int]]) -> bytes:
    """Decrypt a single 16-byte block with LEA-256.

    Args:
        block: 16 bytes of ciphertext.
        rk: Round keys from ``_key_schedule_256``.

    Returns:
        16 bytes of plaintext.
    """
    # Load block as 4 × uint32 (little-endian)
    x = [_bytes_to_u32(block, i * 4) for i in range(4)]

    # 32 rounds (reverse order for decryption)
    for i in range(_ROUNDS - 1, -1, -1):
        rk_i = rk[i]
        x3 = _rotr((x[3] - rk_i[5]) ^ (x[2] - rk_i[4]), 3)
        x2 = _rotr((x[2] - rk_i[3]) ^ (x[1] - rk_i[2]), 5)
        x1 = _rotr((x[1] - rk_i[1]) ^ x[0], 1)
        x0 = _rotr((x[0] - rk_i[0]) ^ x3, 9)
        x = [x0, x1, x2, x3]

    # Pack back to bytes
    out = bytearray(16)
    for i in range(4):
        _u32_to_bytes(x[i], out, i * 4)
    return bytes(out)


# ── Public API ────────────────────────────────────────────────────


def lea256_decrypt(data: bytes, key: bytes = MU_LEA_KEY) -> bytes:
    """Decrypt bytes using LEA-256 in ECB mode.

    Args:
        data: Ciphertext bytes (must be multiple of 16).
        key: 32-byte LEA key.  Defaults to the MU Online key.

    Returns:
        Decrypted plaintext.

    Raises:
        ValueError: If *data* length is not a multiple of 16.
    """
    if len(data) % _BLOCK_SIZE != 0:
        raise ValueError(
            f"Input length must be a multiple of {_BLOCK_SIZE}, "
            f"got {len(data)}"
        )
    if len(key) != 32:
        raise ValueError(f"Key must be 32 bytes, got {len(key)}")

    rk = _key_schedule_256(key)
    result = bytearray(len(data))

    for offset in range(0, len(data), _BLOCK_SIZE):
        block = data[offset:offset + _BLOCK_SIZE]
        decrypted = _decrypt_block(block, rk)
        result[offset:offset + _BLOCK_SIZE] = decrypted

    return bytes(result)
