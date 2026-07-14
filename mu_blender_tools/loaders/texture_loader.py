# MU Online Blender Tools - TextureLoader
#
# Loads and decodes MU Online texture formats (OZJ, OZT, DDS, TGA, JPG).
# Also handles plain JPEG/PNG files.
#
# Reference implementations:
#   - C#: Client.Data.Texture.OZJReader, OZTReader, OZDReader
#         Client.Main.Content.TextureLoader
#   - TS: src/ozj-loader.ts, src/gfx-browser/ozg-cryptor.ts
#
# Design:
#   - No bpy imports — pure data layer
#   - Returns TextureData namedtuple with width/height/channels/pixels
#   - Supports auto-search in Data directory
#   - Built-in decoders for OZJ/OZT/DDS/TGA

from __future__ import annotations

import io
import logging
import math
import os
import struct
from dataclasses import dataclass
from typing import Optional

_logger = logging.getLogger("mu_blender_tools")


# ======================================================================
# TextureData — universal texture container
# ======================================================================


@dataclass
class TextureData:
    """Decoded texture data in RGBA format.

    Matches the concept of C# ``Client.Data.Texture.TextureData``.

    Attributes:
        width: Image width in pixels.
        height: Image height in pixels.
        channels: Number of color channels (3=RGB, 4=RGBA).
        data: Flat byte array in RGBA order (row-major, top-to-bottom).
    """
    width: int
    height: int
    channels: int
    data: bytes


# ======================================================================
# TextureLoader
# ======================================================================


