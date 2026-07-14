# MU Online Blender Tools - Unified Exception Hierarchy
#
# All custom exceptions used by the addon inherit from
# ``MuBlenderError``.  This lets callers catch a single base type
# while still distinguishing error categories.

from __future__ import annotations


class MuBlenderError(Exception):
    """Base exception for all MU Blender Tools errors."""


# ── Reader errors ────────────────────────────────────────────────


class ReaderError(MuBlenderError):
    """Base class for data-read errors."""


class BinaryReaderError(ReaderError):
    """Binary stream read error (e.g. unexpected EOF, invalid format)."""


class BMDParseError(ReaderError):
    """BMD file parse error."""


class TerrainParseError(ReaderError):
    """Terrain file parse error (ATT / MAP / OZB / OBJ)."""


class WorldParseError(ReaderError):
    """World data parse error."""


class TextureError(MuBlenderError):
    """Texture load / decode error."""


# ── Builder errors ───────────────────────────────────────────────


class BuilderError(MuBlenderError):
    """Base class for builder errors."""


class MeshBuildError(BuilderError):
    """Mesh construction error."""


class MaterialBuildError(BuilderError):
    """Material construction error."""


class ArmatureBuildError(BuilderError):
    """Armature construction error."""


class AnimationBuildError(BuilderError):
    """Animation construction error."""


class TerrainBuildError(BuilderError):
    """Terrain mesh construction error."""


# ── Export errors ────────────────────────────────────────────────


class ExportError(MuBlenderError):
    """Base class for export errors."""


class SerializeError(ExportError):
    """Data serialization error."""


class WriteError(ExportError):
    """File write error."""


# ── Import / operator errors ─────────────────────────────────────


class ImportError(MuBlenderError):
    """Import operation error."""


# ── Configuration errors ─────────────────────────────────────────


class ConfigurationError(MuBlenderError):
    """Addon configuration error (e.g. missing Data directory)."""
