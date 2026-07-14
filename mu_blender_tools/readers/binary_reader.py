# MU Online Blender Tools - BinaryReader
#
# A sequential binary reader wrapping a byte buffer.
# Mirrors the functionality of C# System.IO.BinaryReader
# plus the BinaryReaderExtensions from xulek/muonline (Client.Data/).
#
# API naming convention: follows C# BinaryReader method names
# (ReadByte, ReadUInt16, ReadInt32, ReadFloat, ReadString, etc.)
#
# Reference implementations:
#   - C#: System.IO.BinaryReader + BinaryReaderExtensions
#         https://github.com/xulek/muonline/blob/main/Client.Data/BinaryReaderExtensions.cs
#   - TS: DataView offset tracking + BinaryStruct.ts
#         https://github.com/xulek/muonline-bmd-viewer/blob/main/src/BinaryStruct.ts
#
# Design:
#   - Pure Python 3.11+, no external dependencies
#   - All multi-byte values are little-endian (MU format convention)
#   - Offset is tracked internally
#   - Bounds-checked: all reads verify against buffer size

from __future__ import annotations

import struct
from typing import Any

from .._exceptions import BinaryReaderError
from .._logging import get_logger

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

_logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Struct format characters (little-endian)
# ---------------------------------------------------------------------------

_FMT_U8: str = "<B"
_FMT_I8: str = "<b"
_FMT_U16: str = "<H"
_FMT_I16: str = "<h"
_FMT_U32: str = "<I"
_FMT_I32: str = "<i"
_FMT_F32: str = "<f"
_FMT_F64: str = "<d"

# ---------------------------------------------------------------------------
# SeekOrigin constants (matching C# System.IO.SeekOrigin)
# ---------------------------------------------------------------------------


class SeekOrigin:
    """Matching C# System.IO.SeekOrigin."""
    Begin: int = 0
    Current: int = 1
    End: int = 2


# ---------------------------------------------------------------------------
# BinaryReader
# ---------------------------------------------------------------------------


