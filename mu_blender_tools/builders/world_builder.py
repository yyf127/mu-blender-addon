# MU Online Blender Tools - World Builder
#
# Converts WorldReader data (WorldData) into a Blender scene with
# organised collections, empty objects with correct transforms, and
# optional BMD model importing.
#
# Design:
#   - Pure Blender Data API — no bpy.ops calls
#   - Creates nested collections: World → {Terrain, Objects, NPC, ...}
#   - Each world object → Blender Empty with location/rotation/scale
#   - Stores BMD model path + type as custom properties
#   - Optional ``bmd_loader`` callback for importing actual mesh geometry
#   - Integrates with TerrainBuilderOutput for terrain mesh generation

from __future__ import annotations

import logging
import math
from typing import Any, Callable, Optional

import bpy
from bpy.types import Collection, Material, Mesh, Object

from ..readers.world_reader import (
    WorldData,
    WorldObject,
    WorldObjectCategory,
)
from ..builders.terrain_builder import (
    TerrainBuilderOutput,
    TerrainChunkMesh,
)

_logger = logging.getLogger("mu_blender_tools")

# ======================================================================
# Constants
# ======================================================================

WORLD_COLLECTION_NAME: str = "MU_World"
"""Root collection for all world content."""

TERRAIN_COLLECTION_NAME: str = "Terrain"
OBJECTS_COLLECTION_NAME: str = "Objects"
NPC_COLLECTION_NAME: str = "NPC"
MONSTER_COLLECTION_NAME: str = "Monster"
EFFECTS_COLLECTION_NAME: str = "Effects"
LIGHTS_COLLECTION_NAME: str = "Lights"
WATER_COLLECTION_NAME: str = "Water"

TERRAIN_SCALE: float = 100.0
"""MU terrain scale (world units per tile).  Matches terrain_builder."""

# Default MU world size (256 tiles × 100 world-units per tile)
MU_WORLD_SIZE: float = 256.0 * TERRAIN_SCALE

# Collection name → WorldObjectCategory mapping
_CATEGORY_TO_COLLECTION: dict[WorldObjectCategory, str] = {
    WorldObjectCategory.Object: OBJECTS_COLLECTION_NAME,
    WorldObjectCategory.Light: LIGHTS_COLLECTION_NAME,
    WorldObjectCategory.Water: WATER_COLLECTION_NAME,
    WorldObjectCategory.Effect: EFFECTS_COLLECTION_NAME,
    WorldObjectCategory.NPC: NPC_COLLECTION_NAME,
    WorldObjectCategory.Monster: MONSTER_COLLECTION_NAME,
}


# ======================================================================
# BMD loader protocol
# ======================================================================

# A BMD loader is a callable:  (model_path: str, collection: Collection) → Object | None
# It reads the BMD file at ``model_path``, creates mesh objects inside
# ``collection``, and returns the root object (or None on failure).
BMDLoaderFn = Callable[[str, Collection], Optional[Object]]


# ======================================================================
# WorldBuilder
# ======================================================================


