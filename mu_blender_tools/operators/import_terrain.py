# MU Online Blender Tools - Import Terrain Operator
#
# Imports MU Online terrain files (ATT + MAP + OZB) and builds a terrain mesh.
#
# This file contains only the operator definition (business logic).
# UI registration (menu, panel) is in the ``ui`` package.

from __future__ import annotations

import logging
import os

import bpy
from bpy.types import Context, Operator
from bpy.props import BoolProperty, FloatProperty, StringProperty

from ..readers.terrain_reader import (
    TERRAIN_SIZE,
    read_att,
    read_map,
    read_ozb,
)
from ..builders.terrain_builder import build_terrain_mesh
from ..builders.world_builder import WorldBuilder

_logger = logging.getLogger("mu_blender_tools")


class MU_OT_import_terrain(Operator):
    """Import MU Online terrain from ATT, MAP and OZB files."""

    bl_idname = "mu.import_terrain"
    bl_label = "Import MU Terrain"
    bl_description = "Import a MU Online terrain (ATT + MAP + OZB)"
    bl_options = {"REGISTER", "UNDO"}

    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    scale: FloatProperty(name="Scale", default=1.0, min=0.001, max=100.0)  # type: ignore
    chunk_terrain: BoolProperty(name="Chunk Terrain", default=True)  # type: ignore

    def invoke(self, context: Context, event) -> set[str]:
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context: Context) -> set[str]:
        data_dir = self.directory
        if not data_dir or not os.path.isdir(data_dir):
            self.report({"ERROR"}, "Invalid directory")
            return {"CANCELLED"}

        # Walk the directory for terrain files
        att_data = map_data = height_data = light_data = None

        for f in os.listdir(data_dir):
            lower = f.lower()
            path = os.path.join(data_dir, f)

            if lower.endswith(".att"):
                try:
                    with open(path, "rb") as fp:
                        att_data = read_att(fp.read())
                except Exception as e:
                    self.report({"WARNING"}, f"ATT error: {e}")

            elif lower.endswith(".map"):
                try:
                    with open(path, "rb") as fp:
                        map_data = read_map(fp.read())
                except Exception as e:
                    self.report({"WARNING"}, f"MAP error: {e}")

            elif "height" in lower and lower.endswith(".ozb"):
                try:
                    with open(path, "rb") as fp:
                        height_data = read_ozb(fp.read())
                except Exception as e:
                    self.report({"WARNING"}, f"Height OZB error: {e}")

            elif "light" in lower and lower.endswith(".ozb"):
                try:
                    with open(path, "rb") as fp:
                        light_data = read_ozb(fp.read())
                except Exception as e:
                    self.report({"WARNING"}, f"Light OZB error: {e}")

        if not height_data:
            self.report({"ERROR"}, "No heightmap (TerrainHeight.OZB) found")
            return {"CANCELLED"}

        # Build terrain mesh
        chunk_size = 8 if self.chunk_terrain else TERRAIN_SIZE
        terrain = build_terrain_mesh(
            att_data=att_data,
            map_data=map_data,
            height_data=height_data,
            light_data=light_data,
            chunk_size=chunk_size,
        )

        # Build the scene
        from ..readers.world_reader import WorldData
        wd = WorldData(map_number=0)
        wb = WorldBuilder(wd, terrain_output=terrain)
        wb.build()

        self.report({"INFO"}, f"Terrain imported: {len(terrain.chunks)} chunks")
        return {"FINISHED"}


# ======================================================================
# Registration
# ======================================================================

classes = (MU_OT_import_terrain,)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
