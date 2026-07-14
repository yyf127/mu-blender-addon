# MU Online Blender Tools - Scene Importer
#
# Integrates the full terrain-to-scene pipeline into a single Blender
# operator, accessible via File > Import > Import MU World.
#
# Pipeline:
#   Select Data directory
#   → Scan for available worlds
#   → Pick world index
#   → Read ATT / MAP / OZB (height + light) / OBJ
#   → Build terrain mesh (via TerrainBuilder)
#   → Build world data (via WorldReader)
#   → Build Blender scene (via WorldBuilder)
#   → Import BMD objects (via BMDReader + MeshBuilder + MaterialBuilder)

from __future__ import annotations

import logging
import os
import pathlib
from typing import Any, Optional

import bpy
from bpy.types import Collection, Context, Mesh, Object, Operator
from bpy.props import BoolProperty, IntProperty, StringProperty

# ── MU Online readers ─────────────────────────────────────────────
from ..readers.binary_reader import BinaryReaderError
from ..readers.bmd_reader import BMDReader
from ..readers.terrain_reader import (
    OZBData,
    read_att,
    read_map,
    read_ozb,
    read_obj,
)
from ..readers.world_reader import read_world

# ── MU Online builders ────────────────────────────────────────────
from ..builders.terrain_builder import (
    TERRAIN_SIZE,
    build_terrain_mesh,
)
from ..builders.world_builder import WorldBuilder, BMDLoaderFn
from ..builders.mesh_builder import MeshBuilder
from ..builders.material_builder import MaterialBuilder

_logger = logging.getLogger("mu_blender_tools")


# ======================================================================
# Constants
# ======================================================================

# Naming pattern for terrain files inside a world folder
ENCTERRAIN_ATT: str = "EncTerrain{}.att"
ENCTERRAIN_MAP: str = "EncTerrain{}.map"
ENCTERRAIN_OBJ: str = "EncTerrain{}.obj"
TERRAIN_HEIGHT: str = "TerrainHeight.OZB"
TERRAIN_LIGHT: str = "TerrainLight.OZB"

# Subdirectory names (the reference uses both `WorldN` and `worldN`)
WORLD_DIR_PREFIXES: list[str] = ["World", "world"]
OBJECT_DIR_PREFIXES: list[str] = ["Object", "object"]


# ======================================================================
# File-discovery helpers
# ======================================================================


def _scan_available_worlds(data_dir: str) -> list[int]:
    """Scan the Data directory for available world numbers.

    Looks for folders named ``World{N}`` or ``world{N}``.

    Args:
        data_dir: Absolute path to the MU Online Data directory.

    Returns:
        Sorted list of available world numbers.
    """
    worlds: set[int] = set()
    try:
        for entry in os.scandir(data_dir):
            if entry.is_dir():
                for prefix in WORLD_DIR_PREFIXES:
                    if entry.name.startswith(prefix):
                        suffix = entry.name[len(prefix):]
                        if suffix.isdigit():
                            worlds.add(int(suffix))
    except PermissionError:
        pass
    return sorted(worlds)


def _find_file(data_dir: str, world_num: int, *names: str) -> Optional[str]:
    """Search for a terrain file in ``World{N}`` / ``world{N}`` folders.

    Tries multiple naming conventions and returns the first existing path.

    Args:
        data_dir: Data root directory.
        world_num: World index.
        *names: Candidate file names.

    Returns:
        Full path to the first existing file, or None.
    """
    for prefix in WORLD_DIR_PREFIXES:
        world_dir = os.path.join(data_dir, f"{prefix}{world_num}")
        if os.path.isdir(world_dir):
            for name in names:
                path = os.path.join(world_dir, name)
                if os.path.isfile(path):
                    return path
    return None


