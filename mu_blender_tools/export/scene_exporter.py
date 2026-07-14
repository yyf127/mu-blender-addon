# MU Online Blender Tools - Scene Exporter (stub)
#
# Exports the current Blender scene (or selected objects) back to
# MU Online game formats.
#
# This is the highest-level exporter — it reads Blender data and
# dispatches to the appropriate format exporters.
#
# TODO: Implement Blender → reader-dataclass conversion for each
#       supported format.

from __future__ import annotations

from typing import Any, Optional

from .base_exporter import BaseExporter
from .base_writer import BaseWriter


class SceneExporter(BaseExporter):
    """Exporter for a full Blender scene → all MU Online formats."""

    def __init__(
        self,
        world_exporter: Optional[BaseExporter] = None,
        bmd_exporter: Optional[BaseExporter] = None,
        writer: Optional[BaseWriter] = None,
    ) -> None:
        from .world_exporter import WorldExporter
        from .bmd_exporter import BMDExporter
        self._world_exporter = world_exporter or WorldExporter()
        self._bmd_exporter = bmd_exporter or BMDExporter()
        self.writer = writer

    def export(self, data: Any, path: str) -> None:
        """Export the current scene.

        ``data`` is expected to be a ``bpy.types.Scene`` or a
        dict of export-ready dataclasses.
        """
        if self.writer is None:
            raise ValueError("Writer not set — cannot export")
        if not self.validate(data):
            raise ValueError("Invalid scene data")

        # Dispatch based on data type
        if hasattr(data, "objects"):
            # Blender Scene — traverse and export each supported type
            self._export_scene_objects(data)
        elif isinstance(data, dict):
            # Pre-packaged dict — export all components
            for fmt, fmt_data in data.items():
                self._export_format(fmt, fmt_data, path)
        else:
            raise TypeError(f"Unsupported data type: {type(data).__name__}")

    def validate(self, data: Any) -> bool:
        return data is not None

    @property
    def export_name(self) -> str:
        return "Export MU Scene"

    @property
    def file_extensions(self) -> list[str]:
        return [".bmd", ".att", ".map", ".ozb", ".obj"]

    def _export_scene_objects(self, scene: Any) -> None:
        """Walk a Blender scene and export each MU-related object."""
        raise NotImplementedError("Scene walking not yet implemented")

    def _export_format(self, fmt: str, data: Any, path: str) -> None:
        """Route to the correct format exporter."""
        bmd_exts = {".bmd"}
        terrain_exts = {".att", ".map", ".ozb", ".obj"}

        if fmt in bmd_exts:
            self._bmd_exporter.export(data, path)
        elif fmt in terrain_exts:
            self._world_exporter.export(data, path)
        else:
            raise ValueError(f"Unsupported format: {fmt}")