class BinaryReader:
    """Sequential reader for little-endian binary data.

    Wraps a ``bytes`` buffer and maintains an internal read offset.
    All multi-byte reads are **little-endian**, matching the MU Online
    file format convention.

    Method names follow C# ``System.IO.BinaryReader`` conventions:

        ReadByte()      -> int (0-255)
        ReadUInt16()    -> int
        ReadUInt32()    -> int
        ReadInt16()     -> int
        ReadInt32()     -> int
        ReadFloat()     -> float
        ReadDouble()    -> float
        ReadBool()      -> bool
        ReadString(len) -> str   (fixed-length, null-terminated)
        ReadBytes(cnt)  -> bytes

    Position control (matching C# BaseStream):

        Seek(offset, origin) -> int   (origin = SeekOrigin.Begin/Current/End)
        Tell()               -> int   (current offset)
        Skip(count)          -> int
        EOF                  -> bool  (property)
        Size                 -> int   (total buffer length)

    Usage::

        data = open("file.bmd", "rb").read()
        br = BinaryReader(data)
        name = br.ReadString(32)
        mesh_count = br.ReadUInt16()
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, data: bytes | bytearray, offset: int = 0) -> None:
        """Initialize reader with binary data.

        Args:
            data: The binary buffer to read from.
            offset: Initial read offset (default 0).

        Raises:
            BinaryReaderError: If offset is out of bounds.
        """
        if isinstance(data, bytearray):
            data = bytes(data)

        self._buffer: bytes = data
        self._size: int = len(data)
        self._offset: int = 0

        if offset < 0 or offset > self._size:
            raise BinaryReaderError(
                f"Initial offset {offset} is out of bounds for buffer "
                f"size {self._size}."
            )
        self._offset = offset

    # ------------------------------------------------------------------
    # Position properties
    # ------------------------------------------------------------------

    @property
    def EOF(self) -> bool:
        """True if the reader has reached (or passed) the end of the buffer.

        Like C# ``BaseStream.Position >= BaseStream.Length``.
        """
        return self._offset >= self._size

    @property
    def Size(self) -> int:
        """Total buffer size in bytes (like C# ``BaseStream.Length``)."""
        return self._size

    @property
    def Remaining(self) -> int:
        """Number of unread bytes remaining."""
        return self._size - self._offset

    # ------------------------------------------------------------------
    # Position control
    # ------------------------------------------------------------------

    def Tell(self) -> int:
        """Return the current read offset.

        Like C# ``BaseStream.Position`` getter.

        Returns:
            Current offset in bytes from the start of the buffer.
        """
        return self._offset

    def Seek(self, offset: int, origin: int = SeekOrigin.Begin) -> int:
        """Move the read offset.

        Like C# ``BaseStream.Seek(offset, origin)``.

        Args:
            offset: Byte offset relative to ``origin``.
            origin: ``SeekOrigin.Begin`` (0), ``SeekOrigin.Current`` (1),
                    or ``SeekOrigin.End`` (2). Defaults to Begin.

        Returns:
            The new offset value.

        Raises:
            BinaryReaderError: If the resulting position is out of bounds.
        """
        if origin == SeekOrigin.Begin:
            new_offset = offset
        elif origin == SeekOrigin.Current:
            new_offset = self._offset + offset
        elif origin == SeekOrigin.End:
            new_offset = self._size + offset
        else:
            raise ValueError(f"Invalid origin value: {origin}")

        if new_offset < 0 or new_offset > self._size:
            raise BinaryReaderError(
                f"Seek to {offset} (origin={origin}) would result in "
                f"position {new_offset}, which is out of bounds (0..{self._size})."
            )

        self._offset = new_offset
        return self._offset

    def Skip(self, count: int) -> int:
        """Advance the offset by *count* bytes (forward or backward).

        Like ``Seek(count, SeekOrigin.Current)``.

        Args:
            count: Number of bytes to skip (negative to go backward).

        Returns:
            The new offset.
        """
        return self.Seek(count, SeekOrigin.Current)

    # ------------------------------------------------------------------
    # Byte reads
    # ------------------------------------------------------------------

    def ReadByte(self) -> int:
        """Read an unsigned 8-bit integer (0..255).

        Matches C# ``BinaryReader.ReadByte()``.

        Returns:
            Integer in range 0..255.
        """
        self._ensure(1)
        value = struct.unpack_from(_FMT_U8, self._buffer, self._offset)[0]
        self._offset += 1
        return value

    def ReadBytes(self, count: int) -> bytes:
        """Read *count* raw bytes and advance the offset.

        Matches C# ``BinaryReader.ReadBytes(int count)``.

        Args:
            count: Number of bytes to read.

        Returns:
            The requested bytes (may be fewer if at end of buffer).
        """
        actual = min(count, self.Remaining)
        result = self._buffer[self._offset:self._offset + actual]
        self._offset += actual
        return result

    def PeekBytes(self, count: int) -> bytes:
        """Read *count* bytes without advancing the offset.

        Args:
            count: Number of bytes to peek.

        Returns:
            The requested bytes.
        """
        self._ensure(count)
        return self._buffer[self._offset:self._offset + count]

    def ReadRemaining(self) -> bytes:
        """Read all bytes from the current offset to the end of the buffer."""
        return self.ReadBytes(self.Remaining)

    # ------------------------------------------------------------------
    # Unsigned integer reads
    # ------------------------------------------------------------------

    def ReadUInt16(self) -> int:
        """Read an unsigned 16-bit integer (little-endian, 0..65535).

        Matches C# ``BinaryReader.ReadUInt16()``.
        """
        self._ensure(2)
        value = struct.unpack_from(_FMT_U16, self._buffer, self._offset)[0]
        self._offset += 2
        return value

    def ReadUInt32(self) -> int:
        """Read an unsigned 32-bit integer (little-endian, 0..4294967295).

        Matches C# ``BinaryReader.ReadUInt32()``.
        """
        self._ensure(4)
        value = struct.unpack_from(_FMT_U32, self._buffer, self._offset)[0]
        self._offset += 4
        return value

    # ------------------------------------------------------------------
    # Signed integer reads
    # ------------------------------------------------------------------

    def ReadInt16(self) -> int:
        """Read a signed 16-bit integer (little-endian, -32768..32767).

        Matches C# ``BinaryReader.ReadInt16()``.
        """
        self._ensure(2)
        value = struct.unpack_from(_FMT_I16, self._buffer, self._offset)[0]
        self._offset += 2
        return value

    def ReadInt32(self) -> int:
        """Read a signed 32-bit integer (little-endian, -2147483648..2147483647).

        Matches C# ``BinaryReader.ReadInt32()``.
        """
        self._ensure(4)
        value = struct.unpack_from(_FMT_I32, self._buffer, self._offset)[0]
        self._offset += 4
        return value

    # ------------------------------------------------------------------
    # Floating-point reads
    # ------------------------------------------------------------------

    def ReadFloat(self) -> float:
        """Read a 32-bit float (little-endian).

        Matches C# ``BinaryReader.ReadSingle()``.
        """
        self._ensure(4)
        value = struct.unpack_from(_FMT_F32, self._buffer, self._offset)[0]
        self._offset += 4
        return value

    def ReadDouble(self) -> float:
        """Read a 64-bit double-precision float (little-endian).

        Matches C# ``BinaryReader.ReadDouble()``.
        """
        self._ensure(8)
        value = struct.unpack_from(_FMT_F64, self._buffer, self._offset)[0]
        self._offset += 8
        return value

    # ------------------------------------------------------------------
    # Boolean
    # ------------------------------------------------------------------

    def ReadBool(self) -> bool:
        """Read a boolean value (1 byte, non-zero = True).

        Matches C# ``BinaryReader.ReadBoolean()``.
        """
        return self.ReadByte() != 0

    # ------------------------------------------------------------------
    # String reads
    # ------------------------------------------------------------------

    def ReadString(self, length: int, encoding: str = "ascii") -> str:
        """Read a fixed-length null-terminated ASCII string.

        Matches the C# extension method ``BinaryReaderExtensions.ReadString(int length)``
        and the TypeScript ``readStringFromDataView()``.

        The reader consumes exactly *length* bytes. The returned string is
        truncated at the first null byte (if any).

        Args:
            length: Exact number of bytes to consume from the buffer.
            encoding: Text encoding to use (default ``"ascii"``).

        Returns:
            Decoded string, with trailing nulls and whitespace stripped.
        """
        raw = self.ReadBytes(length)
        null_pos = raw.find(b"\x00")
        if null_pos >= 0:
            raw = raw[:null_pos]
        return raw.decode(encoding, errors="replace").rstrip("\x00").rstrip()

    def ReadCString(self, encoding: str = "ascii") -> str:
        """Read a null-terminated string of unknown length.

        Reads until a ``\\x00`` byte is encountered (or end of buffer).
        Consumes the null terminator if found.

        Args:
            encoding: Text encoding to use (default ``"ascii"``).

        Returns:
            Decoded string (without the null terminator).
        """
        start = self._offset
        end = start
        while end < self._size and self._buffer[end] != 0:
            end += 1
        raw = self._buffer[start:end]
        # Consume the null terminator too (if present)
        self._offset = end + 1 if end < self._size else end
        return raw.decode(encoding, errors="replace")

    # ------------------------------------------------------------------
    # Struct reads (flexible format)
    # ------------------------------------------------------------------

    def ReadStruct(self, fmt: str) -> tuple[Any, ...]:
        """Read a struct using a ``struct`` module format string.

    The format string should use little-endian prefix (``<``).
    If no endianness prefix is given, ``<`` is automatically prepended.

        Args:
            fmt: ``struct`` format string (e.g. ``"<h3f"``, ``"<I2H"``).

        Returns:
            Tuple of unpacked values.

        Example::

            count, x, y, z = br.ReadStruct("<H3f")
        """
        if not fmt.startswith(("<", ">", "!")):
            fmt = "<" + fmt
        size = struct.calcsize(fmt)
        self._ensure(size)
        values = struct.unpack_from(fmt, self._buffer, self._offset)
        self._offset += size
        return values

    def ReadStructArray(self, fmt: str, count: int) -> list[tuple[Any, ...]]:
        """Read an array of identical structs.

        More efficient than calling ``ReadStruct(fmt)`` *count* times.
        This corresponds to the C# extension ``ReadStructArray<T>(int length)``.

        Args:
            fmt: ``struct`` format string (little-endian).
            count: Number of elements to read.

        Returns:
            List of unpacked tuples.

        Example::

            vertices = br.ReadStructArray("<h3f", 10)
        """
        if not fmt.startswith(("<", ">", "!")):
            fmt = "<" + fmt
        elem_size = struct.calcsize(fmt)
        total = elem_size * count
        self._ensure(total)

        result: list[tuple[Any, ...]] = []
        for _ in range(count):
            values = struct.unpack_from(fmt, self._buffer, self._offset)
            result.append(values)
            self._offset += elem_size
        return result

    # ------------------------------------------------------------------
    # Vector reads (convenience)
    # ------------------------------------------------------------------

    def ReadVector3(self) -> tuple[float, float, float]:
        """Read a 3-component float vector (12 bytes, little-endian).

        Returns:
            Tuple ``(x, y, z)``.
        """
        return self.ReadStruct("<3f")  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure(self, count: int) -> None:
        """Check that *count* bytes can be read from the current offset.

        Raises:
            BinaryReaderError: If not enough bytes remain.
        """
        if self._offset + count > self._size:
            raise BinaryReaderError(
                f"Requested {count} byte(s) at offset {self._offset}, "
                f"but only {self.Remaining} byte(s) remain "
                f"(buffer size = {self._size})."
            )

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "BinaryReader":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<BinaryReader offset={self._offset}/{self._size} "
            f"remaining={self.Remaining}>"
        )

    def __len__(self) -> int:
        return self._size
