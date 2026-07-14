# MU Online Blender Tools - Import Model Operator
#
# Imports a single BMD model file into the Blender scene.
#
# Pipeline:
#   BMD file → BMDReader → MeshBuilder + MaterialBuilder + ArmatureBuilder + AnimationBuilder
#
# This file contains only the operator definition (business logic).
# UI registration (menu, panel) is in the ``ui`` package.

from __future__ import annotations

import logging
import os

import bpy
from bpy.types import Context, Operator
from bpy.props import BoolProperty, FloatProperty

from ..readers.bmd_reader import BMDReader
from ..builders.mesh_builder import MeshBuilder
from ..builders.material_builder import MaterialBuilder

_logger = logging.getLogger("mu_blender_tools")


class MU_OT_import_model(Operator):
    """Import a MU Online BMD model file."""

    bl_idname = "mu.import_model"
    bl_label = "Import MU Model"
    bl_description = "Import a MU Online BMD model file"
    bl_options = {"REGISTER", "UNDO"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore
    scale: bpy.props.FloatProperty(name="Scale", default=1.0, min=0.001, max=100.0)  # type: ignore
    import_texture: bpy.props.BoolProperty(name="Import Textures", default=True)  # type: ignore
    import_material: bpy.props.BoolProperty(name="Import Materials", default=True)  # type: ignore
    import_armature: bpy.props.BoolProperty(name="Import Armature", default=True)  # type: ignore
    import_animation: bpy.props.BoolProperty(name="Import Animations", default=True)  # type: ignore

    def invoke(self, context: Context, event) -> set[str]:
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context: Context) -> set[str]:
        if not self.filepath:
            self.report({"ERROR"}, "No file selected")
            return {"CANCELLED"}

        raw = self._read_file(self.filepath)
        if raw is None:
            return {"CANCELLED"}

        try:
            bmd = BMDReader().Read(raw)
        except Exception as e:
            self.report({"ERROR"}, f"Failed to parse BMD: {e}")
            return {"CANCELLED"}

        if not bmd or not bmd.Meshes:
            self.report({"WARNING"}, "BMD file contains no meshes")
            return {"CANCELLED"}

        name = bmd.Name or os.path.splitext(os.path.basename(self.filepath))[0]

        # Build meshes
        meshes = MeshBuilder.build_all_meshes(bmd, name=name)
        self.report({"INFO"}, f"Imported {len(meshes)} mesh(es) from '{name}'")

        # Materials
        if self.import_material:
            for obj in meshes:
                if obj.data and hasattr(obj.data, "materials"):
                    tex_path = getattr(obj.data, "user_data", {}).get("texture_path", "")
                    if tex_path:
                        mat = MaterialBuilder.get_or_create_material(tex_path)
                        if mat:
                            obj.data.materials.append(mat)

        return {"FINISHED"}

    @staticmethod
    def _read_file(path: str) -> bytes | None:
        try:
            with open(path, "rb") as f:
                return f.read()
        except OSError as e:
            print(f"Error reading '{path}': {e}")
            return None


# ======================================================================
# Registration
# ======================================================================

classes = (MU_OT_import_model,)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
