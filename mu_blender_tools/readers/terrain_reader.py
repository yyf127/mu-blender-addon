# MU Online Blender Tools - Terrain Reader
#
# Parses MU Online terrain file formats (ATT, MAP, OZB, OBJ).
#
# Reference implementations (TypeScript):
#   src/terrain/formats/ATTReader.ts
#   src/terrain/formats/MAPReader.ts
#   src/terrain/formats/OZBReader.ts
#   src/terrain/formats/OBJReader.ts
#
# Design:
#   - Pure data layer — no bpy imports
#   - Uses BinaryReader from Phase 1
#   - Each format is a standalone function returning a dataclass
#   - Encryption placeholders: actual crypto will be in later phases

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from enum import IntFlag
from typing import Optional

from .binary_reader import BinaryReader, BinaryReaderError

_logger = logging.getLogger("mu_blender_tools")


# ======================================================================
# Constants
# ======================================================================

TERRAIN_SIZE: int = 256
"""MU Online terrain grid: 256×256 tiles."""

TERRAIN_SCALE: float = 100.0
"""World units per tile."""

BUX_MASK: tuple[int, int, int] = (0xFC, 0xCF, 0xAB)
"""Post-decrypt XOR mask used by ATT."""

OBJ_RECORD_SIZES: dict[int, int] = {
    0: 30, 1: 32, 2: 33, 3: 45, 4: 46, 5: 54,
}
"""OBJ record sizes per format version."""


# ======================================================================
# TWFlags — Terrain Wall Attributes (matches TS ATTReader.ts)
# ======================================================================

class TWFlags(IntFlag):
    """Terrain attribute flags — matches C# and TS ``TWFlags`` enum."""
    None_        = 0x0000
    SafeZone     = 0x0001
    Character    = 0x0002
    NoMove       = 0x0004
    NoGround     = 0x0008
    Water        = 0x0010
    Action       = 0x0020
    Height       = 0x0040
    CameraUp     = 0x0080
    NoAttackZone = 0x0100
    Att1         = 0x0200
    Att2         = 0x0400
    Att3         = 0x0800
    Att4         = 0x1000
    Att5         = 0x2000
    Att6         = 0x4000
    Att7         = 0x8000


# ======================================================================
# Data types
# ======================================================================


@dataclass
class TerrainAttributeData:
    """Parsed ATT file data.

    Reference: TS ``TerrainAttributeData`` in ATTReader.ts.
    """
    version: int = 0
    index: int = 0
    width: int = 0
    height: int = 0
    is_extended: bool = False
    terrain_wall: list[int] | None = None
    """Flat array of uint16 TWFlags values, length TERRAIN_SIZE * TERRAIN_SIZE."""


@dataclass
class TerrainMappingData:
    """Parsed MAP file data.

    Reference: TS ``TerrainMappingData`` in MAPReader.ts.
    """
    version: int = 0
    map_number: int = 0
    layer1: list[int] | None = None
    """Base texture indices (TERRAIN_SIZE * TERRAIN_SIZE)."""
    layer2: list[int] | None = None
    """Overlay texture indices (TERRAIN_SIZE * TERRAIN_SIZE)."""
    alpha: list[int] | None = None
    """Blend alpha 0-255 (TERRAIN_SIZE * TERRAIN_SIZE)."""


@dataclass
class OZBData:
    """Parsed OZB file data (heightmap or lightmap).

    Reference: TS ``OZBData`` in OZBReader.ts.
    RGBA flat array where the R channel typically contains the height value.
    """
    width: int = 0
    height: int = 0
    data: bytes | None = None
    """RGBA pixel data (width * height * 4 bytes)."""


@dataclass
class MapObject:
    """A single object placement in an OBJ file.

    Reference: TS ``MapObject`` in OBJReader.ts.
    """
    type: int = 0
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    angle_x: float = 0.0
    angle_y: float = 0.0
    angle_z: float = 0.0
    scale: float = 1.0
    extra: bytes | None = None
    """Version-specific extra bytes."""


@dataclass
class OBJData:
    """Parsed OBJ file data (object placement).

    Reference: TS ``OBJData`` in OBJReader.ts.
    """
    version: int = 0
    map_number: int = 0
    objects: list[MapObject] = None


# ======================================================================
# Decryption helpers (placeholders)
# ======================================================================


def _decrypt_file_cryptor(data: bytes) -> bytes:
    """Decrypt using FileCryptor (placeholder — returns data as-is).

    Reference: TS ``decryptFileCryptor()`` in file-cryptor.ts.
    Will be wired when the crypto module is implemented.
    """
    _logger.debug("FileCryptor decryption not yet implemented — using raw data")
    return data


