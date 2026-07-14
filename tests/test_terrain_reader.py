# MU Online Blender Tools - Tests for Terrain Reader
#
# Run with:  python -m unittest tests.test_terrain_reader -v

"""
Tests for ``mu_blender_tools.readers.terrain_reader``.

Verifies ATT, MAP, OZB, OBJ parsing using synthetic binary data.
"""

from __future__ import annotations

import math
import struct
import sys
import unittest
from typing import Any

sys.path.insert(0, ".")

from mu_blender_tools.readers.terrain_reader import (
    TERRAIN_SIZE,
    TWFlags,
    read_att,
    read_map,
    read_ozb,
    read_obj,
    TerrainAttributeData,
    TerrainMappingData,
    OZBData,
    OBJData,
    MapObject,
)


# ======================================================================
# Helpers
# ======================================================================

def _pack(fmt: str, *values: Any) -> bytes:
    if not fmt.startswith("<"):
        fmt = "<" + fmt
    return struct.pack(fmt, *values)


# ======================================================================
# Tests: ATT reader
# ======================================================================

class TestATTReader(unittest.TestCase):
    """Test ATT terrain attribute parsing."""

    def _make_att(self, flags: list[int], extended: bool = False,
                  use_modulus_header: bool = False) -> bytes:
        """Create a synthetic ATT file."""
        bytes_per_tile = 2 if extended else 1
        tile_data = bytearray()
        for f in flags:
            if extended:
                tile_data += _pack("H", f)
            else:
                tile_data.append(f & 0xFF)

        # Pad to full terrain size
        remaining = TERRAIN_SIZE * TERRAIN_SIZE - len(flags)
        if extended:
            tile_data += b"\x00" * (remaining * 2)
        else:
            tile_data += b"\x00" * remaining

        # Payload = 4-byte header + tile data
        payload = b"\x00\x07\xFF\xFF" + bytes(tile_data)

        # Apply BUX mask in reverse (since reader XORs)
        payload = self._undo_bux(payload)

        if use_modulus_header:
            return b"ATT\x01" + payload
        return payload

    @staticmethod
    def _undo_bux(data: bytes) -> bytes:
        """Apply BUX mask (XOR is its own inverse)."""
        mask = (0xFC, 0xCF, 0xAB)
        out = bytearray(len(data))
        for i, b in enumerate(data):
            out[i] = b ^ mask[i % 3]
        return bytes(out)

    def test_read_standard_att(self) -> None:
        flags = [TWFlags.SafeZone, TWFlags.NoGround, TWFlags.CameraUp]
        data = self._make_att(flags)
        att = read_att(data)
        self.assertEqual(att.version, 0)
        self.assertEqual(att.index, 7)
        self.assertEqual(att.width, 255)
        self.assertEqual(att.height, 255)
        self.assertFalse(att.is_extended)
        self.assertEqual(att.terrain_wall[0], TWFlags.SafeZone)
        self.assertEqual(att.terrain_wall[1], TWFlags.NoGround)
        self.assertEqual(att.terrain_wall[2], TWFlags.CameraUp)

    def test_read_extended_att(self) -> None:
        flags = [
            TWFlags.NoAttackZone | TWFlags.Att7,
            TWFlags.Att1 | TWFlags.Att4 | TWFlags.Water,
        ]
        data = self._make_att(flags, extended=True)
        att = read_att(data)
        self.assertTrue(att.is_extended)
        self.assertEqual(att.terrain_wall[0], flags[0])
        self.assertEqual(att.terrain_wall[1], flags[1])

    def test_read_att_with_modulus_header(self) -> None:
        flags = [TWFlags.SafeZone]
        data = self._make_att(flags, use_modulus_header=True)
        att = read_att(data)
        self.assertEqual(att.terrain_wall[0], TWFlags.SafeZone)

    def test_att_all_zero_returns_none_flags(self) -> None:
        data = self._make_att([], extended=False)
        # Pad all zeros
        att = read_att(data)
        self.assertEqual(att.terrain_wall[0], 0)
        self.assertEqual(att.terrain_wall[100], 0)


