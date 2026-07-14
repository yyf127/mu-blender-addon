# MU Online Blender Tools - Tests for TextureLoader
#
# Run with:  python -m unittest tests.test_texture_loader -v

"""
Tests for ``mu_blender_tools.loaders.texture_loader.TextureLoader``.

Verifies OZJ, OZT, DDS, TGA, JPG decoding using synthetic data.
"""

from __future__ import annotations

import io
import os
import struct
import sys
import unittest
from typing import Any

sys.path.insert(0, ".")

from mu_blender_tools.loaders.texture_loader import (
    TextureLoader,
    TextureData,
    _decode_ozj,
    _decode_ozt,
    _decode_tga,
    _decode_dds,
    _decode_jpg,
    _decode_png,
)


# ======================================================================
# Helpers
# ======================================================================

def _pack(fmt: str, *values: Any) -> bytes:
    if not fmt.startswith("<"):
        fmt = "<" + fmt
    return struct.pack(fmt, *values)


# ======================================================================
# Test: TextureData
# ======================================================================

class TestTextureData(unittest.TestCase):
    """Test TextureData creation."""

    def test_create_rgba(self) -> None:
        td = TextureData(width=4, height=4, channels=4, data=b"\xFF" * 64)
        self.assertEqual(td.width, 4)
        self.assertEqual(td.height, 4)
        self.assertEqual(td.channels, 4)
        self.assertEqual(len(td.data), 64)

    def test_create_rgb(self) -> None:
        td = TextureData(width=2, height=2, channels=3, data=b"\x00" * 12)
        self.assertEqual(len(td.data), 12)


# ======================================================================
# Test: OZJ decoder
# ======================================================================