def _decrypt_modulus_cryptor(data: bytes) -> bytes:
    """Decrypt using ModulusCryptor (placeholder — returns data as-is).

    Reference: TS ``decryptModulusCryptor()`` in modulus-cryptor.ts.
    """
    _logger.debug("ModulusCryptor decryption not yet implemented — using raw data")
    return data


def _xor_bux_mask(data: bytes) -> bytes:
    """Apply post-decrypt BUX XOR mask.

    Reference: TS ``xorBuxMask()`` in file-cryptor.ts.
    """
    out = bytearray(len(data))
    for i, b in enumerate(data):
        out[i] = b ^ BUX_MASK[i % 3]
    return bytes(out)


# ======================================================================
# ATT reader
# ======================================================================


def read_att(data: bytes) -> TerrainAttributeData:
    """Parse an ATT terrain attribute file.

    Reference: TS ``readATT()`` in ATTReader.ts.

    Decryption detection:
      - ``ATT\\x01`` header → ModulusCryptor (skip 4-byte header)
      - Otherwise → FileCryptor
      - Both followed by BUX XOR mask

    Args:
        data: Raw ATT file bytes (with encryption).

    Returns:
        Parsed TerrainAttributeData.

    Raises:
        BinaryReaderError: On invalid format.
    """
    raw: bytes = data

    # Detect encryption
    if len(raw) > 4 and raw[:4] == b"ATT\x01":
        _logger.debug("ATT: detected ModulusCryptor header")
        raw = _decrypt_modulus_cryptor(raw[4:])
    else:
        _logger.debug("ATT: no ModulusCryptor header — using FileCryptor")
        raw = _decrypt_file_cryptor(raw)

    # Post-decrypt BUX mask
    raw = _xor_bux_mask(raw)

    expected_std = TERRAIN_SIZE * TERRAIN_SIZE + 4
    expected_ext = TERRAIN_SIZE * TERRAIN_SIZE * 2 + 4

    if len(raw) not in (expected_std, expected_ext):
        raise BinaryReaderError(
            f"ATT: unexpected size {len(raw)} (expected {expected_std} "
            f"standard or {expected_ext} extended)"
        )

    is_extended = len(raw) == expected_ext
    br = BinaryReader(raw)

    version = br.ReadByte()
    index = br.ReadByte()
    width = br.ReadByte()
    height = br.ReadByte()

    if version != 0:
        raise BinaryReaderError(f"ATT: unsupported version {version}")
    if width != 255 or height != 255:
        raise BinaryReaderError(f"ATT: invalid dimensions {width}x{height}; expected 255x255")

    tile_count = TERRAIN_SIZE * TERRAIN_SIZE
    terrain_wall: list[int] = [0] * tile_count

    if is_extended:
        for i in range(tile_count):
            terrain_wall[i] = br.ReadUInt16()
    else:
        for i in range(tile_count):
            terrain_wall[i] = br.ReadByte()

    return TerrainAttributeData(
        version=version,
        index=index,
        width=width,
        height=height,
        is_extended=is_extended,
        terrain_wall=terrain_wall,
    )


# ======================================================================
# MAP reader
# ======================================================================


def read_map(data: bytes) -> TerrainMappingData:
    """Parse a MAP terrain mapping file.

    Reference: TS ``readMAP()`` in MAPReader.ts.

    Decryption detection:
      - ``MAP\\x01`` header → ModulusCryptor (skip 4 bytes)
      - Otherwise → FileCryptor

    The file contains:
      - version (1 byte)
      - map_number (1 byte)
      - layer1 (256*256 bytes, base texture indices)
      - layer2 (256*256 bytes, overlay texture indices)
      - alpha  (256*256 bytes, 0-255 blend weight)

    Args:
        data: Raw MAP file bytes.

    Returns:
        Parsed TerrainMappingData.

    Raises:
        BinaryReaderError: On invalid format.
    """
    raw: bytes = data

    # Detect encryption
    if len(raw) > 4 and raw[:4] == b"MAP\x01":
        _logger.debug("MAP: detected ModulusCryptor header")
        raw = _decrypt_modulus_cryptor(raw[4:])
    else:
        _logger.debug("MAP: no ModulusCryptor header — using FileCryptor")
        raw = _decrypt_file_cryptor(raw)

    expected_min = 2 + TERRAIN_SIZE * TERRAIN_SIZE * 3  # header + 3 layers
    if len(raw) < expected_min:
        raise BinaryReaderError(
            f"MAP: file too small {len(raw)} (expected at least {expected_min})"
        )

    br = BinaryReader(raw)
    version = br.ReadByte()
    map_number = br.ReadByte()

    tile_count = TERRAIN_SIZE * TERRAIN_SIZE

    layer1 = [br.ReadByte() for _ in range(tile_count)]
    layer2 = [br.ReadByte() for _ in range(tile_count)]
    alpha = [br.ReadByte() for _ in range(tile_count)]

    return TerrainMappingData(
        version=version,
        map_number=map_number,
        layer1=layer1,
        layer2=layer2,
        alpha=alpha,
    )