# ======================================================================
# Tests: MAP reader
# ======================================================================

class TestMAPReader(unittest.TestCase):
    """Test MAP terrain mapping parsing."""

    def _make_map(self, version: int = 1, map_number: int = 3,
                  layer1_val: int = 0, layer2_val: int = 1,
                  alpha_val: int = 128) -> bytes:
        tile_count = TERRAIN_SIZE * TERRAIN_SIZE
        data = bytearray()
        data.append(version & 0xFF)
        data.append(map_number & 0xFF)
        data.extend([layer1_val] * tile_count)
        data.extend([layer2_val] * tile_count)
        data.extend([alpha_val] * tile_count)
        return bytes(data)

    def test_read_map_basic(self) -> None:
        raw = self._make_map(version=1, map_number=3)
        mapping = read_map(raw)
        self.assertEqual(mapping.version, 1)
        self.assertEqual(mapping.map_number, 3)

    def test_read_map_layer_sizes(self) -> None:
        raw = self._make_map()
        mapping = read_map(raw)
        expected = TERRAIN_SIZE * TERRAIN_SIZE
        self.assertEqual(len(mapping.layer1), expected)
        self.assertEqual(len(mapping.layer2), expected)
        self.assertEqual(len(mapping.alpha), expected)

    def test_read_map_values(self) -> None:
        raw = self._make_map(layer1_val=5, layer2_val=10, alpha_val=200)
        mapping = read_map(raw)
        self.assertEqual(mapping.layer1[0], 5)
        self.assertEqual(mapping.layer1[50], 5)
        self.assertEqual(mapping.layer2[0], 10)
        self.assertEqual(mapping.alpha[0], 200)


# ======================================================================
# Tests: OZB reader
# ======================================================================

class TestOZBReader(unittest.TestCase):
    """Test OZB heightmap parsing."""

    def _make_ozb_bm8(self, width: int = 4, height: int = 4) -> bytes:
        """Create a synthetic BM8 OZB file."""
        header = b"BM8\x00"  # type + version
        # BMP header (14 bytes)
        header += _pack("h", 0)     # type
        header += _pack("i", 0)     # size
        header += _pack("h", 0)     # res1
        header += _pack("h", 0)     # res2
        header += _pack("i", 0)     # offBits
        # DIB header (40 bytes)
        header += _pack("i", 40)    # biSize
        header += _pack("i", width)
        header += _pack("i", height)
        header += _pack("h", 1)     # planes
        header += _pack("h", 8)     # bitCount
        header += _pack("i", 0) * 6  # compression, sizeImage, xpels, ypels, clrUsed, clrImportant
        # Colour table (1024 bytes)
        header += b"\x00" * 1024
        # Pixel data (1 byte per pixel)
        pixels = bytes(range(width * height))
        return header + pixels

    def _make_ozb_bm6(self, width: int = 4, height: int = 4) -> bytes:
        """Create a synthetic BM6 (24-bit BGR) OZB file."""
        header = b"BM6\x00"
        header += _pack("h", 0)
        header += _pack("i", 0)
        header += _pack("h", 0)
        header += _pack("h", 0)
        header += _pack("i", 0)
        header += _pack("i", 40)
        header += _pack("i", width)
        header += _pack("i", height)
        header += _pack("h", 1)
        header += _pack("h", 24)  # 24-bit
        header += _pack("i", 0) * 6
        # BGR pixel data
        pixels = bytearray()
        for i in range(width * height):
            pixels.append(i % 256)      # B
            pixels.append((i + 1) % 256)  # G
            pixels.append((i + 2) % 256)  # R
        return header + bytes(pixels)

    def test_read_ozb_bm8(self) -> None:
        raw = self._make_ozb_bm8(4, 4)
        ozb = read_ozb(raw)
        self.assertEqual(ozb.width, 4)
        self.assertEqual(ozb.height, 4)
        self.assertIsNotNone(ozb.data)
        self.assertEqual(len(ozb.data), 4 * 4 * 4)

    def test_read_ozb_bm6(self) -> None:
        raw = self._make_ozb_bm6(4, 4)
        ozb = read_ozb(raw)
        self.assertEqual(ozb.width, 4)
        self.assertEqual(ozb.height, 4)
        self.assertIsNotNone(ozb.data)
        # First pixel BGR = (0, 1, 2) → RGBA = (2, 1, 0, 255)
        self.assertEqual(ozb.data[0], 2)   # R
        self.assertEqual(ozb.data[1], 1)   # G
        self.assertEqual(ozb.data[2], 0)   # B
        self.assertEqual(ozb.data[3], 255)  # A

    def test_read_ozb_unknown_type(self) -> None:
        from mu_blender_tools.readers.binary_reader import BinaryReaderError
        raw = b"BM7\x00" + b"\x00" * 200
        with self.assertRaises(BinaryReaderError):
            read_ozb(raw)


