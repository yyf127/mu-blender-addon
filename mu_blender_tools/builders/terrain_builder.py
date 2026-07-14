# MU Online Blender Tools - Terrain Builder
#
# Converts TerrainReader data into terrain mesh primitives (vertices, triangles,
# UVs, material assignments) — the data layer that a future operator will
# consume to create actual Blender mesh objects.
#
# Reference implementations:
#   src/terrain/TerrainMesh.ts      (TypeScript — vertex grid, height, normals)
#   src/terrain/TerrainTexturing.ts (TypeScript — layer geometry & atlas UV)
#   Client.Main.Controls.Terrain.TerrainRenderer (C# — tile batching)
#
# Design principles:
#   - Pure data transformation — no file I/O, no bpy
#   - Multiple output modes: single unified mesh OR chunked meshes
#   - Two-layer texture blending via MAP layer1/layer2/alpha
#   - Vertex normals computed from height-field gradient (same as reference)

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from math import sqrt
from typing import Optional

from ..readers.terrain_reader import (
    TERRAIN_SCALE,
    TERRAIN_SIZE,
    TWFlags,
    TerrainAttributeData,
    TerrainMappingData,
    OZBData,
)

_logger = logging.getLogger("mu_blender_tools")

# ======================================================================
# Constants
# ======================================================================

SPECIAL_HEIGHT: float = 1200.0
"""Extra height applied to tiles with TWFlags.Height (reference TerrainMesh.ts)."""

VERTEX_GRID_SIZE: int = TERRAIN_SIZE + 1
"""Number of vertices per side of the terrain grid (257)."""

DEFAULT_CHUNK_SIZE: int = 8
"""Default tiles per chunk side (8×8 = 64 tiles/chunk)."""


# ======================================================================
# Mesh output data types
# ======================================================================


@dataclass
class TerrainVertex:
    """A single terrain vertex with position, normal, and UV data."""
    x: float = 0.0
    y: float = 0.0        # height
    z: float = 0.0
    nx: float = 0.0
    ny: float = 1.0
    nz: float = 0.0
    uv_u: float = 0.0     # base layer UV
    uv_v: float = 0.0


@dataclass
class TerrainFace:
    """A single triangle face."""
    v0: int = 0
    v1: int = 0
    v2: int = 0
    material_index: int = 0


@dataclass
class TerrainChunkMesh:
    """Mesh data for one terrain chunk (or the whole terrain).

    Stores data in flat arrays suitable for direct Blender ``foreach_set``
    consumption.
    """
    vertices: list[TerrainVertex] = field(default_factory=list)
    """All vertices in this chunk."""
    faces: list[TerrainFace] = field(default_factory=list)
    """All triangles in this chunk."""
    material_slots: list[str] = field(default_factory=list)
    """Material slot names (texture paths) for this chunk, indexed by
    ``TerrainFace.material_index``."""

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def face_count(self) -> int:
        return len(self.faces)


@dataclass
class TerrainBuilderOutput:
    """Complete output of the terrain builder."""
    chunks: list[TerrainChunkMesh] = field(default_factory=list)
    """One or more mesh chunks covering the full terrain."""
    chunk_size_tiles: int = DEFAULT_CHUNK_SIZE
    """Number of tiles per chunk side."""
    grid_size: int = TERRAIN_SIZE
    """Total terrain grid size in tiles."""
    vertex_grid_size: int = VERTEX_GRID_SIZE
    """Total vertex grid size per side."""


# ======================================================================
# Terrain Builder
# ======================================================================


