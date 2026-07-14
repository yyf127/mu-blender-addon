# MU Online Blender Tools - Tests for Terrain Builder
#
# Run with:  python -m unittest tests.test_terrain_builder -v

"""
Tests for ``mu_blender_tools.builders.terrain_builder``.

Verifies terrain mesh generation: vertex grid, normals, UVs, material
assignments, chunking, and NoGround skipping.
"""

from __future__ import annotations

import math
import sys
import unittest

sys.path.insert(0, ".")

from mu_blender_tools.readers.terrain_reader import (
    TERRAIN_SIZE,
    TWFlags,
    TerrainAttributeData,
    TerrainMappingData,
    OZBData,
)
from mu_blender_tools.builders.terrain_builder import (
    VERTEX_GRID_SIZE,
    SPECIAL_HEIGHT,
    TERRAIN_SCALE,
    DEFAULT_CHUNK_SIZE,
    TerrainBuilder,
    TerrainBuilderOutput,
    TerrainChunkMesh,
    build_terrain_mesh,
)


# ======================================================================
# Helpers
# ======================================================================

def _make_default_att(flags: int = 0) -> TerrainAttributeData:
    """Create a default ATT with uniform flags."""
    return TerrainAttributeData(
        version=0,
        index=0,
        width=255,
        height=255,
        is_extended=False,
        terrain_wall=[flags] * (TERRAIN_SIZE * TERRAIN_SIZE),
    )


def _make_default_map(
    layer1_val: int = 0,
    layer2_val: int = 255,
    alpha_val: int = 0,
) -> TerrainMappingData:
    """Create a default MAP with uniform values."""
    return TerrainMappingData(
        version=1,
        map_number=1,
        layer1=[layer1_val] * (TERRAIN_SIZE * TERRAIN_SIZE),
        layer2=[layer2_val] * (TERRAIN_SIZE * TERRAIN_SIZE),
        alpha=[alpha_val] * (TERRAIN_SIZE * TERRAIN_SIZE),
    )


def _make_default_height(height_val: int = 128) -> OZBData:
    """Create a default heightmap with uniform height."""
    data = bytearray(TERRAIN_SIZE * TERRAIN_SIZE * 4)
    for i in range(TERRAIN_SIZE * TERRAIN_SIZE):
        data[i * 4] = height_val & 0xFF       # R = height
        data[i * 4 + 1] = 0
        data[i * 4 + 2] = 0
        data[i * 4 + 3] = 255
    return OZBData(
        width=TERRAIN_SIZE,
        height=TERRAIN_SIZE,
        data=bytes(data),
    )


def _make_default_light(light_val: int = 255) -> OZBData:
    """Create a default lightmap with uniform brightness."""
    data = bytearray(TERRAIN_SIZE * TERRAIN_SIZE * 4)
    for i in range(TERRAIN_SIZE * TERRAIN_SIZE):
        data[i * 4] = light_val & 0xFF
        data[i * 4 + 1] = light_val & 0xFF
        data[i * 4 + 2] = light_val & 0xFF
        data[i * 4 + 3] = 255
    return OZBData(
        width=TERRAIN_SIZE,
        height=TERRAIN_SIZE,
        data=bytes(data),
    )


# ======================================================================
# Tests: TerrainBuilder construction and validation
# ======================================================================

class TestTerrainBuilderConstruction(unittest.TestCase):
    """Test builder construction and validation."""

    def test_valid_construction(self) -> None:
        att = _make_default_att()
        mp = _make_default_map()
        h = _make_default_height()
        builder = TerrainBuilder(att_data=att, map_data=mp, height_data=h)
        self.assertIsNotNone(builder)

    def test_missing_height_raises(self) -> None:
        att = _make_default_att()
        mp = _make_default_map()
        h = OZBData(width=0, height=0, data=None)
        with self.assertRaises(ValueError):
            TerrainBuilder(att_data=att, map_data=mp, height_data=h)

    def test_small_heightmap_raises(self) -> None:
        att = _make_default_att()
        mp = _make_default_map()
        h = OZBData(width=4, height=4, data=bytes(4 * 4 * 4))
        with self.assertRaises(ValueError):
            TerrainBuilder(att_data=att, map_data=mp, height_data=h)


# ======================================================================
# Tests: Output structure
# ======================================================================

class TestTerrainBuilderOutput(unittest.TestCase):
    """Test output structure and chunking."""

    def test_default_chunk_count(self) -> None:
        att = _make_default_att()
        mp = _make_default_map()
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h)
        expected_chunks = (TERRAIN_SIZE // DEFAULT_CHUNK_SIZE) ** 2
        self.assertEqual(len(out.chunks), expected_chunks)

    def test_single_chunk_mode(self) -> None:
        att = _make_default_att()
        mp = _make_default_map()
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        self.assertEqual(len(out.chunks), 1)

    def test_output_properties(self) -> None:
        att = _make_default_att()
        mp = _make_default_map()
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h)
        self.assertEqual(out.grid_size, TERRAIN_SIZE)
        self.assertEqual(out.vertex_grid_size, VERTEX_GRID_SIZE)
        self.assertEqual(out.chunk_size_tiles, DEFAULT_CHUNK_SIZE)