class WorldBuilder:
    """Build a complete Blender scene from parsed world data.

    Usage::

        from mu_blender_tools.readers.world_reader import read_world
        from mu_blender_tools.builders.world_builder import WorldBuilder

        world_data = read_world(obj_data, att_data, map_data, height_data)
        builder = WorldBuilder(world_data)
        builder.build()
    """

    def __init__(
        self,
        world_data: WorldData,
        terrain_output: Optional[TerrainBuilderOutput] = None,
        bmd_loader: Optional[BMDLoaderFn] = None,
        collection_name: str = WORLD_COLLECTION_NAME,
    ) -> None:
        """Initialise the world builder.

        Args:
            world_data: Parsed world data from ``read_world()``.
            terrain_output: Optional terrain mesh data from
                ``build_terrain_mesh()``.  If provided a terrain mesh
                is created.
            bmd_loader: Optional callable that imports a BMD model into
                a collection.  If provided each world object will attempt
                to load its model.  Signature:
                ``(model_path: str, collection: Collection) → Object | None``
            collection_name: Name for the root world collection.
        """
        self._data = world_data
        self._terrain = terrain_output
        self._bmd_loader = bmd_loader
        self._root_name = collection_name

        # Populated during build()
        self.root_collection: Optional[Collection] = None
        self.collections: dict[str, Collection] = {}
        """Flat dict of all created sub-collections keyed by name."""

        self.created_objects: list[Object] = []
        """All Blender objects created during build()."""

    # ==================================================================
    # Public API
    # ==================================================================

    def build(self) -> dict[str, Collection]:
        """Run the full build pipeline.

        1. Create collection hierarchy.
        2. Build terrain mesh (if ``terrain_output`` was provided).
        3. Create world-object empties (all categories).
        4. Optionally import BMD models via ``bmd_loader``.

        Returns:
            Dict of ``{collection_name: Collection}`` for all created
            sub-collections.
        """
        self._create_collections()

        if self._terrain is not None:
            self._build_terrain()

        for wo in self._data.objects:
            self._create_world_object(wo)

        _logger.info(
            "WorldBuilder: created %d objects in %d collections for world %d",
            len(self.created_objects),
            len(self.collections),
            self._data.map_number,
        )
        return dict(self.collections)

    # ==================================================================
    # Collection management
    # ==================================================================

    def _ensure_collection(self, name: str, parent: Optional[Collection] = None) -> Collection:
        """Get or create a collection, optionally parenting it.

        Args:
            name: Collection name.
            parent: Parent collection (if None, scene master collection).

        Returns:
            The (possibly existing) collection.
        """
        col = bpy.data.collections.get(name)
        if col is None:
            col = bpy.data.collections.new(name)
            self.collections[name] = col

        # Link to parent
        if parent is not None and col.name not in parent.children:
            parent.children.link(col)
        elif parent is None and col.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(col)

        return col

    def _create_collections(self) -> None:
        """Create the nested collection hierarchy."""
        # Root world collection
        self.root_collection = self._ensure_collection(self._root_name)

        collections_order = [
            TERRAIN_COLLECTION_NAME,
            OBJECTS_COLLECTION_NAME,
            NPC_COLLECTION_NAME,
            MONSTER_COLLECTION_NAME,
            EFFECTS_COLLECTION_NAME,
            LIGHTS_COLLECTION_NAME,
            WATER_COLLECTION_NAME,
        ]

        for name in collections_order:
            col = self._ensure_collection(name, parent=self.root_collection)
            self.collections[name] = col

    def _collection_for_category(self, category: WorldObjectCategory) -> Collection:
        """Get the target collection for a world object category.

        Falls back to the Objects collection.
        """
        name = _CATEGORY_TO_COLLECTION.get(category, OBJECTS_COLLECTION_NAME)
        col = self.collections.get(name)
        if col is None:
            col = self._ensure_collection(name, parent=self.root_collection)
            self.collections[name] = col
        return col

    # ==================================================================
    # Coordinate conversion helpers
    # ==================================================================

    @staticmethod
    def _mu_to_blender_position(
        mu_x: float, mu_y: float, mu_z: float,
        world_size: float = MU_WORLD_SIZE,
    ) -> tuple[float, float, float]:
        """Convert MU Online coordinates to Blender Y-up coordinates.

        MU Online uses Z-up with XY as the ground plane.
        Blender uses Z-up with XZ as the ground plane (Y-forward).

        Mapping:
            Blender.X = MU.X
            Blender.Y = world_size - MU.Y  (mirror to keep winding)
            Blender.Z = MU.Z               (height, up)

        Args:
            mu_x: MU X coordinate (ground plane).
            mu_y: MU Y coordinate (ground plane, north direction).
            mu_z: MU Z coordinate (height / elevation).
            world_size: World extent in Blender units.

        Returns:
            ``(blender_x, blender_y, blender_z)``.
        """
        return (mu_x, world_size - mu_y, mu_z)

    @staticmethod
    def _mu_angle_to_blender_rotation(
        angle_x: float, angle_y: float, angle_z: float,
    ) -> tuple[float, float, float]:
        """Convert MU Euler angles (degrees) to Blender Euler (radians).

        MU angles are in degrees with Z-up convention.
        Blender expects radians with XYZ Euler order.

        Args:
            angle_x: Rotation around X axis (degrees).
            angle_y: Rotation around Y axis (degrees, facing direction).
            angle_z: Rotation around Z axis (degrees, roll/up).

        Returns:
            ``(blender_rx, blender_ry, blender_rz)`` in radians.
        """
        return (
            math.radians(angle_x),
            math.radians(angle_y),
            math.radians(angle_z),
        )

    # ==================================================================
    # Terrain building
    # ==================================================================

    def _build_terrain(self) -> None:
        """Build terrain meshes from ``TerrainBuilderOutput``."""
        if self._terrain is None:
            return

        terrain_col = self.collections.get(TERRAIN_COLLECTION_NAME)
        if terrain_col is None:
            terrain_col = self._ensure_collection(
                TERRAIN_COLLECTION_NAME, parent=self.root_collection,
            )
            self.collections[TERRAIN_COLLECTION_NAME] = terrain_col

        for chunk_index, chunk in enumerate(self._terrain.chunks):
            self._build_terrain_chunk(chunk, chunk_index, terrain_col)

    def _build_terrain_chunk(
        self, chunk: TerrainChunkMesh, index: int, collection: Collection,
    ) -> Optional[Object]:
        """Build a single terrain chunk mesh.

        Args:
            chunk: TerrainChunkMesh data.
            index: Chunk index (for naming).
            collection: Target collection.

        Returns:
            Created Blender Object, or None if the chunk has no faces.
        """
        if chunk.face_count == 0 or chunk.vertex_count == 0:
            return None

        mesh_name = f"Terrain_Chunk{index:04d}"
        mesh: Mesh = bpy.data.meshes.new(mesh_name)

        # -- Vertices --
        verts: list[tuple[float, float, float]] = [
            (v.x, v.y, v.z) for v in chunk.vertices
        ]
        mesh.vertices.add(chunk.vertex_count)
        mesh.vertices.foreach_set("co", [c for v in verts for c in v])

        # -- Faces (triangles) --
        tri_count = chunk.face_count
        loop_count = tri_count * 3

        # Each face is a triangle: store vertex index triple per face
        face_verts: list[int] = []
        for face in chunk.faces:
            face_verts.extend([face.v0, face.v1, face.v2])

        mesh.loops.add(loop_count)
        mesh.polygons.add(tri_count)

        # Build polygon loop_start / loop_total
        loop_starts: list[int] = []
        loop_totals: list[int] = []
        for i in range(tri_count):
            loop_starts.append(i * 3)
            loop_totals.append(3)

        mesh.polygons.foreach_set("loop_start", loop_starts)
        mesh.polygons.foreach_set("loop_total", loop_totals)
        mesh.loops.foreach_set("vertex_index", face_verts)

        # -- Material indices --
        mat_indices: list[int] = []
        for face in chunk.faces:
            mat_indices.append(face.material_index)
        mesh.polygons.foreach_set("material_index", mat_indices)

        # -- UV --
        uv_data = mesh.uv_layers.new(name="UVMap")
        if uv_data is not None:
            uv_loop: list[float] = []
            for face in chunk.faces:
                for vi in (face.v0, face.v1, face.v2):
                    if vi < len(chunk.vertices):
                        v = chunk.vertices[vi]
                        uv_loop.extend([v.uv_u, v.uv_v])
                    else:
                        uv_loop.extend([0.0, 0.0])
            uv_data.data.foreach_set("uv", uv_loop)

        # -- Normals (per-vertex) --
        mesh.use_auto_smooth = True
        normals: list[float] = []
        for v in chunk.vertices:
            normals.extend([v.nx, v.ny, v.nz])
        # Repeat per loop vertex
        loop_normals: list[float] = []
        for face in chunk.faces:
            for vi in (face.v0, face.v1, face.v2):
                if vi < len(chunk.vertices):
                    off = vi * 3
                    loop_normals.extend(normals[off:off + 3])
                else:
                    loop_normals.extend([0.0, 1.0, 0.0])
        mesh.normals_split_custom_set(
            [(loop_normals[i], loop_normals[i + 1], loop_normals[i + 2])
             for i in range(0, len(loop_normals), 3)]
        )

        mesh.validate()
        mesh.update()

        # -- Material slots --
        obj: Object = bpy.data.objects.new(mesh_name, mesh)
        collection.objects.link(obj)
        self.created_objects.append(obj)

        for mat_name in chunk.material_slots:
            mat = bpy.data.materials.get(mat_name)
            if mat is None:
                mat = bpy.data.materials.new(mat_name)
            obj.data.materials.append(mat)

        _logger.debug(
            "Terrain chunk %d: %d verts, %d faces, %d materials",
            index, chunk.vertex_count, chunk.face_count,
            len(chunk.material_slots),
        )
        return obj

    # ==================================================================
    # World object creation
    # ==================================================================

    def _create_world_object(self, wo: WorldObject) -> Optional[Object]:
        """Create a Blender object for one ``WorldObject``.

        If a ``bmd_loader`` was provided the BMD model is imported.
        Otherwise a plain Empty is created as a placeholder.

        Args:
            wo: The world object to create.

        Returns:
            The created Blender Object, or None.
        """
        col = self._collection_for_category(wo.category)
        pos = self._mu_to_blender_position(
            wo.position_x, wo.position_y, wo.position_z,
        )
        rot = self._mu_angle_to_blender_rotation(
            wo.angle_x, wo.angle_y, wo.angle_z,
        )

        # Try BMD loader first
        if self._bmd_loader is not None and wo.model_path:
            try:
                obj = self._bmd_loader(wo.model_path, col)
                if obj is not None:
                    obj.location = pos
                    obj.rotation_euler = rot
                    obj.scale = (wo.scale, wo.scale, wo.scale)
                    self._set_object_properties(obj, wo)
                    self.created_objects.append(obj)
                    return obj
            except Exception as e:
                _logger.warning(
                    "BMD loader failed for '%s' (type %d): %s — "
                    "creating empty placeholder",
                    wo.model_path, wo.type, e,
                )

        # Fallback: create an Empty
        obj = self._create_empty(wo, col, pos, rot)
        self.created_objects.append(obj)
        return obj

    def _create_empty(
        self, wo: WorldObject, collection: Collection,
        pos: tuple[float, float, float],
        rot: tuple[float, float, float],
    ) -> Object:
        """Create a plain Empty object as a placeholder.

        The empty stores the BMD model path and type as custom properties
        so a later operator can replace it with the actual model.
        """
        name = f"{wo.name}_t{wo.type:03d}"
        obj: Object = bpy.data.objects.new(name, None)  # None data = Empty
        obj.empty_display_size = 50.0
        obj.empty_display_type = "PLAIN_AXES"
        obj.location = pos
        obj.rotation_euler = rot
        obj.scale = (wo.scale, wo.scale, wo.scale)

        self._set_object_properties(obj, wo)

        collection.objects.link(obj)
        return obj

    @staticmethod
    def _set_object_properties(obj: Object, wo: WorldObject) -> None:
        """Store world-object metadata as Blender custom properties."""
        obj["mu_type"] = wo.type
        obj["mu_category"] = wo.category.name
        obj["mu_name"] = wo.name
        obj["mu_model_path"] = wo.model_path
        obj["mu_angle_x"] = wo.angle_x
        obj["mu_angle_y"] = wo.angle_y
        obj["mu_angle_z"] = wo.angle_z
