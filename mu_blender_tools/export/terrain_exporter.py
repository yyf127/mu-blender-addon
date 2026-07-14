# MU Online Blender Tools - Terrain Exporter (stub)
#
# Exports terrain data back to ATT / MAP / OZB / OBJ binary formats.
#
# TODO: Implement ATTSerializer, MAPSerializer, OZBSerializer, OBJSerializer.

from __future__ import annotations

from typing import Any, Optional

from .base_exporter import BaseExporter
from .base_serializer import BaseSerializer
from .base_writer import BaseWriter


# ── ATT Serializer ────────────────────────────────────────────────


class ATTSerializer(BaseSerializer):
    """Stub: serializes TerrainAttributeData to .att bytes."""

    def serialize(self, data: Any) -> bytes:
        raise NotImplementedError("ATTSerializer not yet implemented")

    @property
    def file_extension(self) -> str:
        return ".att"

    @property
    def format_name(self) -> str:
        return "MU Online Terrain Attribute"


# ── MAP Serializer ────────────────────────────────────────────────


class MAPSerializer(BaseSerializer):
    """Stub: serializes TerrainMappingData to .map bytes."""

    def serialize(self, data: Any) -> bytes:
        raise NotImplementedError("MAPSerializer not yet implemented")

    @property
    def file_extension(self) -> str:
        return ".map"

    @property
    def format_name(self) -> str:
        return "MU Online Terrain Mapping"


# ── OZB Serializer ────────────────────────────────────────────────


class OZBSerializer(BaseSerializer):
    """Stub: serializes OZBData to .ozb bytes."""

    def serialize(self, data: Any) -> bytes:
        raise NotImplementedError("OZBSerializer not yet implemented")

    @property
    def file_extension(self) -> str:
        return ".ozb"

    @property
    def format_name(self) -> str:
        return "MU Online Terrain Height/Light"


# ── OBJ Serializer ────────────────────────────────────────────────


class OBJSerializer(BaseSerializer):
    """Stub: serializes OBJData to .obj bytes (reverse of OBJReader)."""

    def serialize(self, data: Any) -> bytes:
        raise NotImplementedError("OBJSerializer not yet implemented")

    @property
    def file_extension(self) -> str:
        return ".obj"

    @property
    def format_name(self) -> str:
        return "MU Online Object Placement"


# ── Terrain Exporter ──────────────────────────────────────────────


class TerrainExporter(BaseExporter):
    """Exporter for terrain files (.att, .map, .ozb, .obj).

    Can export individual component files or all at once.
    """

    def __init__(
        self,
        att_serializer: Optional[BaseSerializer] = None,
        map_serializer: Optional[BaseSerializer] = None,
        ozb_serializer: Optional[BaseSerializer] = None,
        obj_serializer: Optional[BaseSerializer] = None,
        writer: Optional[BaseWriter] = None,
    ) -> None:
        self.serializers = {
            ".att": att_serializer or ATTSerializer(),
            ".map": map_serializer or MAPSerializer(),
            ".ozb": ozb_serializer or OZBSerializer(),
            ".obj": obj_serializer or OBJSerializer(),
        }
        self.writer = writer

    def export(self, data: Any, path: str) -> None:
        if self.writer is None:
            raise ValueError("Writer not set — cannot export")
        ext = self._detect_extension(path)
        ser = self.serializers.get(ext)
        if ser is None:
            raise ValueError(f"No serializer for extension '{ext}'")
        if not self.validate(data):
            raise ValueError("Invalid terrain data")
        raw = ser.serialize(data)
        self.writer.write(raw, path)

    def validate(self, data: Any) -> bool:
        return data is not None

    @property
    def export_name(self) -> str:
        return "Export MU Terrain"

    @property
    def file_extensions(self) -> list[str]:
        return [".att", ".map", ".ozb", ".obj"]

    @staticmethod
    def _detect_extension(path: str) -> str:
        import os
        _, ext = os.path.splitext(path)
        return ext.lower()