# ======================================================================
# Tests: Vertex grid
# ======================================================================

class TestTerrainVertexGrid(unittest.TestCase):
    """Test vertex generation."""

    def test_vertex_count_single_chunk(self) -> None:
        """Single chunk should have VERTEX_GRID_SIZE^2 vertices."""
        att = _make_default_att()
        mp = _make_default_map()
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        # All tiles are active → all vertices created
        self.assertEqual(chunk.vertex_count, VERTEX_GRID_SIZE * VERTEX_GRID_SIZE)

    def test_vertex_positions(self) -> None:
        """Check first and last vertex positions."""
        att = _make_default_att()
        mp = _make_default_map()
        h = _make_default_height(height_val=100)
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]

        # Find vertex at (0, 0) — lowest UV
        v00 = chunk.vertices[0]
        self.assertAlmostEqual(v00.x, 0.0)
        self.assertAlmostEqual(v00.z, TERRAIN_SIZE * TERRAIN_SCALE)  # world_size - 0

        # Find vertex at (256, 256) — highest UV
        v_last = chunk.vertices[-1]
        self.assertAlmostEqual(v_last.x, TERRAIN_SIZE * TERRAIN_SCALE)
        self.assertAlmostEqual(v_last.z, 0.0)  # world_size - 256*100

    def test_height_applied(self) -> None:
        """Height value should be heightmap R * 1.5."""
        att = _make_default_att()
        mp = _make_default_map()
        h = _make_default_height(height_val=100)
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        expected_y = 100 * 1.5
        self.assertAlmostEqual(chunk.vertices[0].y, expected_y)

    def test_special_height_flag(self) -> None:
        """Tiles with TWFlags.Height should get extra height."""
        att = _make_default_att(flags=TWFlags.Height)
        mp = _make_default_map()
        h = _make_default_height(height_val=100)
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        expected_y = 100 * 1.5 + SPECIAL_HEIGHT
        self.assertAlmostEqual(chunk.vertices[0].y, expected_y)


# ======================================================================
# Tests: Normals
# ======================================================================

class TestTerrainNormals(unittest.TestCase):
    """Test normal vector computation."""

    def test_flat_terrain_normals(self) -> None:
        """Uniform height → normals should point up."""
        att = _make_default_att()
        mp = _make_default_map()
        h = _make_default_height(height_val=128)
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        for v in chunk.vertices:
            # Should be near (0, 1, 0)
            self.assertAlmostEqual(v.nx, 0.0, places=4)
            self.assertAlmostEqual(v.nz, 0.0, places=4)
            self.assertGreater(v.ny, 0.99)

    def test_normal_length(self) -> None:
        """Each normal should be unit length."""
        att = _make_default_att()
        mp = _make_default_map()
        h = _make_default_height(height_val=128)
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        for v in chunk.vertices[:100]:
            length = math.sqrt(v.nx ** 2 + v.ny ** 2 + v.nz ** 2)
            self.assertAlmostEqual(length, 1.0, places=4)

    def test_normal_has_gradient(self) -> None:
        """Sloped terrain should produce tilted normals."""
        # Create heightmap with a gradient
        data = bytearray(TERRAIN_SIZE * TERRAIN_SIZE * 4)
        for ty in range(TERRAIN_SIZE):
            for tx in range(TERRAIN_SIZE):
                idx = ty * TERRAIN_SIZE + tx
                data[idx * 4] = tx  # R increases with x
                data[idx * 4 + 1] = 0
                data[idx * 4 + 2] = 0
                data[idx * 4 + 3] = 255
        h = OZBData(width=TERRAIN_SIZE, height=TERRAIN_SIZE, data=bytes(data))
        att = _make_default_att()
        mp = _make_default_map()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        # Vertex at (1,1) should have non-zero nx (gradient in x direction)
        v11 = chunk.vertices[VERTEX_GRID_SIZE + 1]
        self.assertNotAlmostEqual(v11.nx, 0.0, places=2)


# ======================================================================
# Tests: UV
# ======================================================================

class TestTerrainUV(unittest.TestCase):
    """Test UV coordinate generation."""

    def test_uv_range(self) -> None:
        """UVs should be in [0, 1] range."""
        att = _make_default_att()
        mp = _make_default_map()
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        for v in chunk.vertices:
            self.assertGreaterEqual(v.uv_u, 0.0)
            self.assertLessEqual(v.uv_u, 1.0)
            self.assertGreaterEqual(v.uv_v, 0.0)
            self.assertLessEqual(v.uv_v, 1.0)

    def test_uv_corners(self) -> None:
        """UV at (0,0) should be (0,0), UV at (256,256) should be (1,1)."""
        att = _make_default_att()
        mp = _make_default_map()
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        self.assertAlmostEqual(chunk.vertices[0].uv_u, 0.0)
        self.assertAlmostEqual(chunk.vertices[0].uv_v, 0.0)
        self.assertAlmostEqual(chunk.vertices[-1].uv_u, 1.0)
        self.assertAlmostEqual(chunk.vertices[-1].uv_v, 1.0)


