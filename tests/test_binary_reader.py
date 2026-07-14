# MU Online Blender Tools - Tests for BinaryReader
#
# Run with:  python -m unittest tests.test_binary_reader -v
# Or:        python -m pytest tests/test_binary_reader.py -v

"""
Tests for ``mu_blender_tools.readers.binary_reader.BinaryReader``.

Verifies that the API matches C# ``System.IO.BinaryReader`` conventions
and that all read operations behave correctly.
"""

from __future__ import annotations

import struct
import sys
import unittest
from typing import Any

sys.path.insert(0, ".")

from mu_blender_tools.readers.binary_reader import (
    BinaryReader,
    BinaryReaderError,
    SeekOrigin,
)


# ======================================================================
# Helper
# ======================================================================

def _build(fmt: str, *values: Any) -> bytes:
    """Pack values into little-endian bytes."""
    if not fmt.startswith("<"):
        fmt = "<" + fmt
    return struct.pack(fmt, *values)


# ======================================================================
# Tests
# ======================================================================


class TestBinaryReaderPrimitives(unittest.TestCase):
    """Test primitive integer and float reads."""

    def setUp(self) -> None:
        # Each read test creates its own BinaryReader with clean data
        pass

    def test_ReadByte(self) -> None:
        br = BinaryReader(b"\xAB\xCD")
        self.assertEqual(br.ReadByte(), 0xAB)
        self.assertEqual(br.Tell(), 1)
        self.assertEqual(br.ReadByte(), 0xCD)

    def test_ReadUInt16(self) -> None:
        br = BinaryReader(_build("H", 0x1234))
        self.assertEqual(br.ReadUInt16(), 0x1234)
        self.assertEqual(br.Tell(), 2)

    def test_ReadUInt32(self) -> None:
        br = BinaryReader(_build("I", 0x12345678))
        self.assertEqual(br.ReadUInt32(), 0x12345678)

    def test_ReadInt16(self) -> None:
        br = BinaryReader(_build("h", -32768))
        self.assertEqual(br.ReadInt16(), -32768)

    def test_ReadInt32(self) -> None:
        br = BinaryReader(_build("i", -2000000000))
        self.assertEqual(br.ReadInt32(), -2000000000)

    def test_ReadFloat(self) -> None:
        br = BinaryReader(_build("f", 3.14159265))
        self.assertAlmostEqual(br.ReadFloat(), 3.14159265, places=6)

    def test_ReadDouble(self) -> None:
        br = BinaryReader(_build("d", 1.0e100))
        self.assertAlmostEqual(br.ReadDouble(), 1.0e100, places=10)

    def test_ReadBool(self) -> None:
        br = BinaryReader(_build("B", 0) + _build("B", 1) + _build("B", 42))
        self.assertFalse(br.ReadBool())
        self.assertTrue(br.ReadBool())
        self.assertTrue(br.ReadBool())


class TestBinaryReaderPosition(unittest.TestCase):
    """Test Tell, Seek, Skip, EOF."""

    def setUp(self) -> None:
        self.br = BinaryReader(b"\x00" * 32)

    def test_Tell(self) -> None:
        self.assertEqual(self.br.Tell(), 0)
        self.assertFalse(self.br.EOF)
        self.assertEqual(self.br.Remaining, 32)

    def test_Seek_absolute(self) -> None:
        self.br.Seek(16)
        self.assertEqual(self.br.Tell(), 16)

    def test_Seek_relative(self) -> None:
        self.br.Seek(8)
        self.br.Seek(4, SeekOrigin.Current)
        self.assertEqual(self.br.Tell(), 12)

    def test_Seek_end(self) -> None:
        self.br.Seek(-4, SeekOrigin.End)
        self.assertEqual(self.br.Tell(), 28)

    def test_Skip(self) -> None:
        self.br.Skip(10)
        self.assertEqual(self.br.Tell(), 10)
        self.br.Skip(-3)
        self.assertEqual(self.br.Tell(), 7)

    def test_EOF(self) -> None:
        self.br.Seek(32)
        self.assertTrue(self.br.EOF)

    def test_ReadRemaining(self) -> None:
        self.br.Seek(10)
        rem = self.br.ReadRemaining()
        self.assertEqual(len(rem), 22)

    def test_out_of_bounds_Seek(self) -> None:
        with self.assertRaises(BinaryReaderError):
            self.br.Seek(-1)
        with self.assertRaises(BinaryReaderError):
            self.br.Seek(33)

    def test_out_of_bounds_read(self) -> None:
        br = BinaryReader(b"\x01\x02\x03")
        with self.assertRaises(BinaryReaderError):
            br.ReadInt32()