class TerrainBuilder:
    """Builds terrain mesh data from parsed TerrainReader data.

    Args:
        att_data: Parsed ATT terrain attribute data.
        map_data: Parsed MAP terrain mapping data.
        height_data: Parsed OZB heightmap data (required).
        light_data: Optional parsed OZB lightmap data.
        chunk_size: Number of tiles per chunk side (default 8).
            Set to ``TERRAIN_SIZE`` for a single monolithic mesh.
        texture_path_resolver: Optional callable that maps texture index
            (0-255) to a material name / texture path.  Defaults to
            ``"TerrainTile{idx:02d}"``.
    """

    def __init__(
        self,
        att_data: TerrainAttributeData,
        map_data: TerrainMappingData,
        height_data: OZBData,
        light_data: Optional[OZBData] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        texture_path_resolver: Optional[callable] = None,
    ) -> None:
        self._att = att_data
        self._map = map_data
        self._height = height_data
        self._light = light_data
        self._chunk_size = min(chunk_size, TERRAIN_SIZE)
        self._resolve_tex = texture_path_resolver or self._default_texture_name

        # Validate input sizes
        self._validate()

    # ── validation ────────────────────────────────────────────────

    def _validate(self) -> None:
        """Validate input data dimensions."""
        expected = TERRAIN_SIZE * TERRAIN_SIZE
        for name, data in [
            ("ATT terrain_wall", self._att.terrain_wall),
            ("MAP layer1", self._map.layer1),
            ("MAP layer2", self._map.layer2),
            ("MAP alpha", self._map.alpha),
            ("height data", self._height.data),
        ]:
            if data is None:
                raise ValueError(f"{name} is None — cannot build terrain")

        # Height data must cover 256×256 pixels at least
        h = self._height
        if h.width < TERRAIN_SIZE or h.height < TERRAIN_SIZE:
            raise ValueError(
                f"Heightmap too small: {h.width}×{h.height}, "
                f"need at least {TERRAIN_SIZE}×{TERRAIN_SIZE}"
            )

    @staticmethod
    def _default_texture_name(tile_index: int) -> str:
        """Default texture name resolver."""
        if tile_index == 255:
            return ""  # no texture
        return f"TerrainTile{tile_index:02d}.ozj"

    # ── height sampling ───────────────────────────────────────────

    def _get_height(self, tile_x: int, tile_y: int) -> float:
        """Sample height at a tile coordinate (0-255).

        Reference: ``TerrainMesh.ts getHeight()``.
        """
        cx = max(0, min(tile_x, TERRAIN_SIZE - 1))
        cy = max(0, min(tile_y, TERRAIN_SIZE - 1))
        idx = cy * TERRAIN_SIZE + cx
        data = self._height.data
        h = data[idx * 4] * 1.5  # R channel * 1.5

        if self._att.terrain_wall and (self._att.terrain_wall[idx] & TWFlags.Height):
            h += SPECIAL_HEIGHT

        return h

    def _get_light_color(self, tile_x: int, tile_y: int) -> tuple[float, float, float]:
        """Sample lightmap colour at a tile coordinate.

        Returns (r, g, b) in 0-1 range.  White if no lightmap.
        """
        if not self._light or not self._light.data:
            return (1.0, 1.0, 1.0)

        cx = max(0, min(tile_x, TERRAIN_SIZE - 1))
        cy = max(0, min(tile_y, TERRAIN_SIZE - 1))
        idx = cy * TERRAIN_SIZE + cx
        data = self._light.data
        return (
            data[idx * 4] / 255.0,
            data[idx * 4 + 1] / 255.0,
            data[idx * 4 + 2] / 255.0,
        )

    # ── normal computation ───────────────────────────────────────

    def _compute_normal(
        self, vx: int, vy: int
    ) -> tuple[float, float, float]:
        """Compute vertex normal from height-field gradient.

        Reference: ``TerrainMesh.ts`` normal computation.
        Uses central differences on the 256×256 height grid.

        Returns (nx, ny, nz).
        """
        tx = min(vx, TERRAIN_SIZE - 1)
        ty = min(vy, TERRAIN_SIZE - 1)

        hL = self._get_height(tx - 1, ty)
        hR = self._get_height(tx + 1, ty)
        hD = self._get_height(tx, ty - 1)
        hU = self._get_height(tx, ty + 1)

        nx = hL - hR
        ny = 2.0 * TERRAIN_SCALE
        # Z axis is mirrored (world -> y flipped), so invert dH/dz sign
        nz = hU - hD

        length = sqrt(nx * nx + ny * ny + nz * nz)
        if length < 1e-12:
            return (0.0, 1.0, 0.0)

        inv = 1.0 / length
        return (nx * inv, ny * inv, nz * inv)

    # ── core build entry point ───────────────────────────────────

    def build(self) -> TerrainBuilderOutput:
        """Build the complete terrain mesh data.

        Returns:
            TerrainBuilderOutput with one or more chunk meshes.
        """
        output = TerrainBuilderOutput(
            chunk_size_tiles=self._chunk_size,
        )

        chunks_x = (TERRAIN_SIZE + self._chunk_size - 1) // self._chunk_size
        chunks_y = (TERRAIN_SIZE + self._chunk_size - 1) // self._chunk_size

        for cy in range(chunks_y):
            for cx in range(chunks_x):
                chunk = self._build_chunk(cx, cy)
                output.chunks.append(chunk)

        return output

    # ── chunk builder ─────────────────────────────────────────────

    def _build_chunk(self, chunk_cx: int, chunk_cy: int) -> TerrainChunkMesh:
        """Build one terrain chunk.

        Args:
            chunk_cx: Chunk column index.
            chunk_cy: Chunk row index.

        Returns:
            TerrainChunkMesh for this chunk.
        """
        chunk = TerrainChunkMesh()

        # Tile range for this chunk
        tile_x0 = chunk_cx * self._chunk_size
        tile_y0 = chunk_cy * self._chunk_size
        tile_x1 = min(tile_x0 + self._chunk_size, TERRAIN_SIZE)
        tile_y1 = min(tile_y0 + self._chunk_size, TERRAIN_SIZE)

        # Vertex grid range (+1 because vertices span tile boundaries)
        vx0 = tile_x0
        vy0 = tile_y0
        vx1 = tile_x1        # inclusive vertex index
        vy1 = tile_y1

        # We'll build a local vertex pool indexed by (vx, vy) relative to chunk
        # Store a dict: (local_vx, local_vy) -> vertex index
        local_vert: dict[tuple[int, int], int] = {}
        local_verts_list: list[TerrainVertex] = []

        def _get_or_create_vertex(vx: int, vy: int) -> int:
            """Get or create vertex at grid position (vx, vy)."""
            key = (vx, vy)
            idx = local_vert.get(key)
            if idx is not None:
                return idx

            # World-space position
            pos_x = vx * TERRAIN_SCALE
            pos_y = self._get_height(vx, vy)
            # MU world is Z-up with XY ground → Y-up with XZ ground
            # Z = world_size - Y  (mirror to keep handedness)
            world_size = TERRAIN_SIZE * TERRAIN_SCALE
            pos_z = world_size - vy * TERRAIN_SCALE

            # Normal
            nx, ny, nz = self._compute_normal(vx, vy)

            # UV (normalised over full terrain)
            uv_u = vx / TERRAIN_SIZE
            uv_v = vy / TERRAIN_SIZE

            vert = TerrainVertex(
                x=pos_x, y=pos_y, z=pos_z,
                nx=nx, ny=ny, nz=nz,
                uv_u=uv_u, uv_v=uv_v,
            )

            idx = len(local_verts_list)
            local_verts_list.append(vert)
            local_vert[key] = idx
            return idx

        # Collect unique material indices referenced in this chunk
        material_indices: set[int] = set()

        # Build faces
        for ty in range(tile_y0, tile_y1):
            for tx in range(tile_x0, tile_x1):
                tile_idx = ty * TERRAIN_SIZE + tx

                # Skip NoGround tiles
                if self._att.terrain_wall is not None:
                    if self._att.terrain_wall[tile_idx] & TWFlags.NoGround:
                        continue

                # Determine material(s) for this tile
                layer1_idx = self._map.layer1[tile_idx] if self._map.layer1 else 0
                layer2_idx = self._map.layer2[tile_idx] if self._map.layer2 else 255
                alpha_val = self._map.alpha[tile_idx] if self._map.alpha else 0

                # Vertex indices for the four corners of this tile
                # Winding: v0--v1  →  v0, v1, v3  and  v1, v2, v3
                #           |  |
                #          v3--v2
                v0 = _get_or_create_vertex(tx,     ty)
                v1 = _get_or_create_vertex(tx + 1, ty)
                v2 = _get_or_create_vertex(tx + 1, ty + 1)
                v3 = _get_or_create_vertex(tx,     ty + 1)

                # Two materials per tile: base (layer1) and overlay (layer2)
                # We create separate faces for each layer so the operator can
               # assign two materials in Blender.
                # If alpha is 0 or layer2 is 255 (no texture), only layer1.
                # If alpha is 255 (fully opaque overlay), only layer2.
                # Otherwise both layers are emitted.

                is_opaque = alpha_val >= 254  # fully opaque → layer2 is the visible surface

                # Resolve material slot index for layer1
                mat1 = layer1_idx
                material_indices.add(mat1)

                if is_opaque and layer2_idx != 255:
                    # Opaque → layer2 covers layer1 entirely
                    mat2 = layer2_idx
                    material_indices.add(mat2)
                    chunk.faces.append(TerrainFace(v0, v1, v3, mat2))
                    chunk.faces.append(TerrainFace(v1, v2, v3, mat2))
                else:
                    # Base layer (layer1)
                    chunk.faces.append(TerrainFace(v0, v1, v3, mat1))
                    chunk.faces.append(TerrainFace(v1, v2, v3, mat1))

                    # Overlay layer (layer2) if valid and has alpha
                    if layer2_idx != 255 and alpha_val > 0:
                        mat2 = layer2_idx
                        material_indices.add(mat2)
                        chunk.faces.append(TerrainFace(v0, v1, v3, mat2))
                        chunk.faces.append(TerrainFace(v1, v2, v3, mat2))

        # Build material slot list (sorted by index for determinism)
        sorted_mats = sorted(material_indices)
        # Remap face material indices to slot positions
        mat_remap = {old: new for new, old in enumerate(sorted_mats)}
        for face in chunk.faces:
            face.material_index = mat_remap[face.material_index]

        chunk.material_slots = [self._resolve_tex(idx) for idx in sorted_mats]
        chunk.vertices = local_verts_list

        return chunk


# ======================================================================
# Convenience builder function
# ======================================================================


def build_terrain_mesh(
    att_data: TerrainAttributeData,
    map_data: TerrainMappingData,
    height_data: OZBData,
    light_data: Optional[OZBData] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    texture_path_resolver: Optional[callable] = None,
) -> TerrainBuilderOutput:
    """Build terrain mesh data from parsed terrain reader data.

    This is a convenience wrapper around ``TerrainBuilder``.

    Args:
        att_data: Parsed ATT terrain attribute data.
        map_data: Parsed MAP terrain mapping data.
        height_data: Parsed OZB heightmap data.
        light_data: Optional parsed OZB lightmap data.
        chunk_size: Tiles per chunk side (default 8).  Set to
            ``TERRAIN_SIZE`` (256) for a single mesh.
        texture_path_resolver: Callable(index) → material name.

    Returns:
        TerrainBuilderOutput containing chunk meshes.
    """
    builder = TerrainBuilder(
        att_data=att_data,
        map_data=map_data,
        height_data=height_data,
        light_data=light_data,
        chunk_size=chunk_size,
        texture_path_resolver=texture_path_resolver,
    )
    return builder.build()
