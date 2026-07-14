# MU Online Blender Tools - Menu
#
# Registers File > Import menu entries for all MU Online import operators.
#
# This file contains ONLY UI code — no business logic.

from __future__ import annotations

import bpy
from bpy.types import Context


# ======================================================================
# Import menu callbacks
# ======================================================================


def menu_import_model(self, context: Context) -> None:
    """Add 'MU Model (.bmd)' to File > Import."""
    settings = context.scene.mu_import  # type: ignore[attr-defined]
    op = self.layout.operator("mu.import_model", text="MU Online Model (.bmd)")
    op.scale = settings.scale
    op.import_texture = settings.import_texture
    op.import_material = settings.import_material
    op.import_armature = settings.import_armature
    op.import_animation = settings.import_animation


def menu_import_terrain(self, context: Context) -> None:
    """Add 'MU Terrain (.att/.map/.ozb)' to File > Import."""
    settings = context.scene.mu_import  # type: ignore[attr-defined]
    op = self.layout.operator("mu.import_terrain", text="MU Online Terrain (.att/.map/.ozb)")
    op.scale = settings.scale
    op.chunk_terrain = settings.chunk_terrain


def menu_import_world(self, context: Context) -> None:
    """Add 'MU World' to File > Import."""
    settings = context.scene.mu_import  # type: ignore[attr-defined]
    op = self.layout.operator("mu.import_world", text="MU Online World (.att/.map/.ozb/.obj)")
    op.directory = settings.data_folder
    op.import_terrain = True
    op.import_objects = True
    op.chunk_terrain = settings.chunk_terrain


# ======================================================================
# Registration
# ======================================================================


def register() -> None:
    """Register all menu entries under File > Import."""
    bpy.types.TOPBAR_MT_file_import.append(menu_import_model)
    bpy.types.TOPBAR_MT_file_import.append(menu_import_terrain)
    bpy.types.TOPBAR_MT_file_import.append(menu_import_world)


def unregister() -> None:
    """Unregister all menu entries."""
    bpy.types.TOPBAR_MT_file_import.remove(menu_import_world)
    bpy.types.TOPBAR_MT_file_import.remove(menu_import_terrain)
    bpy.types.TOPBAR_MT_file_import.remove(menu_import_model)