def _find_object_bmd(data_dir: str, world_num: int, model_path: str) -> Optional[str]:
    """Find a BMD model file in ``Object{N}`` / ``object{N}`` folders.

    Args:
        data_dir: Data root directory.
        world_num: World index.
        model_path: Relative model path (e.g. ``Object1/Object01.bmd``).

    Returns:
        Full path to the BMD file, or None.
    """
    # Normalise separators
    model_path = model_path.replace("\\", "/")

    for prefix in OBJECT_DIR_PREFIXES:
        obj_dir = os.path.join(data_dir, f"{prefix}{world_num}")
        if os.path.isdir(obj_dir):
            # Try the model path as-is relative to the object directory
            candidate = os.path.join(obj_dir, os.path.basename(model_path))
            if os.path.isfile(candidate):
                return candidate

    # Fallback: search the data dir for any matching filename
    basename = os.path.basename(model_path)
    for root, _dirs, files in os.walk(data_dir):
        for f in files:
            if f.lower() == basename.lower():
                return os.path.join(root, f)

    return None


def _read_file_bytes(path: str) -> Optional[bytes]:
    """Read a file as binary bytes.

    Args:
        path: Full file path.

    Returns:
        File bytes, or None on failure.
    """
    try:
        with open(path, "rb") as f:
            return f.read()
    except (OSError, PermissionError) as e:
        _logger.warning("Cannot read '%s': %s", path, e)
        return None


# ======================================================================
# BMD loader callback (for WorldBuilder)
# ======================================================================


def _make_bmd_loader(data_dir: str, world_num: int) -> BMDLoaderFn:
    """Create a BMD loader closure for ``WorldBuilder``.

    Returns a callable that, given a model path and collection, attempts
    to import the BMD file and create mesh objects inside that collection.

    Args:
        data_dir: Data root directory.
        world_num: World index.

    Returns:
        BMD loader callable.
    """
    def _bmd_loader(model_path: str, collection: Collection) -> Optional[Object]:
        """Load a single BMD model and create mesh objects.

        Creates a parent Empty to hold the model, then builds meshes,
        materials, armature, and actions underneath it.

        Args:
            model_path: Relative BMD path (e.g. ``Object1/Tree01.bmd``).
            collection: Target Blender collection.

        Returns:
            Root Empty object, or None on failure.
        """
        file_path = _find_object_bmd(data_dir, world_num, model_path)
        if file_path is None:
            _logger.debug("BMD not found: '%s'", model_path)
            return None

        raw = _read_file_bytes(file_path)
        if raw is None:
            return None

        try:
            bmd = BMDReader().Read(raw)
        except Exception as e:
            _logger.warning("BMD parse failed for '%s': %s", model_path, e)
            return None

        if bmd is None or not bmd.Meshes:
            return None

        # Build mesh objects
        meshes = MeshBuilder.build_all_meshes(bmd, name=bmd.Name, collection=collection)
        if not meshes:
            return None

        # Build materials for each mesh
        for obj in meshes:
            if obj.data and hasattr(obj.data, "materials"):
                # Get the texture path from user_data or mesh name
                tex_path = getattr(obj.data, "user_data", {}).get("texture_path", "")
                if tex_path:
                    mat = MaterialBuilder.get_or_create_material(tex_path)
                    if mat and obj.data.materials:
                        obj.data.materials.append(mat)

        # Parent all meshes under a single empty (for transform control)
        root_name = bmd.Name or os.path.splitext(os.path.basename(file_path))[0]
        root: Object = bpy.data.objects.new(root_name, None)
        root.empty_display_size = 30.0
        root.empty_display_type = "PLAIN_AXES"
        collection.objects.link(root)

        for obj in meshes:
            obj.parent = root

        return root

    return _bmd_loader


# ======================================================================
# Operator
# ======================================================================