class TestOZJDecoder(unittest.TestCase):
    """Test OZJ decoding. Requires Pillow."""

    def setUp(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")

    def _make_ozj(self, width: int = 8, height: int = 8, top_down: bool = True) -> bytes:
        """Create a synthetic OZJ file with embedded JPEG."""
        from PIL import Image
        import io as _io

        # Create a small test JPEG
        img = Image.new("RGB", (width, height), color=(128, 64, 32))
        buf = _io.BytesIO()
        img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        # OZJ header + JPEG payload
        ozj = bytearray()
        ozj += _pack("I", 0x4A5A4F5A)      # magic
        ozj += _pack("h", 1)                 # version
        ozj += b"JPEG"                        # format
        ozj += b"\x00" * 7                    # padding to offset 17
        ozj += _pack("?", top_down)           # isTopDownSort at offset 17
        ozj += b"\x00" * 6                    # more padding to offset 24
        ozj += jpeg_bytes                     # JPEG data

        return bytes(ozj)

    def test_decode_ozj_top_down(self) -> None:
        ozj = self._make_ozj(8, 8, top_down=True)
        td = _decode_ozj(ozj)
        self.assertEqual(td.width, 8)
        self.assertEqual(td.height, 8)
        self.assertEqual(td.channels, 4)
        self.assertEqual(len(td.data), 8 * 8 * 4)

    def test_decode_ozj_bottom_up(self) -> None:
        ozj = self._make_ozj(8, 8, top_down=False)
        td = _decode_ozj(ozj)
        self.assertEqual(td.width, 8)
        self.assertEqual(td.height, 8)

    def test_decode_ozj_too_small(self) -> None:
        with self.assertRaises(ValueError):
            _decode_ozj(b"\x00" * 10)


# ======================================================================
# Test: OZT decoder
# ======================================================================

class TestOZTDecoder(unittest.TestCase):
    """Test OZT decoding (raw BGRA, bottom-up, power-of-two)."""

    def _make_ozt(self, nx: int, ny: int, r: int = 255, g: int = 128, b: int = 64, a: int = 255) -> bytes:
        """Create a synthetic OZT file."""
        header = b"\x00" * 16
        header += _pack("h", nx)      # nx
        header += _pack("h", ny)      # ny
        header += _pack("B", 32)      # depth
        header += _pack("B", 0)       # u1

        # BGRA pixel data (bottom-up)
        pixels = bytearray()
        for y in range(ny):
            for x in range(nx):
                pixels.append(b)  # B
                pixels.append(g)  # G
                pixels.append(r)  # R
                pixels.append(a)  # A

        return bytes(header + bytes(pixels))

    def test_decode_ozt_small(self) -> None:
        ozt = self._make_ozt(4, 4)
        td = _decode_ozt(ozt)
        # Power-of-two: 4x4 stays 4x4
        self.assertEqual(td.width, 4)
        self.assertEqual(td.height, 4)
        self.assertEqual(td.channels, 4)
        # First pixel should be RGBA(255, 128, 64, 255)
        self.assertEqual(td.data[0], 255)  # R
        self.assertEqual(td.data[1], 128)  # G
        self.assertEqual(td.data[2], 64)   # B
        self.assertEqual(td.data[3], 255)  # A

    def test_decode_ozt_power_of_two(self) -> None:
        """Non-power-of-two input should be padded."""
        ozt = self._make_ozt(6, 5)
        td = _decode_ozt(ozt)
        self.assertEqual(td.width, 8)    # next power of 2
        self.assertEqual(td.height, 8)   # next power of 2

    def test_decode_ozt_bad_depth(self) -> None:
        ozt = self._make_ozt(4, 4)
        # Corrupt depth
        ozt_list = bytearray(ozt)
        ozt_list[20] = 24  # depth = 24 instead of 32
        with self.assertRaises(ValueError):
            _decode_ozt(bytes(ozt_list))

    def test_decode_ozt_too_small(self) -> None:
        with self.assertRaises(ValueError):
            _decode_ozt(b"\x00" * 10)


# ======================================================================
# Test: TGA decoder
# ======================================================================

class TestTGADecoder(unittest.TestCase):
    """Test TGA decoding (uncompressed RGB/RGBA)."""

    def _make_tga(self, width: int, height: int, channels: int = 4,
                  r: int = 255, g: int = 128, b: int = 64, a: int = 255,
                  rle: bool = False, top_down: bool = False) -> bytes:
        """Create a synthetic TGA file."""
        tga = bytearray()
        tga.append(0)                        # id_length
        tga.append(0)                        # colormap_type
        tga.append(10 if rle else 2)         # image_type
        # colormap spec (5 bytes)
        tga += b"\x00\x00\x00\x00\x00"
        # x/y origin (4 bytes)
        tga += _pack("hh", 0, 0)
        tga += _pack("hh", width, height)
        tga.append(channels * 8)             # bpp
        desc = 0x20 if top_down else 0x00
        tga.append(desc)                     # descriptor

        # Pixel data (BGRA order, bottom-up by default)
        pixels = bytearray()
        for y in range(height):
            for x in range(width):
                pixels.append(b)  # B
                pixels.append(g)  # G
                pixels.append(r)  # R
                if channels == 4:
                    pixels.append(a)

        tga += pixels
        return bytes(tga)

    def test_decode_tga_rgba(self) -> None:
        tga = self._make_tga(4, 4, channels=4)
        td = _decode_tga(tga)
        self.assertEqual(td.width, 4)
        self.assertEqual(td.height, 4)
        self.assertEqual(td.channels, 4)
        # B=64, G=128, R=255 → RGBA(255, 128, 64, 255)
        self.assertEqual(td.data[0], 255)
        self.assertEqual(td.data[1], 128)
        self.assertEqual(td.data[2], 64)
        self.assertEqual(td.data[3], 255)

    def test_decode_tga_rgb(self) -> None:
        """24-bit TGA (3 channels) should be padded to RGBA."""
        tga = self._make_tga(2, 2, channels=3)
        td = _decode_tga(tga)
        self.assertEqual(td.channels, 4)

    def test_decode_tga_too_small(self) -> None:
        with self.assertRaises(ValueError):
            _decode_tga(b"\x00" * 10)

    def test_decode_tga_unsupported_type(self) -> None:
        tga = bytearray(self._make_tga(2, 2))
        tga[2] = 1  # unsupported type
        with self.assertRaises(ValueError):
            _decode_tga(bytes(tga))


# ======================================================================
# Test: DDS decoder
# ======================================================================

class TestDDSDecoder(unittest.TestCase):
    """Test DDS decoding. Requires Pillow."""

    def setUp(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")

    def _make_dds_header(self, width: int = 8, height: int = 8) -> bytes:
        """Create a minimal DDS uncompressed RGBA header followed by pixel data."""
        # This is a simplified DDS - just enough for Pillow to parse
        # DDS header is 128 bytes
        hdr = bytearray(128)
        hdr[0:4] = b"DDS "
        # Size (124), flags, height, width, pitch, etc.
        _pack_into("<I", hdr, 4, 124)   # size
        _pack_into("<I", hdr, 8, 0x00021007)  # flags (DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE)
        _pack_into("<I", hdr, 12, height)
        _pack_into("<I", hdr, 16, width)
        _pack_into("<I", hdr, 20, width * height * 4)  # pitch

        # Pixel format at offset 76
        _pack_into("<I", hdr, 76, 32)  # size
        _pack_into("<I", hdr, 80, 0x41)  # flags (DDPF_RGB | DDPF_ALPHAPIXELS)
        hdr[84:88] = b"DXT5" if False else b"\x00\x00\x00\x00"  # fourCC (none for RGBA)
        # For uncompressed, we use RGB bit counts
        _pack_into("<I", hdr, 88, 32)  # bit count
        _pack_into("<I", hdr, 92, 0x00FF0000)  # R mask
        _pack_into("<I", hdr, 96, 0x0000FF00)  # G mask
        _pack_into("<I", hdr, 100, 0x000000FF)  # B mask
        _pack_into("<I", hdr, 104, 0xFF000000)  # A mask

        # Caps
        _pack_into("<I", hdr, 108, 0x1000)  # DDSCAPS_TEXTURE

        return bytes(hdr)

    def test_decode_dds(self) -> None:
        hdr = self._make_dds_header(4, 4)
        # Append raw RGBA pixel data
        pixels = b"\x80\x40\x20\xFF" * 16  # RGBA(128, 64, 32, 255) * 16
        dds = hdr + pixels

        td = _decode_dds(dds)
        self.assertEqual(td.width, 4)
        self.assertEqual(td.height, 4)
        self.assertEqual(td.channels, 4)


# ======================================================================
# Test: JPEG / PNG decoders
# ======================================================================

class TestStandardFormatDecoders(unittest.TestCase):
    """Test JPEG/PNG decoding. Requires Pillow."""

    def setUp(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")

    def _make_test_image_bytes(self, fmt: str, width: int = 4, height: int = 4) -> bytes:
        """Create a small test image in the given format."""
        from PIL import Image
        import io as _io

        img = Image.new("RGB", (width, height), color=(192, 96, 48))
        buf = _io.BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()

    def test_decode_jpg(self) -> None:
        data = self._make_test_image_bytes("JPEG")
        td = _decode_jpg(data)
        self.assertEqual(td.width, 4)
        self.assertEqual(td.height, 4)
        self.assertEqual(td.channels, 4)

    def test_decode_png(self) -> None:
        data = self._make_test_image_bytes("PNG")
        td = _decode_png(data)
        self.assertEqual(td.width, 4)
        self.assertEqual(td.height, 4)
        self.assertEqual(td.channels, 4)


# ======================================================================
# Test: TextureLoader
# ======================================================================

class TestTextureLoader(unittest.TestCase):
    """Test TextureLoader file resolution and caching."""

    def setUp(self) -> None:
        self.tmp_dir = os.path.join(os.path.dirname(__file__), "_test_textures")
        os.makedirs(self.tmp_dir, exist_ok=True)

        # Create a small test PNG file
        try:
            from PIL import Image
            img = Image.new("RGB", (2, 2), color=(255, 0, 0))
            img.save(os.path.join(self.tmp_dir, "test.png"))
            img.save(os.path.join(self.tmp_dir, "test.jpg"), format="JPEG")
            self.has_pillow = True
        except ImportError:
            self.has_pillow = False

        # Create a synthetic OZT file
        ozt = self._make_small_ozt()
        with open(os.path.join(self.tmp_dir, "test.ozt"), "wb") as f:
            f.write(ozt)

        # Create a synthetic OZJ file
        if self.has_pillow:
            ozj = self._make_small_ozj()
            with open(os.path.join(self.tmp_dir, "test.ozj"), "wb") as f:
                f.write(ozj)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @staticmethod
    def _make_small_ozt(nx: int = 4, ny: int = 4) -> bytes:
        header = b"\x00" * 16
        header += _pack("h", nx)
        header += _pack("h", ny)
        header += _pack("B", 32)  # depth
        header += _pack("B", 0)
        pixels = bytearray()
        for _ in range(ny):
            for _ in range(nx):
                pixels += b"\x40\x80\xFF\xFF"  # BGRA
        return bytes(header + bytes(pixels))

    @staticmethod
    def _make_small_ozj() -> bytes:
        from PIL import Image
        import io as _io
        img = Image.new("RGB", (4, 4), color=(128, 64, 32))
        buf = _io.BytesIO()
        img.save(buf, format="JPEG")
        jpeg = buf.getvalue()

        ozj = bytearray()
        ozj += _pack("I", 0x4A5A4F5A)  # magic
        ozj += _pack("h", 1)
        ozj += b"JPEG"
        ozj += b"\x00" * 7
        ozj += _pack("?", True)  # isTopDownSort
        ozj += b"\x00" * 6
        ozj += jpeg
        return bytes(ozj)

    def test_load_png(self) -> None:
        if not self.has_pillow:
            self.skipTest("Pillow not installed")
        loader = TextureLoader(data_path=self.tmp_dir)
        td = loader.load("test.png")
        self.assertIsNotNone(td)
        self.assertEqual(td.width, 2)  # type: ignore[union-attr]
        self.assertEqual(td.height, 2)  # type: ignore[union-attr]

    def test_load_jpg(self) -> None:
        if not self.has_pillow:
            self.skipTest("Pillow not installed")
        loader = TextureLoader(data_path=self.tmp_dir)
        td = loader.load("test.jpg")
        self.assertIsNotNone(td)

    def test_load_ozt(self) -> None:
        loader = TextureLoader(data_path=self.tmp_dir)
        td = loader.load("test.ozt")
        self.assertIsNotNone(td)
        self.assertEqual(td.width, 4)  # type: ignore[union-attr]
        self.assertEqual(td.height, 4)  # type: ignore[union-attr]

    def test_load_ozj(self) -> None:
        if not self.has_pillow:
            self.skipTest("Pillow not installed")
        loader = TextureLoader(data_path=self.tmp_dir)
        td = loader.load("test.ozj")
        self.assertIsNotNone(td)
        self.assertEqual(td.width, 4)  # type: ignore[union-attr]
        self.assertEqual(td.height, 4)  # type: ignore[union-attr]

    def test_load_nonexistent(self) -> None:
        loader = TextureLoader(data_path=self.tmp_dir)
        td = loader.load("nonexistent.png")
        self.assertIsNone(td)

    def test_cache(self) -> None:
        if not self.has_pillow:
            self.skipTest("Pillow not installed")
        loader = TextureLoader(data_path=self.tmp_dir)
        td1 = loader.load("test.png", use_cache=True)
        td2 = loader.load("test.png", use_cache=True)
        # Same object if cached
        self.assertIs(td1, td2)

    def test_clear_cache(self) -> None:
        if not self.has_pillow:
            self.skipTest("Pillow not installed")
        loader = TextureLoader(data_path=self.tmp_dir)
        td1 = loader.load("test.png")
        loader.clear_cache()
        td2 = loader.load("test.png")
        self.assertIsNot(td1, td2)

    def test_unsupported_extension(self) -> None:
        # Create a file with unsupported extension
        path = os.path.join(self.tmp_dir, "test.xyz")
        with open(path, "wb") as f:
            f.write(b"dummy")
        loader = TextureLoader(data_path=self.tmp_dir)
        td = loader.load("test.xyz")
        self.assertIsNone(td)

    def test_absolute_path(self) -> None:
        if not self.has_pillow:
            self.skipTest("Pillow not installed")
        png_path = os.path.join(self.tmp_dir, "test.png")
        loader = TextureLoader()
        td = loader.load(png_path)
        self.assertIsNotNone(td)


# ======================================================================
# Helper: pack_into for bytearray
# ======================================================================

def _pack_into(fmt: str, buf: bytearray, offset: int, *values: Any) -> None:
    """Pack values into a bytearray at the given offset."""
    packed = struct.pack(fmt if fmt.startswith("<") else "<" + fmt, *values)
    buf[offset:offset + len(packed)] = packed


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