# ======================================================================
# OZB reader (heightmap / lightmap)
# ======================================================================


def read_ozb(data: bytes) -> OZBData:
    """Parse an OZB file (terrain heightmap or lightmap).

    Reference: TS ``readOZB()`` in OZBReader.ts.

    The format is a BMP-like container with BM6 (24-bit BGR)
    or BM8 (8-bit indexed) pixel data.

    Args:
        data: Raw OZB file bytes.

    Returns:
        Parsed OZBData with RGBA pixel data.

    Raises:
        BinaryReaderError: On invalid format.
    """
    br = BinaryReader(data)

    file_type = br.ReadString(3)
    _ = br.ReadByte()  # version

    # BMP header (14 bytes)
    _ = br.ReadInt16()    # bmp_type
    _ = br.ReadInt32()    # bmp_size
    _ = br.ReadInt16()    # res1
    _ = br.ReadInt16()    # res2
    _ = br.ReadInt32()    # offBits

    # DIB header (40 bytes)
    _ = br.ReadInt32()    # biSize
    width = br.ReadInt32()
    height = br.ReadInt32()
    _ = br.ReadInt16()    # planes
    _ = br.ReadInt16()    # bitCount
    _ = br.ReadInt32()    # compression
    _ = br.ReadInt32()    # sizeImage
    _ = br.ReadInt32()    # xpelsPerMeter
    _ = br.ReadInt32()    # ypelsPerMeter
    _ = br.ReadInt32()    # clrUsed
    _ = br.ReadInt32()    # clrImportant

    pixel_count = width * height
    result_data = bytearray(pixel_count * 4)

    if file_type in ("BM8", "BM\x18"):
        # 8-bit indexed: skip colour table (1024 bytes for 256 colours)
        br.Skip(1024)

        for i in range(pixel_count):
            v = br.ReadByte()
            result_data[i * 4] = v      # R
            result_data[i * 4 + 1] = 0   # G
            result_data[i * 4 + 2] = 0   # B
            result_data[i * 4 + 3] = 255 # A

    elif file_type == "BM6":
        # 24-bit BGR
        for i in range(pixel_count):
            b = br.ReadByte()
            g = br.ReadByte()
            r = br.ReadByte()
            result_data[i * 4] = r
            result_data[i * 4 + 1] = g
            result_data[i * 4 + 2] = b
            result_data[i * 4 + 3] = 255

    else:
        raise BinaryReaderError(f"OZB: unknown file type '{file_type}'")

    return OZBData(
        width=width,
        height=height,
        data=bytes(result_data),
    )


# ======================================================================
# OBJ reader (object placement)
# ======================================================================


def read_obj(data: bytes) -> OBJData:
    """Parse an OBJ terrain object placement file.

    Reference: TS ``readOBJ()`` in OBJReader.ts.

    Always decrypted with FileCryptor first.

    Args:
        data: Raw OBJ file bytes (encrypted with FileCryptor).

    Returns:
        Parsed OBJData with object placement list.

    Raises:
        BinaryReaderError: On invalid format.
    """
    raw = _decrypt_file_cryptor(data)

    br = BinaryReader(raw)

    version = br.ReadByte()
    map_number = br.ReadByte()
    count = br.ReadInt16()

    obj_size = OBJ_RECORD_SIZES.get(version)
    if obj_size is None:
        raise BinaryReaderError(f"OBJ: unsupported version {version}")

    objects: list[MapObject] = []

    for _ in range(count):
        if br.Remaining < obj_size:
            _logger.warning("OBJ: truncated record at %d/%d", len(objects), count)
            break

        type_id = br.ReadInt16()
        px = br.ReadFloat()
        py = br.ReadFloat()
        pz = br.ReadFloat()
        ax = br.ReadFloat()
        ay = br.ReadFloat()
        az = br.ReadFloat()
        scale = br.ReadFloat()

        extra_bytes = obj_size - 30
        extra = br.ReadBytes(extra_bytes) if extra_bytes > 0 else None

        objects.append(MapObject(
            type=type_id,
            position_x=px, position_y=py, position_z=pz,
            angle_x=ax, angle_y=ay, angle_z=az,
            scale=scale,
            extra=extra,
        ))

    return OBJData(
        version=version,
        map_number=map_number,
        objects=objects,
    )