class TestBinaryReaderString(unittest.TestCase):
    """Test ReadString (fixed-length null-terminated) and ReadCString."""

    def test_ReadString_fixed(self) -> None:
        """Fixed-length null-terminated string (matching C# extension)."""
        raw = b"Hello\x00\x00\x00..."
        br = BinaryReader(raw)
        s = br.ReadString(8)
        self.assertEqual(s, "Hello")
        self.assertEqual(br.Tell(), 8)

    def test_ReadString_no_null(self) -> None:
        """String without null terminator within the fixed length."""
        raw = b"ABCDEFGH"
        br = BinaryReader(raw)
        s = br.ReadString(8)
        self.assertEqual(s, "ABCDEFGH")

    def test_ReadString_unicode(self) -> None:
        """String with non-ASCII characters."""
        raw = "Café\x00".encode("utf-8") + b"\x00" * 3
        br = BinaryReader(raw)
        s = br.ReadString(8, encoding="utf-8")
        self.assertEqual(s, "Café")

    def test_ReadCString(self) -> None:
        """Null-terminated string of unknown length."""
        raw = b"Monster\x00MoreData"
        br = BinaryReader(raw)
        s = br.ReadCString()
        self.assertEqual(s, "Monster")
        # 7 chars + 1 null = 8 bytes
        self.assertEqual(br.Tell(), 8)

    def test_ReadCString_eof(self) -> None:
        """C-string that runs to end of buffer (no null)."""
        raw = b"NoNullHere"
        br = BinaryReader(raw)
        s = br.ReadCString()
        self.assertEqual(s, "NoNullHere")
        self.assertTrue(br.EOF)


class TestBinaryReaderReadBytes(unittest.TestCase):
    """Test ReadBytes and PeekBytes."""

    def test_ReadBytes(self) -> None:
        data = bytes(range(256))
        br = BinaryReader(data)
        chunk = br.ReadBytes(10)
        self.assertEqual(chunk, bytes(range(10)))
        self.assertEqual(br.Tell(), 10)

    def test_ReadBytes_short_at_eof(self) -> None:
        """Reading near end returns fewer bytes (like C# ReadBytes)."""
        data = b"\x01\x02\x03"
        br = BinaryReader(data)
        result = br.ReadBytes(10)
        self.assertEqual(result, b"\x01\x02\x03")
        self.assertTrue(br.EOF)

    def test_PeekBytes(self) -> None:
        data = b"\x01\x02\x03\x04"
        br = BinaryReader(data)
        peeked = br.PeekBytes(2)
        self.assertEqual(peeked, b"\x01\x02")
        self.assertEqual(br.Tell(), 0)  # offset unchanged


class TestBinaryReaderStruct(unittest.TestCase):
    """Test ReadStruct and ReadStructArray."""

    def test_ReadStruct(self) -> None:
        raw = _build("H3f", 5, 1.0, 2.0, 3.0)
        br = BinaryReader(raw)
        count, x, y, z = br.ReadStruct("<H3f")
        self.assertEqual(count, 5)
        self.assertAlmostEqual(x, 1.0)
        self.assertAlmostEqual(y, 2.0)
        self.assertAlmostEqual(z, 3.0)

    def test_ReadStruct_auto_endian(self) -> None:
        """Format string without prefix should auto-prepend '<'."""
        raw = _build("H", 42)
        br = BinaryReader(raw)
        (val,) = br.ReadStruct("H")
        self.assertEqual(val, 42)

    def test_ReadStructArray(self) -> None:
        raw = _build("2h", 10, 20) + _build("2h", 30, 40) + _build("2h", 50, 60)
        br = BinaryReader(raw)
        arr = br.ReadStructArray("<2h", 3)
        self.assertEqual(len(arr), 3)
        self.assertEqual(arr[0], (10, 20))
        self.assertEqual(arr[1], (30, 40))
        self.assertEqual(arr[2], (50, 60))

    def test_ReadVector3(self) -> None:
        raw = _build("3f", 100.0, 200.0, 300.0)
        br = BinaryReader(raw)
        vx, vy, vz = br.ReadVector3()
        self.assertAlmostEqual(vx, 100.0)
        self.assertAlmostEqual(vy, 200.0)
        self.assertAlmostEqual(vz, 300.0)


class TestBinaryReaderErrors(unittest.TestCase):
    """Test error handling."""

    def test_empty_buffer(self) -> None:
        with self.assertRaises(BinaryReaderError):
            BinaryReader(b"", offset=1)

    def test_read_past_end(self) -> None:
        br = BinaryReader(b"\x01")
        br.ReadByte()
        with self.assertRaises(BinaryReaderError):
            br.ReadByte()

    def test_repr(self) -> None:
        br = BinaryReader(b"\x00" * 16)
        r = repr(br)
        self.assertIn("BinaryReader", r)

    def test_len(self) -> None:
        br = BinaryReader(b"\x00" * 100)
        self.assertEqual(len(br), 100)

    def test_Size(self) -> None:
        br = BinaryReader(b"\x00" * 64)
        self.assertEqual(br.Size, 64)

    def test_Remaining(self) -> None:
        br = BinaryReader(b"\x00" * 10)
        br.Seek(3)
        self.assertEqual(br.Remaining, 7)


class TestBinaryReaderContextManager(unittest.TestCase):
    """Test context manager usage."""

    def test_context_manager(self) -> None:
        data = b"\x01\x02\x03\x04"
        with BinaryReader(data) as br:
            val = br.ReadUInt32()
        self.assertEqual(val, 0x04030201)


class TestSeekOrigin(unittest.TestCase):
    """Test SeekOrigin constants."""

    def test_constants(self) -> None:
        self.assertEqual(SeekOrigin.Begin, 0)
        self.assertEqual(SeekOrigin.Current, 1)
        self.assertEqual(SeekOrigin.End, 2)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
