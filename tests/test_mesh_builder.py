# MU Online Blender Tools - Tests for MeshBuilder
#
# Run with:  python -m unittest tests.test_mesh_builder -v
#
# NOTE: MeshBuilder requires bpy (Blender Python). These tests use mocking
# to verify the builder logic without a running Blender instance.
#
# For manual Blender testing:
#   blender --python tests/manual_test_mesh_builder.py

"""
Tests for ``mu_blender_tools.builders.mesh_builder.MeshBuilder``.

Uses ``unittest.mock`` to simulate Blender's bpy module.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock
from typing import Any

sys.path.insert(0, ".")


# ======================================================================
# Mock bpy infrastructure BEFORE importing MeshBuilder
# ======================================================================

class MockMesh:
    """Mimics bpy.types.Mesh for testing."""
    def __init__(self, name: str = "Mesh") -> None:
        self.name = name
        self.vertices = MagicMock()
        self.loops = MagicMock()
        self.polygons = MagicMock()
        self.uv_layers = MagicMock()
        self.uv_layers.new.return_value = MagicMock()
        self.user_data: dict[str, Any] = {}
        self.use_auto_smooth = False
        self._normals_split_custom_set_called = False

    def validate(self) -> None:
        pass

    def update(self) -> None:
        pass

    def normals_split_custom_set(self, normals: Any) -> None:
        """Mock normals_split_custom_set — stores the normals for later assertion."""
        self._normals_split_custom_set_called = True
        self._normals_split_custom_set_args = normals


class MockObject:
    """Mimics bpy.types.Object for testing.

    Correctly simulates the relationship between ``material_slots``
    and ``data.materials.append()`` — appending to ``data.materials``
    also grows ``material_slots`` (matching real Blender behavior).
    """
    def __init__(self, name: str = "Object", mesh_data: Any = None) -> None:
        self.name = name
        self.data = mesh_data if mesh_data else MockMesh()
        self.material_slots: list[None] = []
        # Wire data.materials.append to update material_slots
        if not hasattr(self.data, 'materials') or self.data.materials is None:
            self.data.materials = MagicMock()
        self.data.materials.append = self._append_material_slot

    def _append_material_slot(self, item: Any = None) -> None:
        self.material_slots.append(None)


class MockBpy:
    """Mock the ``bpy`` module."""
    def __init__(self) -> None:
        self.data = MagicMock()
        self.data.meshes = MagicMock()
        self.data.meshes.new.side_effect = lambda name: MockMesh(name)
        self.data.objects = MagicMock()
        self.data.objects.new.side_effect = lambda name, mesh: MockObject(name, mesh)

        self.context = MagicMock()
        self.context.view_layer = MagicMock()
        self.context.view_layer.active_collection = MagicMock()
        self.context.scene = MagicMock()
        self.context.scene.collection = MagicMock()

        self.types = MagicMock()
        self.types.Collection = MagicMock
        self.types.Mesh = MockMesh
        self.types.Object = MockObject


# Patch sys.modules BEFORE any addon code is imported
_bpy_mock = MockBpy()
sys.modules["bpy"] = _bpy_mock
sys.modules["bpy.types"] = MagicMock()
sys.modules["bpy_extras"] = MagicMock()

from mu_blender_tools.readers.bmd_types import (
    BMD,
    BMDTextureMesh,
    BMDTextureVertex,
    BMDTextureNormal,
    BMDTexCoord,
    BMDTriangle,
    BMD_DUMMY_BONE,
)
from mu_blender_tools.builders.mesh_builder import MeshBuilder


# ======================================================================
# Test data helpers
# ======================================================================

def _v(node: int = 0, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> BMDTextureVertex:
    return BMDTextureVertex(Node=node, Position=(x, y, z))

def _n(node: int = 0, nx: float = 0.0, ny: float = 0.0, nz: float = 1.0) -> BMDTextureNormal:
    return BMDTextureNormal(Node=node, Normal=(nx, ny, nz), BindVertex=0)

def _t(u: float = 0.0, v: float = 0.0) -> BMDTexCoord:
    return BMDTexCoord(U=u, V=v)

def _tri(
    polygon: int = 3,
    v: tuple[int, int, int, int] = (0, 1, 2, 0),
    n: tuple[int, int, int, int] = (0, 1, 2, 0),
    tc: tuple[int, int, int, int] = (0, 1, 2, 0),
) -> BMDTriangle:
    return BMDTriangle(
        Polygon=polygon,
        VertexIndex=list(v),
        NormalIndex=list(n),
        TexCoordIndex=list(tc),
        LightMapCoord=[],
        LightMapIndexes=0,
    )

def _mesh(
    vertices: list[BMDTextureVertex] | None = None,
    normals: list[BMDTextureNormal] | None = None,
    texcoords: list[BMDTexCoord] | None = None,
    triangles: list[BMDTriangle] | None = None,
    texture: int = 0,
    texture_path: str = "",
) -> BMDTextureMesh:
    return BMDTextureMesh(
        Vertices=vertices or [],
        Normals=normals or [],
        TexCoords=texcoords or [],
        Triangles=triangles or [],
        Texture=texture,
        TexturePath=texture_path,
    )


# ======================================================================
# Tests: _build_face_data (pure logic, no bpy needed)
# ======================================================================

class TestBuildFaceData(unittest.TestCase):
    """_build_face_data: loop counts and vertex indices."""

    def test_triangle(self) -> None:
        m = _mesh(
            vertices=[_v() for _ in range(3)],
            triangles=[_tri(polygon=3, v=(0, 1, 2, 0))],
        )
        counts, indices = MeshBuilder._build_face_data(m)
        self.assertEqual(counts, [3])
        self.assertEqual(indices[0], [0, 1, 2])

    def test_quad(self) -> None:
        m = _mesh(
            vertices=[_v() for _ in range(4)],
            triangles=[_tri(polygon=4, v=(0, 1, 2, 3))],
        )
        counts, indices = MeshBuilder._build_face_data(m)
        self.assertEqual(counts, [4])
        self.assertEqual(indices[0], [0, 1, 2, 3])

    def test_invalid_index_clamped(self) -> None:
        m = _mesh(
            vertices=[_v()],
            triangles=[_tri(polygon=3, v=(5, -1, 2, 0))],
        )
        _, indices = MeshBuilder._build_face_data(m)
        self.assertEqual(indices[0], [0, 0, 0])

    def test_mixed_tri_and_quad(self) -> None:
        m = _mesh(
            vertices=[_v() for _ in range(4)],
            triangles=[
                _tri(polygon=3, v=(0, 1, 2, 0)),
                _tri(polygon=4, v=(0, 1, 2, 3)),
            ],
        )
        counts, _ = MeshBuilder._build_face_data(m)
        self.assertEqual(counts, [3, 4])

    def test_polygon_zero_treated_as_tri(self) -> None:
        m = _mesh(
            vertices=[_v() for _ in range(3)],
            triangles=[_tri(polygon=0, v=(0, 1, 2, 0))],
        )
        counts, _ = MeshBuilder._build_face_data(m)
        self.assertEqual(counts, [3])

    def test_empty_mesh(self) -> None:
        m = _mesh()
        counts, indices = MeshBuilder._build_face_data(m)
        self.assertEqual(counts, [])
        self.assertEqual(indices, [])


# ======================================================================
# Tests: _build_vertices
# ======================================================================

class TestBuildVertices(unittest.TestCase):
    """_build_vertices: vertex coordinates."""

    def test_writes_coords_via_foreach(self) -> None:
        m = _mesh(vertices=[_v(x=1.0, y=2.0, z=3.0), _v(x=4.0, y=5.0, z=6.0)])
        mock_mesh = MockMesh()
        MeshBuilder._build_vertices(mock_mesh, m, 2)
        mock_mesh.vertices.foreach_set.assert_called_once_with(
            "co", [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        )

    def test_no_vertices_empty(self) -> None:
        m = _mesh()
        mock_mesh = MockMesh()
        MeshBuilder._build_vertices(mock_mesh, m, 0)
        mock_mesh.vertices.foreach_set.assert_called_once_with("co", [])


# ======================================================================
# Tests: _build_faces
# ======================================================================

class TestBuildFaces(unittest.TestCase):
    """_build_faces: polygon and loop data."""

    def test_single_triangle(self) -> None:
        m = _mesh(
            vertices=[_v() for _ in range(3)],
            triangles=[_tri(polygon=3, v=(0, 1, 2, 0))],
        )
        counts, indices = MeshBuilder._build_face_data(m)
        mock_mesh = MockMesh()
        MeshBuilder._build_faces(mock_mesh, m, counts, indices, 1)

        mock_mesh.loops.foreach_set.assert_called_once_with("vertex_index", [0, 1, 2])
        poly_calls = {c[0][0]: c[0][1] for c in mock_mesh.polygons.foreach_set.call_args_list}
        self.assertEqual(poly_calls["loop_start"], [0])
        self.assertEqual(poly_calls["loop_total"], [3])


# ======================================================================
# Tests: _build_uv
# ======================================================================

class TestBuildUV(unittest.TestCase):
    """_build_uv: UV coordinates."""

    def test_uv_written_correctly(self) -> None:
        m = _mesh(
            vertices=[_v() for _ in range(3)],
            texcoords=[_t(0.5, 0.75) for _ in range(3)],
            triangles=[_tri(polygon=3, v=(0, 1, 2, 0), tc=(0, 1, 2, 0))],
        )
        counts, indices = MeshBuilder._build_face_data(m)
        mock_mesh = MockMesh()
        MeshBuilder._build_uv(mock_mesh, m, counts, indices)

        mock_mesh.uv_layers.new.assert_called_once_with(name="UVMap")
        uv = mock_mesh.uv_layers.new.return_value
        uv.data.foreach_set.assert_called_once_with("uv", [0.5, 0.75] * 3)

    def test_bad_uv_index_zeros(self) -> None:
        m = _mesh(
            vertices=[_v() for _ in range(3)],
            texcoords=[_t(0.5, 0.75)],
            triangles=[_tri(polygon=3, v=(0, 1, 2, 0), tc=(0, 99, -1, 0))],
        )
        counts, indices = MeshBuilder._build_face_data(m)
        mock_mesh = MockMesh()
        MeshBuilder._build_uv(mock_mesh, m, counts, indices)

        uv = mock_mesh.uv_layers.new.return_value
        args = uv.data.foreach_set.call_args[0][1]
        self.assertEqual(args[0], 0.5)   # valid index 0
        self.assertEqual(args[1], 0.75)
        self.assertEqual(args[2], 0.0)   # invalid index 99
        self.assertEqual(args[4], 0.0)   # invalid index -1


# ======================================================================
# Tests: _build_normals
# ======================================================================

class TestBuildNormals(unittest.TestCase):
    """_build_normals: custom split normals."""

    def test_normals_written(self) -> None:
        m = _mesh(
            vertices=[_v() for _ in range(3)],
            normals=[_n(nz=1.0) for _ in range(3)],
            triangles=[_tri(polygon=3, v=(0, 1, 2, 0), n=(0, 1, 2, 0))],
        )
        counts, indices = MeshBuilder._build_face_data(m)
        mock_mesh = MockMesh()
        MeshBuilder._build_normals(mock_mesh, m, counts, indices)

        self.assertTrue(mock_mesh._normals_split_custom_set_called)
        loops = mock_mesh._normals_split_custom_set_args
        self.assertEqual(len(loops), 3)
        for ln in loops:
            self.assertEqual(ln, (0.0, 0.0, 1.0))

    def test_bad_normal_index_fallback(self) -> None:
        m = _mesh(
            vertices=[_v() for _ in range(3)],
            normals=[_n()],
            triangles=[_tri(polygon=3, v=(0, 1, 2, 0), n=(0, 99, -1, 0))],
        )
        counts, indices = MeshBuilder._build_face_data(m)
        mock_mesh = MockMesh()
        MeshBuilder._build_normals(mock_mesh, m, counts, indices)

        self.assertTrue(mock_mesh._normals_split_custom_set_called)
        loops = mock_mesh._normals_split_custom_set_args
        self.assertEqual(loops[1], (0.0, 0.0, 1.0))  # invalid index 99
        self.assertEqual(loops[2], (0.0, 0.0, 1.0))  # invalid index -1


# ======================================================================
# Tests: _build_material_indices
# ======================================================================

class TestBuildMaterialIndices(unittest.TestCase):
    """_build_material_indices: per-polygon material index."""

    def test_uses_texture_field(self) -> None:
        m = _mesh(vertices=[_v() for _ in range(3)], triangles=[_tri()], texture=5)
        mock_mesh = MockMesh()
        MeshBuilder._build_material_indices(mock_mesh, m, 1)
        args = mock_mesh.polygons.foreach_set.call_args[0]
        self.assertEqual(args[0], "material_index")
        self.assertEqual(args[1], [5])

    def test_negative_clamped_to_zero(self) -> None:
        m = _mesh(vertices=[_v() for _ in range(3)], triangles=[_tri()], texture=-1)
        mock_mesh = MockMesh()
        MeshBuilder._build_material_indices(mock_mesh, m, 1)
        args = mock_mesh.polygons.foreach_set.call_args[0]
        self.assertEqual(args[1], [0])


# ======================================================================
# Tests: _build_material_slots
# ======================================================================

class TestBuildMaterialSlots(unittest.TestCase):
    """_build_material_slots: empty material slots on object."""

    def test_slots_for_texture_3(self) -> None:
        m = _mesh(texture=3)
        obj = MockObject("Test")
        MeshBuilder._build_material_slots(obj, m)
        self.assertGreaterEqual(len(obj.material_slots), 4)

    def test_slots_for_texture_0(self) -> None:
        m = _mesh(texture=0)
        obj = MockObject("Test")
        MeshBuilder._build_material_slots(obj, m)
        self.assertGreaterEqual(len(obj.material_slots), 1)


# ======================================================================
# Integration tests
# ======================================================================

class TestCreateSingleMesh(unittest.TestCase):
    """_create_single_mesh integration."""

    def test_basic_triangle(self) -> None:
        m = _mesh(
            vertices=[_v(x=float(i)) for i in range(3)],
            normals=[_n(nz=1.0) for _ in range(3)],
            texcoords=[_t(0.0, 0.0) for _ in range(3)],
            triangles=[_tri(polygon=3, v=(0, 1, 2, 0))],
        )
        obj = MeshBuilder._create_single_mesh(m, 0, "Test", MagicMock())
        self.assertIsNotNone(obj)

    def test_empty_returns_none(self) -> None:
        m = _mesh()
        obj = MeshBuilder._create_single_mesh(m, 0, "Test", MagicMock())
        self.assertIsNone(obj)


class TestBuildAllMeshes(unittest.TestCase):
    """build_all_meshes end-to-end."""

    def test_empty_bmd(self) -> None:
        bmd = BMD(Version=0x0A, Name="E", Meshes=[])
        self.assertEqual(MeshBuilder.build_all_meshes(bmd), [])

    def test_single_mesh(self) -> None:
        bmd = BMD(Version=0x0A, Name="S", Meshes=[
            _mesh(vertices=[_v() for _ in range(3)], triangles=[_tri()]),
        ])
        self.assertEqual(len(MeshBuilder.build_all_meshes(bmd)), 1)

    def test_three_meshes(self) -> None:
        bmd = BMD(Version=0x0A, Name="M", Meshes=[
            _mesh(vertices=[_v() for _ in range(3)], triangles=[_tri()], texture=i)
            for i in range(3)
        ])
        self.assertEqual(len(MeshBuilder.build_all_meshes(bmd)), 3)

    def test_empty_meshes_skipped(self) -> None:
        bmd = BMD(Version=0x0A, Name="Mix", Meshes=[
            _mesh(vertices=[_v() for _ in range(3)], triangles=[_tri()]),
            _mesh(),  # empty → skip
            _mesh(vertices=[_v() for _ in range(3)], triangles=[_tri()]),
        ])
        self.assertEqual(len(MeshBuilder.build_all_meshes(bmd)), 2)

    def test_no_uv_no_normal(self) -> None:
        """Mesh without UVs or normals still creates an object."""
        bmd = BMD(Version=0x0A, Name="N", Meshes=[
            _mesh(vertices=[_v() for _ in range(3)], triangles=[_tri()]),
        ])
        self.assertEqual(len(MeshBuilder.build_all_meshes(bmd)), 1)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
