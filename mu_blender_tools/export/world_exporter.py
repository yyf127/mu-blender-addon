# MU Online Blender Tools - World Exporter (stub)
#
# Exports a complete world: terrain files + object placement + metadata.
#
# TODO: Implement world-level serialization that combines
#       ATT, MAP, OZB, and OBJ serializers.

from __future__ import annotations

from typing import Any, Optional

from .base_exporter import BaseExporter
from .base_serializer import BaseSerializer
from .base_writer import BaseWriter


class WorldExporter(BaseExporter):
    """Exporter for a complete MU Online world (all terrain + objects).

    Delegates to individual terrain serializers for each component
    file.
    """

    def __init__(
        self,
        terrain_exporter: Optional[BaseExporter] = None,
        writer: Optional[BaseWriter] = None,
    ) -> None:
        # Import here to avoid circular dependency at package level
        from .terrain_exporter import TerrainExporter
        self._terrain_exporter = terrain_exporter or TerrainExporter()
        self.writer = writer

    def export(self, data: Any, path: str) -> None:
        """Export a full world.

        ``data`` is expected to be a dict-like object with keys
        ``att``, ``map``, ``height``, ``light``, ``obj``, each
        containing the corresponding reader dataclass.
        """
        if self.writer is None:
            raise ValueError("Writer not set — cannot export")
        if not self.validate(data):
            raise ValueError("Invalid world data")

        # Export each component to its file
        import os

        base_dir = os.path.dirname(path)

        components = [
            ("att", ".att"),
            ("map", ".map"),
            ("height", ".ozb"),
            ("light", ".ozb"),
            ("obj", ".obj"),
        ]

        for key, ext in components:
            component_data = getattr(data, key, None) if hasattr(data, key) else data.get(key)
            if component_data is None:
                continue
            comp_path = os.path.join(base_dir, f"{key}{ext}")
            self._terrain_exporter.export(component_data, comp_path)

    def validate(self, data: Any) -> bool:
        return data is not None

    @property
    def export_name(self) -> str:
        return "Export MU World"

    @property
    def file_extensions(self) -> list[str]:
        return [".att", ".map", ".ozb", ".obj"]
