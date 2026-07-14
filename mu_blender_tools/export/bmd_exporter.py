# MU Online Blender Tools - BMD Exporter (stub)
#
# Exports in-memory BMD data back to the .bmd binary format.
#
# TODO: Implement BMDSerializer (reverse of BMDReader).

from __future__ import annotations

from typing import Any, Optional

from .base_exporter import BaseExporter
from .base_serializer import BaseSerializer
from .base_writer import BaseWriter

# Forward reference — will be implemented in a later phase
# from ..readers.bmd_types import BMD


class BMDSerializer(BaseSerializer):
    """Stub: serializes BMD data back to .bmd bytes.

    To be implemented in a later phase.
    """

    def serialize(self, data: Any) -> bytes:
        raise NotImplementedError("BMDSerializer not yet implemented")

    @property
    def file_extension(self) -> str:
        return ".bmd"

    @property
    def format_name(self) -> str:
        return "MU Online BMD Model"


class BMDExporter(BaseExporter):
    """Exporter for .bmd model files."""

    def __init__(
        self,
        serializer: Optional[BaseSerializer] = None,
        writer: Optional[BaseWriter] = None,
    ) -> None:
        self.serializer = serializer or BMDSerializer()
        self.writer = writer

    def export(self, data: Any, path: str) -> None:
        if self.writer is None:
            raise ValueError("Writer not set — cannot export")
        if not self.validate(data):
            raise ValueError("Invalid BMD data")
        raw = self.serializer.serialize(data)
        self.writer.write(raw, path)

    def validate(self, data: Any) -> bool:
        # TODO: check isinstance(data, BMD)
        return data is not None

    @property
    def export_name(self) -> str:
        return "Export BMD Model"

    @property
    def file_extensions(self) -> list[str]:
        return [".bmd"]