# ======================================================================
# Tests: Material / texture layer
# ======================================================================

class TestTerrainMaterials(unittest.TestCase):
    """Test material assignment and texture layer handling."""

    def test_material_slots_present(self) -> None:
        """Chunk should have material slots defined."""
        att = _make_default_att()
        mp = _make_default_map(layer1_val=5, layer2_val=255)
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        self.assertGreater(len(chunk.material_slots), 0)

    def test_material_slot_names(self) -> None:
        """Default resolver should produce expected names."""
        att = _make_default_att()
        mp = _make_default_map(layer1_val=3, layer2_val=255)
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        self.assertIn("TerrainTile03.ozj", chunk.material_slots)

    def test_custom_texture_resolver(self) -> None:
        """Custom resolver should be used."""
        def resolver(idx: int) -> str:
            return f"Custom_{idx}"

        att = _make_default_att()
        mp = _make_default_map(layer1_val=7, layer2_val=255)
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE,
                                 texture_path_resolver=resolver)
        chunk = out.chunks[0]
        self.assertIn("Custom_7", chunk.material_slots)

    def test_face_material_indices_match_slots(self) -> None:
        """Face material_index should be valid slot index."""
        att = _make_default_att()
        mp = _make_default_map(layer1_val=2, layer2_val=255, alpha_val=0)
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        for face in chunk.faces:
            self.assertLess(face.material_index, len(chunk.material_slots))
            self.assertGreaterEqual(face.material_index, 0)


# ======================================================================
# Tests: Face count and NoGround
# ======================================================================

class TestTerrainFaces(unittest.TestCase):
    """Test face generation and NoGround skipping."""

    def test_face_count_all_active(self) -> None:
        """All tiles active → should have 2 triangles per tile × total tiles."""
        att = _make_default_att(flags=0)
        mp = _make_default_map(layer1_val=0, layer2_val=255, alpha_val=0)
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        # 256*256 tiles, 2 triangles each
        expected_faces = TERRAIN_SIZE * TERRAIN_SIZE * 2
        self.assertEqual(chunk.face_count, expected_faces)

    def test_no_ground_skips_tiles(self) -> None:
        """Tiles with NoGround flag should be skipped entirely."""
        att = _make_default_att(flags=TWFlags.NoGround)
        mp = _make_default_map()
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        self.assertEqual(chunk.face_count, 0)
        # Vertices may still exist if referenced elsewhere, but faces should be 0

    def test_partial_no_ground(self) -> None:
        """Mix of active and NoGround tiles in different chunks."""
        # Make only the first tile NoGround
        wall = [0] * (TERRAIN_SIZE * TERRAIN_SIZE)
        wall[0] = TWFlags.NoGround
        att = TerrainAttributeData(
            version=0, index=0, width=255, height=255,
            is_extended=False, terrain_wall=wall,
        )
        mp = _make_default_map()
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=DEFAULT_CHUNK_SIZE)

        # First chunk (0,0) has tile (0,0) which is NoGround → fewer faces
        first_chunk = out.chunks[0]
        # 8x8 tiles minus 1 NoGround = 63 active tiles × 2 triangles
        self.assertEqual(first_chunk.face_count, 63 * 2)


# ======================================================================
# Tests: Two-layer blending
# ======================================================================

class TestTerrainLayerBlending(unittest.TestCase):
    """Test dual-layer material emission."""

    def test_opaque_overlay_uses_layer2_only(self) -> None:
        """Alpha >= 254 and layer2 != 255 → only layer2 faces emitted."""
        att = _make_default_att()
        mp = _make_default_map(layer1_val=1, layer2_val=2, alpha_val=255)
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        # Should have 2 triangles per tile, all using material index for layer2
        self.assertEqual(chunk.face_count, TERRAIN_SIZE * TERRAIN_SIZE * 2)
        for face in chunk.faces:
            mat_name = chunk.material_slots[face.material_index]
            self.assertIn("TerrainTile02", mat_name)

    def test_alpha_blend_emits_both_layers(self) -> None:
        """0 < alpha < 254 and layer2 != 255 → both layers emitted."""
        att = _make_default_att()
        mp = _make_default_map(layer1_val=3, layer2_val=4, alpha_val=128)
        h = _make_default_height()
        out = build_terrain_mesh(att, mp, h, chunk_size=TERRAIN_SIZE)
        chunk = out.chunks[0]
        # 2 triangles for layer1 + 2 triangles for layer2 = 4 per tile
        self.assertEqual(chunk.face_count, TERRAIN_SIZE * TERRAIN_SIZE * 4)


# ======================================================================
# Tests: Lightmap
# ======================================================================

class TestTerrainLightmap(unittest.TestCase):
    """Test lightmap data integration."""

    def test_lightmap_accepted(self) -> None:
        """Builder should accept optional lightmap."""
        att = _make_default_att()
        mp = _make_default_map()
        h = _make_default_height()
        light = _make_default_light(light_val=200)
        out = build_terrain_mesh(att, mp, h, light_data=light)
        self.assertGreater(len(out.chunks), 0)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
