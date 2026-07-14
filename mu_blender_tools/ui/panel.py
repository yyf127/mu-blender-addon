# MU Online Blender Tools - Panel
#
# Defines the shared import-settings PropertyGroup and the 3D View
# sidebar panel.
#
# This file contains ONLY UI code — no business logic.

from __future__ import annotations

import bpy
from bpy.types import Panel, PropertyGroup
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    PointerProperty,
    StringProperty,
)


# ======================================================================
# Shared import settings
# ======================================================================


class MUImportSettings(PropertyGroup):
    """Global import settings used by all MU Online import operators.

    Stored in ``context.scene.mu_import``.
    """

    scale: FloatProperty(
        name="Scale",
        description="Global scale factor applied to imported assets",
        default=1.0,
        min=0.001,
        max=1000.0,
        soft_min=0.01,
        soft_max=100.0,
        precision=3,
    )  # type: ignore

    up_axis: EnumProperty(
        name="Up Axis",
        description="Coordinate system up-axis for imported assets",
        items=[
            ("Z", "Z-Up", "MU Online native coordinate system (Z up)"),
            ("Y", "Y-Up", "Blender native coordinate system (Y up)"),
            ("-Z", "-Z Up", "Inverted Z axis"),
            ("-Y", "-Y Up", "Inverted Y axis"),
        ],
        default="Z",
    )  # type: ignore

    import_texture: BoolProperty(
        name="Import Textures",
        description="Load and assign texture files (.ozj, .ozt, .jpg, .png)",
        default=True,
    )  # type: ignore

    import_material: BoolProperty(
        name="Import Materials",
        description="Create Blender materials with Principled BSDF and image textures",
        default=True,
    )  # type: ignore

    import_armature: BoolProperty(
        name="Import Armature",
        description="Build armature (skeleton) for skinned BMD models",
        default=True,
    )  # type: ignore

    import_animation: BoolProperty(
        name="Import Animations",
        description="Import animation actions from BMD action data",
        default=True,
    )  # type: ignore

    debug: BoolProperty(
        name="Debug Logging",
        description="Enable verbose debug output to the console",
        default=False,
    )  # type: ignore

    data_folder: StringProperty(
        name="Data Folder",
        description="Path to the MU Online Data directory (for texture/material resolution)",
        subtype="DIR_PATH",
        default="",
    )  # type: ignore

    chunk_terrain: BoolProperty(
        name="Chunk Terrain",
        description="Split large terrain meshes into 8×8 manageable chunks",
        default=True,
    )  # type: ignore


# ======================================================================
# 3D View Sidebar Panel
# ======================================================================


class MU_PT_import_panel(Panel):
    """MU Online import settings panel in the 3D View sidebar."""

    bl_label = "MU Online"
    bl_idname = "MU_PT_import_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MU"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        settings = context.scene.mu_import  # type: ignore[attr-defined]

        # ── Import actions ─────────────────────────────────────────
        box = layout.box()
        box.label(text="Import", icon="IMPORT")
        col = box.column(align=True)
        col.scale_y = 1.4

        op = col.operator("mu.import_model", text="MU Model (.bmd)")
        op.scale = settings.scale
        op.import_texture = settings.import_texture
        op.import_material = settings.import_material
        op.import_armature = settings.import_armature
        op.import_animation = settings.import_animation

        op = col.operator("mu.import_terrain", text="MU Terrain (.att/.map/.ozb)")
        op.scale = settings.scale
        op.chunk_terrain = settings.chunk_terrain

        op = col.operator("mu.import_world", text="MU World (.att/.map/.ozb/.obj)")
        op.import_terrain = True
        op.import_objects = True
        op.chunk_terrain = settings.chunk_terrain

        # ── Settings ───────────────────────────────────────────────
        box = layout.box()
        box.label(text="Settings", icon="SETTINGS")
        box.prop(settings, "scale")
        box.prop(settings, "up_axis")

        col = box.column(align=True)
        col.prop(settings, "import_texture")
        col.prop(settings, "import_material")
        col.prop(settings, "import_armature")
        col.prop(settings, "import_animation")
        col.prop(settings, "chunk_terrain")

        box = layout.box()
        box.label(text="Advanced", icon="SETTINGS")
        box.prop(settings, "data_folder")
        box.prop(settings, "debug")


# ======================================================================
# Registration helpers
# ======================================================================

classes = (
    MUImportSettings,
    MU_PT_import_panel,
)


def register() -> None:
    """Register property group and panel."""
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mu_import = PointerProperty(type=MUImportSettings)  # type: ignore[attr-defined]


def unregister() -> None:
    """Unregister panel and property group."""
    del bpy.types.Scene.mu_import  # type: ignore[attr-defined]
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
