# MU Online Blender Tools - Exporter Interface
#
# An Exporter is the top-level orchestrator.  It:
#   1. Collects / converts data from readers or Blender scene
#   2. Passes data to a Serializer
#   3. Passes serialized bytes to a Writer
#
# Each concrete Exporter knows which Serializer + Writer to use.

from __future__ import annotations

import abc
from typing import Any, Optional

from .base_serializer import BaseSerializer
from .base_writer import BaseWriter


class BaseExporter(abc.ABC):
    """Abstract interface for a complete export pipeline."""

    # ── Components (set by subclass or at runtime) ────────────────

    serializer: Optional[BaseSerializer] = None
    """The serializer used to convert in-memory data to bytes."""

    writer: Optional[BaseWriter] = None
    """The writer used to persist bytes to a file."""

    # ── Public API ────────────────────────────────────────────────

    @abc.abstractmethod
    def export(self, data: Any, path: str) -> None:
        """Run the full export pipeline.

        1. Validate *data*.
        2. Serialize via ``self.serializer.serialize(data)``.
        3. Write via ``self.writer.write(serialized_bytes, path)``.

        Args:
            data: The in-memory data to export (type varies by exporter).
            path: Destination file path.

        Raises:
            ValueError: If *data* is invalid or components are missing.
            OSError: On write failure.
        """
        ...

    @abc.abstractmethod
    def validate(self, data: Any) -> bool:
        """Check whether *data* can be exported by this exporter.

        Args:
            data: Candidate export data.

        Returns:
            True if *data* is valid for export.
        """
        ...

    @property
    @abc.abstractmethod
    def export_name(self) -> str:
        """Human-readable name, e.g. ``Export BMD Model``."""
        ...

    @property
    @abc.abstractmethod
    def file_extensions(self) -> list[str]:
        """Accepted file extensions, e.g. ``[".bmd"]``."""
        ...