class MU_OT_import_world(Operator):
    """Import an entire MU Online world from the game's Data directory.

    Reads terrain files (ATT, MAP, OZB, OBJ), builds the terrain mesh,
    classifies world objects, and creates a complete Blender scene with
    organised collections and placeholder empties.

    Pipeline:
        ATT → TerrainAttributeData
        MAP → TerrainMappingData
        OZB → Heightmap (+ optional Lightmap)
        OBJ → OBJData  ─┐
                        ├→ WorldReader → WorldData → WorldBuilder → Scene
        TerrainBuilder ─┘
    """

    bl_idname = "mu.import_world"
    bl_label = "Import MU World"
    bl_description = "Import an entire MU Online world from the Data directory"
    bl_options = {"REGISTER", "UNDO"}

    # ── Properties ─────────────────────────────────────────────────

    directory: StringProperty(
        name="Data Directory",
        description="MU Online Data directory containing World{N} and Object{N} folders",
        subtype="DIR_PATH",
        maxlen=1024,
    )  # type: ignore

    world_number: IntProperty(
        name="World Number",
        description="World index to import (0 = Lorencia, 1 = Dungeon, etc.)",
        default=0,
        min=0,
        max=255,
    )  # type: ignore

    import_terrain: BoolProperty(
        name="Import Terrain",
        description="Build the terrain mesh from heightmap and texture data",
        default=True,
    )  # type: ignore

    import_objects: BoolProperty(
        name="Import Objects",
        description="Import BMD models for world objects (trees, buildings, etc.)",
        default=True,
    )  # type: ignore

    chunk_terrain: BoolProperty(
        name="Chunk Terrain",
        description="Split the terrain into manageable 8×8 chunks",
        default=True,
    )  # type: ignore

    # ── Invoke ─────────────────────────────────────────────────────

    def invoke(self, context: Context, event: Any) -> set[str]:
        """Show the file browser dialog, then run."""
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context: Context) -> None:
        """Draw the operator properties panel."""
        layout = self.layout
        layout.prop(self, "world_number")

        box = layout.box()
        box.label(text="Import Options", icon="SETTINGS")
        box.prop(self, "import_terrain")
        box.prop(self, "import_objects")

        if self.import_terrain:
            box.prop(self, "chunk_terrain")

        # Show available worlds
        data_dir = self.directory
        if data_dir:
            worlds = _scan_available_worlds(data_dir)
            if worlds:
                box = layout.box()
                box.label(text=f"Available worlds: {', '.join(str(w) for w in worlds)}", icon="WORLD")

    # ── Execute ────────────────────────────────────────────────────

    def execute(self, context: Context) -> set[str]:
        """Run the full import pipeline."""
        data_dir = self.directory
        world_num = self.world_number

        if not data_dir or not os.path.isdir(data_dir):
            self.report({"ERROR"}, f"Invalid Data directory: {data_dir}")
            return {"CANCELLED"}

        wm = context.window_manager
        wm.progress_begin(0, 100)
        wm.progress_update(0)
        self.report({"INFO"}, f"Importing World {world_num} from {data_dir}...")

        try:
            # ── Stage 1: Read terrain files ────────────────────────
            self.report({"INFO"}, "Reading terrain files...")
            wm.progress_update(10)

            att_data = None
            map_data = None
            height_data = None
            light_data = None
            obj_data = None

            # ATT
            att_path = _find_file(data_dir, world_num,
                                  ENCTERRAIN_ATT.format(world_num))
            if att_path:
                raw = _read_file_bytes(att_path)
                if raw:
                    try:
                        att_data = read_att(raw)
                        self.report({"INFO"}, f"  ATT: {att_path}")
                    except BinaryReaderError as e:
                        self.report({"WARNING"}, f"  ATT parse error: {e}")

            # MAP
            map_path = _find_file(data_dir, world_num,
                                  ENCTERRAIN_MAP.format(world_num))
            if map_path:
                raw = _read_file_bytes(map_path)
                if raw:
                    try:
                        map_data = read_map(raw)
                        self.report({"INFO"}, f"  MAP: {map_path}")
                    except BinaryReaderError as e:
                        self.report({"WARNING"}, f"  MAP parse error: {e}")

            # OZB — height
            height_path = _find_file(data_dir, world_num, TERRAIN_HEIGHT)
            if height_path:
                raw = _read_file_bytes(height_path)
                if raw:
                    try:
                        height_data = read_ozb(raw)
                        self.report({"INFO"}, f"  Height: {height_path}")
                    except BinaryReaderError as e:
                        self.report({"WARNING"}, f"  Height parse error: {e}")

            # OZB — light (optional)
            light_path = _find_file(data_dir, world_num, TERRAIN_LIGHT)
            if light_path:
                raw = _read_file_bytes(light_path)
                if raw:
                    try:
                        light_data = read_ozb(raw)
                        self.report({"INFO"}, f"  Light: {light_path}")
                    except BinaryReaderError as e:
                        self.report({"WARNING"}, f"  Light parse error: {e}")

            # OBJ
            obj_path = _find_file(data_dir, world_num,
                                  ENCTERRAIN_OBJ.format(world_num))
            if obj_path:
                raw = _read_file_bytes(obj_path)
                if raw:
                    try:
                        obj_data = read_obj(raw)
                        self.report({"INFO"}, f"  OBJ: {obj_path} ({len(obj_data.objects)} objects)")
                    except BinaryReaderError as e:
                        self.report({"WARNING"}, f"  OBJ parse error: {e}")

            if not height_data:
                self.report({"ERROR"}, "Terrain height file (TerrainHeight.OZB) not found or unreadable")
                wm.progress_end()
                return {"CANCELLED"}

            wm.progress_update(30)

            # ── Stage 2: Build terrain mesh ───────────────────────
            terrain_output = None
            if self.import_terrain and att_data and map_data and height_data:
                self.report({"INFO"}, "Building terrain mesh...")
                wm.progress_update(40)

                chunk_size = 8 if self.chunk_terrain else TERRAIN_SIZE
                terrain_output = build_terrain_mesh(
                    att_data=att_data,
                    map_data=map_data,
                    height_data=height_data,
                    light_data=light_data,
                    chunk_size=chunk_size,
                )
                self.report({"INFO"}, f"  Terrain: {len(terrain_output.chunks)} chunks built")
                wm.progress_update(55)

            # ── Stage 3: Build world data ─────────────────────────
            self.report({"INFO"}, "Building world data...")
            wm.progress_update(60)

            world_data = read_world(
                obj_data=obj_data,
                att_data=att_data,
                map_data=map_data,
                height_data=height_data,
                light_data=light_data,
            ) if obj_data else None

            if world_data:
                self.report({"INFO"}, f"  World: {len(world_data.objects)} objects, "
                            f"{len(world_data.npcs)} NPCs, "
                            f"{len(world_data.monsters)} monsters")
            wm.progress_update(70)

            # ── Stage 4: Build Blender scene ──────────────────────
            self.report({"INFO"}, "Building Blender scene...")
            wm.progress_update(75)

            bmd_loader: Optional[BMDLoaderFn] = None
            if self.import_objects and world_data is not None:
                bmd_loader = _make_bmd_loader(data_dir, world_num)

            world_builder = WorldBuilder(
                world_data=world_data,
                terrain_output=terrain_output,
                bmd_loader=bmd_loader,
            )

            collections = world_builder.build()
            wm.progress_update(90)

            # ── Stage 5: Report results ───────────────────────────
            obj_count = len(world_builder.created_objects)
            col_count = len(collections)

            # Select the root collection
            if world_builder.root_collection:
                context.view_layer.active_layer_collection = (
                    context.view_layer.layer_collection
                )

            wm.progress_update(100)

            self.report(
                {"INFO"},
                f"World {world_num} imported: {obj_count} objects in {col_count} collections",
            )
            _logger.info(
                "Scene import complete: world=%d, objects=%d, collections=%d",
                world_num, obj_count, col_count,
            )
            return {"FINISHED"}

        except Exception as e:
            self.report({"ERROR"}, f"Import failed: {e}")
            _logger.exception("World import error: %s", e)
            return {"CANCELLED"}

        finally:
            wm.progress_end()


# ======================================================================
# Registration (operator only — menu is in ``ui/menu.py``)
# ======================================================================

classes = (MU_OT_import_world,)


def register() -> None:
    """Register the world import operator."""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    """Unregister the world import operator."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