class TextureLoader:
    """Loads and decodes MU Online texture files.

    Supports: OZJ, OZT, DDS, TGA, JPG, PNG.

    Usage::

        loader = TextureLoader(data_path="/path/to/Data")
        tex = loader.load("Player/human_face.jpg")
        # tex is a TextureData with width, height, channels, data
    """

    def __init__(self, data_path: Optional[str] = None) -> None:
        """Initialize the texture loader.

        Args:
            data_path: Root MU Online Data directory. If not set,
                       the loader will only accept absolute paths.
        """
        self._data_path: Optional[str] = data_path
        self._cache: dict[str, TextureData] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def data_path(self) -> Optional[str]:
        return self._data_path

    @data_path.setter
    def data_path(self, path: Optional[str]) -> None:
        self._data_path = path

    def load(self, path: str, use_cache: bool = True) -> Optional[TextureData]:
        """Load and decode a texture file.

        Args:
            path: Relative or absolute path to the texture file.
            use_cache: If True (default), cached results are returned.

        Returns:
            TextureData if successful, None on failure.
        """
        # Resolve the full path
        full_path = self._resolve_path(path)
        if not full_path:
            _logger.warning("Texture not found: %s", path)
            return None

        # Check cache
        if use_cache and full_path in self._cache:
            return self._cache[full_path]

        # Read file
        try:
            with open(full_path, "rb") as f:
                raw = f.read()
        except OSError as e:
            _logger.error("Failed to read texture file '%s': %s", full_path, e)
            return None

        # Detect format and decode
        ext = os.path.splitext(full_path)[1].lower()
        tex = self._decode(raw, ext, full_path)

        if tex is not None and use_cache:
            self._cache[full_path] = tex

        return tex

    def clear_cache(self) -> None:
        """Clear the internal texture cache."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    def _resolve_path(self, path: str) -> Optional[str]:
        """Find the actual file path, searching the Data directory if needed.

        Resolution order:
          1. If path is absolute and exists, return it.
          2. If data_path is set, try join(data_path, path).
          3. Case-insensitive search in parent directory.
        """
        # Direct absolute path
        if os.path.isabs(path) and os.path.isfile(path):
            return os.path.abspath(path)

        # Try relative to data_path
        if self._data_path:
            candidate = os.path.join(self._data_path, path)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

            # Case-insensitive search in parent dir
            parent = os.path.dirname(candidate)
            filename = os.path.basename(candidate)
            if os.path.isdir(parent):
                for entry in os.listdir(parent):
                    if entry.lower() == filename.lower():
                        return os.path.abspath(os.path.join(parent, entry))

        # Try as relative path from CWD
        if os.path.isfile(path):
            return os.path.abspath(path)

        return None

    # ------------------------------------------------------------------
    # Format detection and dispatch
    # ------------------------------------------------------------------

    @staticmethod
    def _decode(raw: bytes, ext: str, source_name: str = "") -> Optional[TextureData]:
        """Detect format from extension and decode.

        Args:
            raw: Raw file bytes.
            ext: File extension (lowercase, with dot).
            source_name: Path or name for error messages.

        Returns:
            TextureData or None.
        """
        try:
            if ext == ".ozj":
                return _decode_ozj(raw)
            elif ext == ".ozt":
                return _decode_ozt(raw)
            elif ext == ".tga":
                return _decode_tga(raw)
            elif ext == ".dds":
                return _decode_dds(raw)
            elif ext in (".jpg", ".jpeg"):
                return _decode_jpg(raw)
            elif ext == ".png":
                return _decode_png(raw)
            else:
                _logger.warning("Unsupported texture extension '%s': %s", ext, source_name)
                return None
        except Exception as e:
            _logger.error("Failed to decode '%s' (%s): %s", source_name, ext, e)
            return None


# ======================================================================
# OZJ decoder
# ======================================================================
# Reference: C# OZJReader.cs / TS ozj-loader.ts
#
# Format:
#   offset 0:  magic    (4 bytes, uint32 LE)
#   offset 4:  version  (2 bytes, int16 LE)
#   offset 6:  format   (4 bytes, ASCII, e.g. "JPEG" or "JPG ")
#   offset 17: isTopDownSort (1 byte, bool)
#   offset 24: JPEG payload begins
#
# If isTopDownSort is False, the JPEG image needs vertical flip.


def _decode_ozj(raw: bytes) -> TextureData:
    """Decode an OZJ file (JPEG in a custom container).

    Args:
        raw: Complete OZJ file bytes.

    Returns:
        TextureData in RGBA format.

    Raises:
        ValueError: On invalid format or unsupported variant.
    """
    if len(raw) < 24:
        raise ValueError("OZJ file too small")

    is_top_down = raw[17] != 0
    jpeg_start = 24

    # Extract JPEG payload
    jpeg_data = raw[jpeg_start:]

    # Decode JPEG using PIL-like approach
    # We use Python's built-in capabilities
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow is required for OZJ/JPG decoding: pip install Pillow")

    img = Image.open(io.BytesIO(jpeg_data))
    img = img.convert("RGBA")

    # Vertical flip if needed (non-top-down)
    if not is_top_down:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)

    width, height = img.size
    data = img.tobytes("raw", "RGBA")

    return TextureData(width=width, height=height, channels=4, data=data)


# ======================================================================
# OZT decoder
# ======================================================================
# Reference: C# OZTReader.cs / TS ozj-loader.ts (oztToPng)
#
# Format:
#   offset 0:   header    (16 bytes)
#   offset 16:  nx        (int16 LE)
#   offset 18:  ny        (int16 LE)
#   offset 20:  depth     (uint8, must be 32)
#   offset 21:  u1        (uint8)
#   offset 22+: pixel data (BGRA order, bottom-up, row pitch = nx * 4)
#
# Output is expanded to power-of-two dimensions.


def _decode_ozt(raw: bytes) -> TextureData:
    """Decode an OZT file (raw BGRA, bottom-up, power-of-two output).

    Args:
        raw: Complete OZT file bytes.

    Returns:
        TextureData in RGBA format (power-of-two dimensions).

    Raises:
        ValueError: On invalid format.
    """
    HEADER_SIZE = 16
    MAX_SIZE = 1024

    if len(raw) < HEADER_SIZE + 6:
        raise ValueError("OZT file too small")

    nx = struct.unpack_from("<h", raw, HEADER_SIZE)[0]         # int16
    ny = struct.unpack_from("<h", raw, HEADER_SIZE + 2)[0]     # int16
    depth = raw[HEADER_SIZE + 4]                                 # byte

    if depth != 32:
        raise ValueError(f"OZT depth must be 32, got {depth}")
    if nx <= 0 or ny <= 0 or nx > MAX_SIZE or ny > MAX_SIZE:
        raise ValueError(f"OZT invalid dimensions: {nx}x{ny}")

    # Power-of-two output dimensions
    out_w = 1 << (nx - 1).bit_length()
    out_h = 1 << (ny - 1).bit_length()

    pixel_data = raw[HEADER_SIZE + 6:]
    expected_pixels = nx * ny * 4
    if len(pixel_data) < expected_pixels:
        raise ValueError(
            f"OZT truncated: expected {expected_pixels} pixel bytes, "
            f"got {len(pixel_data)}"
        )

    # Allocate RGBA output buffer (power-of-two, top-down)
    out = bytearray(out_w * out_h * 4)

    # Each source row is nx * 4 bytes, stored bottom-up in BGRA order.
    # We write each row to the output as RGBA, top-down, padded to out_w.
    for y in range(ny):
        src_row_start = y * nx * 4
        dst_row = (ny - 1 - y) * out_w * 4  # bottom-up → top-down

        for x in range(nx):
            src_offset = src_row_start + x * 4
            dst_offset = dst_row + x * 4

            b = pixel_data[src_offset]
            g = pixel_data[src_offset + 1]
            r = pixel_data[src_offset + 2]
            a = pixel_data[src_offset + 3]

            out[dst_offset] = r
            out[dst_offset + 1] = g
            out[dst_offset + 2] = b
            out[dst_offset + 3] = a

    return TextureData(width=out_w, height=out_h, channels=4, data=bytes(out))


# ======================================================================
# TGA decoder (minimal — uncompressed RGB/RGBA)
# ======================================================================
# Reference: TS bmd-loader.ts (convertTgaToDataUrl via @lunapaint/tga-codec)
#
# TGA header:
#   offset 0:  id_length      (uint8)
#   offset 1:  colormap_type  (uint8)
#   offset 2:  image_type     (uint8) — 2=uncompressed RGB, 10=RLE
#   offset 12: width          (int16 LE)
#   offset 14: height         (int16 LE)
#   offset 16: bpp            (uint8) — 24 or 32
#   offset 17: descriptor     (uint8) — bit 5 = top-down flag


def _decode_tga(raw: bytes) -> TextureData:
    """Decode an uncompressed Truevision TGA file.

    Supports 24-bit RGB and 32-bit RGBA, uncompressed (type 2)
    and RLE-compressed (type 10).

    Args:
        raw: Complete TGA file bytes.

    Returns:
        TextureData in RGBA format.

    Raises:
        ValueError: On unsupported TGA variant.
    """
    if len(raw) < 18:
        raise ValueError("TGA file too small")

    image_type = raw[2]
    width = struct.unpack_from("<h", raw, 12)[0]
    height = struct.unpack_from("<h", raw, 14)[0]
    bpp = raw[16]
    descriptor = raw[17]

    if width <= 0 or height <= 0:
        raise ValueError(f"TGA invalid dimensions: {width}x{height}")

    top_down = bool(descriptor & 0x20)
    channels = bpp // 8  # 3 for RGB, 4 for RGBA

    # Skip ID field + colormap data
    id_length = raw[0]
    colormap_type = raw[1]
    data_offset = 18 + id_length

    if colormap_type == 1:
        # Skip colormap: first_entry(2) + length(2) + entry_size(1)
        cmap_first = struct.unpack_from("<h", raw, 3)[0]
        cmap_length = struct.unpack_from("<h", raw, 5)[0]
        cmap_size = raw[7]
        data_offset += cmap_length * (cmap_size // 8)

    pixel_data = raw[data_offset:]

    if image_type == 2:
        # Uncompressed RGB/RGBA
        return _decode_tga_uncompressed(
            pixel_data, width, height, channels, top_down
        )
    elif image_type == 10:
        # RLE-compressed
        return _decode_tga_rle(
            pixel_data, width, height, channels, top_down
        )
    else:
        raise ValueError(f"Unsupported TGA image type: {image_type}")


def _decode_tga_uncompressed(
    data: bytes, width: int, height: int, channels: int, top_down: bool
) -> TextureData:
    """Decode uncompressed TGA pixel data (BGRA order → RGBA)."""
    stride = width * channels
    expected = stride * height
    if len(data) < expected:
        raise ValueError(f"TGA truncated: expected {expected} bytes, got {len(data)}")

    out = bytearray(width * height * 4)

    for y in range(height):
        dst_y = y if top_down else (height - 1 - y)
        row_offset = y * stride
        dst_offset_base = dst_y * width * 4

        for x in range(width):
            src_offset = row_offset + x * channels
            dst_offset = dst_offset_base + x * 4

            b = data[src_offset]
            g = data[src_offset + 1]
            r = data[src_offset + 2]
            a = data[src_offset + 3] if channels == 4 else 255

            out[dst_offset] = r
            out[dst_offset + 1] = g
            out[dst_offset + 2] = b
            out[dst_offset + 3] = a

    return TextureData(width=width, height=height, channels=4, data=bytes(out))


def _decode_tga_rle(
    data: bytes, width: int, height: int, channels: int, top_down: bool
) -> TextureData:
    """Decode RLE-compressed TGA pixel data."""
    out = bytearray(width * height * 4)
    src_pos = 0
    total_pixels = width * height
    pixel_buf = bytearray(channels)

    for pixel_idx in range(total_pixels):
        if src_pos >= len(data):
            raise ValueError("TGA RLE: unexpected end of data")

        header = data[src_pos]
        src_pos += 1
        is_rle = header & 0x80
        count = (header & 0x7F) + 1

        if is_rle:
            # Repeated pixel
            if src_pos + channels > len(data):
                raise ValueError("TGA RLE: unexpected end of data")
            for c in range(channels):
                pixel_buf[c] = data[src_pos]
                src_pos += 1
            b = pixel_buf[0]
            g = pixel_buf[1]
            r = pixel_buf[2]
            a = pixel_buf[3] if channels == 4 else 255
        else:
            # Raw pixels
            pass

        for _ in range(count):
            if pixel_idx >= total_pixels:
                break

            if not is_rle:
                if src_pos + channels > len(data):
                    raise ValueError("TGA RLE: unexpected end of data")
                b = data[src_pos]
                g = data[src_pos + 1]
                r = data[src_pos + 2]
                a = data[src_pos + 3] if channels == 4 else 255
                src_pos += channels

            y = pixel_idx // width
            x = pixel_idx % width
            dst_y = y if top_down else (height - 1 - y)
            dst_offset = (dst_y * width + x) * 4

            out[dst_offset] = r
            out[dst_offset + 1] = g
            out[dst_offset + 2] = b
            out[dst_offset + 3] = a

            pixel_idx += 1

        pixel_idx -= 1  # compensate for loop increment

    # Actually redo more carefully:
    # Let me just use a simpler approach
    return _decode_tga_rle_safe(data, width, height, channels, top_down)


def _decode_tga_rle_safe(
    data: bytes, width: int, height: int, channels: int, top_down: bool
) -> TextureData:
    """Safer RLE TGA decoder using index-based approach."""
    out = bytearray(width * height * 4)
    src_pos = 0
    dst_pos = 0

    while dst_pos < len(out):
        if src_pos >= len(data):
            raise ValueError("TGA RLE: unexpected end of data")

        header = data[src_pos]
        src_pos += 1
        is_rle = header & 0x80
        count = (header & 0x7F) + 1

        if is_rle:
            # Read one pixel and repeat
            if src_pos + channels > len(data):
                raise ValueError("TGA RLE: unexpected end of data")
            b = data[src_pos]
            g = data[src_pos + 1]
            r = data[src_pos + 2]
            a = data[src_pos + 3] if channels == 4 else 255
            src_pos += channels

            for _ in range(count):
                if dst_pos >= len(out):
                    break
                out[dst_pos] = r
                out[dst_pos + 1] = g
                out[dst_pos + 2] = b
                out[dst_pos + 3] = a
                dst_pos += 4
        else:
            # Raw pixels
            for _ in range(count):
                if dst_pos >= len(out) or src_pos + channels > len(data):
                    break
                b = data[src_pos]
                g = data[src_pos + 1]
                r = data[src_pos + 2]
                a = data[src_pos + 3] if channels == 4 else 255
                src_pos += channels
                out[dst_pos] = r
                out[dst_pos + 1] = g
                out[dst_pos + 2] = b
                out[dst_pos + 3] = a
                dst_pos += 4

    # If the TGA is bottom-up, flip the entire image
    if not top_down:
        row_size = width * 4
        flipped = bytearray(len(out))
        for y in range(height):
            src_start = y * row_size
            dst_start = (height - 1 - y) * row_size
            flipped[dst_start:dst_start + row_size] = out[src_start:src_start + row_size]
        out = flipped

    return TextureData(width=width, height=height, channels=4, data=bytes(out))


# ======================================================================
# DDS decoder (via Pillow)
# ======================================================================
# Reference: C# OZDReader.cs / TS ozg-cryptor.ts decodeOzd()
#
# DDS header is 128 bytes. Pixel format string at offset 84.
# For MU Online, DDS in OZD files is encrypted with ModulusCryptor.
# For standalone .dds files, no decryption needed.


def _decode_dds(raw: bytes) -> TextureData:
    """Decode a DDS file using Pillow.

    Args:
        raw: Complete DDS file bytes.

    Returns:
        TextureData in RGBA format.

    Raises:
        ValueError: On invalid format.
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow is required for DDS decoding: pip install Pillow")

    if len(raw) < 128:
        raise ValueError("DDS file too small")

    # Check DDS magic
    if raw[:4] != b"DDS ":
        raise ValueError("Invalid DDS magic")

    try:
        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGBA")
        width, height = img.size
        data = img.tobytes("raw", "RGBA")
        return TextureData(width=width, height=height, channels=4, data=data)
    except Exception as e:
        raise ValueError(f"Failed to decode DDS: {e}")


# ======================================================================
# JPEG / PNG decoders (via Pillow)
# ======================================================================


def _decode_jpg(raw: bytes) -> TextureData:
    """Decode a JPEG file.

    Args:
        raw: Complete JPEG file bytes.

    Returns:
        TextureData in RGBA format.
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow is required for JPEG decoding: pip install Pillow")

    img = Image.open(io.BytesIO(raw))
    img = img.convert("RGBA")
    width, height = img.size
    data = img.tobytes("raw", "RGBA")
    return TextureData(width=width, height=height, channels=4, data=data)


def _decode_png(raw: bytes) -> TextureData:
    """Decode a PNG file.

    Args:
        raw: Complete PNG file bytes.

    Returns:
        TextureData in RGBA format.
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow is required for PNG decoding: pip install Pillow")

    img = Image.open(io.BytesIO(raw))
    img = img.convert("RGBA")
    width, height = img.size
    data = img.tobytes("raw", "RGBA")
    return TextureData(width=width, height=height, channels=4, data=data)