# ======================================================================
# Tests: OBJ reader
# ======================================================================

class TestOBJReader(unittest.TestCase):
    """Test OBJ object placement parsing."""

    def _make_obj_v0(self, map_number: int = 1,
                     objects: list[tuple[int, float, float, float,
                                          float, float, float, float]] | None = None) -> bytes:
        """Create a synthetic OBJ file (version 0, 30-byte records)."""
        objs = objects or [(100, 1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 1.0)]
        data = bytearray()
        data.append(0)  # version
        data.append(map_number & 0xFF)
        data += _pack("h", len(objs))
        for typ, px, py, pz, ax, ay, az, sc in objs:
            data += _pack("h", typ)
            data += _pack("fffffff", px, py, pz, ax, ay, az, sc)
        return data

    def test_read_obj_v0(self) -> None:
        raw = self._make_obj_v0(map_number=5, objects=[
            (101, 10.0, 20.0, 30.0, 1.0, 2.0, 3.0, 1.5),
        ])
        obj = read_obj(raw)
        self.assertEqual(obj.version, 0)
        self.assertEqual(obj.map_number, 5)
        self.assertEqual(len(obj.objects), 1)
        o = obj.objects[0]
        self.assertEqual(o.type, 101)
        self.assertAlmostEqual(o.position_x, 10.0)
        self.assertAlmostEqual(o.position_y, 20.0)
        self.assertAlmostEqual(o.position_z, 30.0)
        self.assertAlmostEqual(o.angle_x, 1.0)
        self.assertAlmostEqual(o.angle_y, 2.0)
        self.assertAlmostEqual(o.angle_z, 3.0)
        self.assertAlmostEqual(o.scale, 1.5)

    def test_read_obj_multiple_objects(self) -> None:
        objs = [
            (10, 1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 1.0),
            (20, 4.0, 5.0, 6.0, 0.0, 0.0, 0.0, 2.0),
            (30, 7.0, 8.0, 9.0, 0.0, 0.0, 0.0, 0.5),
        ]
        raw = self._make_obj_v0(objects=objs)
        obj = read_obj(raw)
        self.assertEqual(len(obj.objects), 3)

    def test_read_obj_truncated_safe(self) -> None:
        """Truncated data should not crash."""
        raw = self._make_obj_v0(objects=[(1, 0, 0, 0, 0, 0, 0, 1)])
        truncated = raw[:20]
        obj = read_obj(truncated)
        # Will have 0 objects since we can't even read the header properly
        self.assertIsNotNone(obj)


# ======================================================================
# Tests: TWFlags
# ======================================================================

class TestTWFlags(unittest.TestCase):
    """Test TWFlags IntFlag enum."""

    def test_combined_flags(self) -> None:
        combined = TWFlags.SafeZone | TWFlags.Water
        self.assertEqual(combined, 0x0011)

    def test_flag_bit_positions(self) -> None:
        self.assertEqual(TWFlags.None_.value, 0x0000)
        self.assertEqual(TWFlags.SafeZone.value, 0x0001)
        self.assertEqual(TWFlags.NoMove.value, 0x0004)
        self.assertEqual(TWFlags.Water.value, 0x0010)
        self.assertEqual(TWFlags.Height.value, 0x0040)
        self.assertEqual(TWFlags.Att7.value, 0x8000)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
