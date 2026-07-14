# MU Online Blender Tools - Tests for World Builder
#
# Run with:  python -m unittest tests.test_world_builder -v
#
# NOTE: WorldBuilder requires bpy (Blender Python). These tests use mocking
# to verify the builder logic without a running Blender instance.

"""
Tests for ``mu_blender_tools.builders.world_builder.WorldBuilder``.

Uses ``unittest.mock`` to simulate Blender's bpy module.
"""

from __future__ import annotations

import math
import sys
import unittest
from unittest.mock import MagicMock, patch, call
from typing import Any

sys.path.insert(0, ".")


# ======================================================================
# Mock bpy infrastructure BEFORE importing WorldBuilder
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
        self.materials: list[Any] = []

    def validate(self) -> None:
        pass

    def update(self) -> None:
        pass

    def normals_split_custom_set(self, normals: Any) -> None:
        pass


class MockCollection:
    """Mimics bpy.types.Collection for testing."""
    def __init__(self, name: str = "Collection") -> None:
        self.name = name
        self.children = MockCollectionChildren()
        self.objects = MockObjectList()

    def link(self, obj: Any) -> None:
        self.objects.link(obj)


class MockObject:
    """Mimics bpy.types.Object for testing."""
    def __init__(self, name: str = "Object", mesh_data: Any = None) -> None:
        self.name = name
        self.data = mesh_data
        self.location = (0.0, 0.0, 0.0)
        self.rotation_euler = (0.0, 0.0, 0.0)
        self.scale = (1.0, 1.0, 1.0)
        self.empty_display_size = 1.0
        self.empty_display_type = "PLAIN_AXES"
        self.__custom_properties: dict[str, Any] = {}

    def __setitem__(self, key: str, value: Any) -> None:
        self.__custom_properties[key] = value

    def __getitem__(self, key: str) -> Any:
        return self.__custom_properties[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.__custom_properties.get(key, default)


class MockMaterial:
    """Mimics bpy.types.Material."""
    def __init__(self, name: str = "Material") -> None:
        self.name = name


class MockCollections:
    """Mimics ``bpy.data.collections`` with ``.new()`` and ``.get()``."""
    def __init__(self) -> None:
        self._store: dict[str, MockCollection] = {}

    def new(self, name: str) -> MockCollection:
        col = MockCollection(name)
        self._store[name] = col
        return col

    def get(self, name: str) -> Any:
        return self._store.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._store


class MockMeshes:
    """Mimics ``bpy.data.meshes`` with ``.new()``."""
    def __init__(self) -> None:
        self._store: dict[str, MockMesh] = {}

    def new(self, name: str) -> MockMesh:
        mesh = MockMesh(name)
        self._store[name] = mesh
        return mesh


class MockObjects:
    """Mimics ``bpy.data.objects`` with ``.new()``."""
    def __init__(self) -> None:
        self._store: dict[str, MockObject] = {}

    def new(self, name: str, data: Any) -> MockObject:
        obj = MockObject(name, data)
        self._store[name] = obj
        return obj


class MockMaterials:
    """Mimics ``bpy.data.materials`` with ``.new()`` and ``.get()``."""
    def __init__(self) -> None:
        self._store: dict[str, MockMaterial] = {}

    def new(self, name: str) -> MockMaterial:
        mat = MockMaterial(name)
        self._store[name] = mat
        return mat

    def get(self, name: str) -> Any:
        return self._store.get(name)


class MockBpyData:
    """Mimics ``bpy.data`` for testing."""
    def __init__(self) -> None:
        self.collections = MockCollections()
        self.meshes = MockMeshes()
        self.objects = MockObjects()
        self.materials = MockMaterials()


class MockSceneChildren:
    """Mimics ``Collection.children`` — supports ``.link()``."""
    def __init__(self) -> None:
        self._items: list[Any] = []

    def link(self, col: Any) -> None:
        self._items.append(col)

    def __contains__(self, item: Any) -> bool:
        return item in self._items

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


class MockCollectionChildren(MockSceneChildren):
    """Same as MockSceneChildren but for nested collections."""
    pass


class MockObjectList:
    """Mimics ``Collection.objects`` — supports ``.link()``."""
    def __init__(self) -> None:
        self._items: list[Any] = []

    def link(self, obj: Any) -> None:
        self._items.append(obj)

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, item: Any) -> bool:
        return item in self._items


class MockBpyContextSceneCollection:
    """Mimics ``bpy.context.scene.collection``."""
    def __init__(self) -> None:
        self.children = MockSceneChildren()

    def link(self, col: Any) -> None:
        self.children.link(col)


class MockBpyContext:
    """Mimics ``bpy.context`` for testing."""
    def __init__(self) -> None:
        self.scene = MagicMock()
        self.scene.collection = MockBpyContextSceneCollection()


class MockBpy:
    """Mock the ``bpy`` module."""
    def __init__(self) -> None:
        self.data = MockBpyData()
        self.context = MockBpyContext()


# Patch bpy BEFORE importing the module under test.
_bpy_mock = MockBpy()
_modules_patch = {
    "bpy": _bpy_mock,
    "bpy.types": MagicMock(),
    "bpy.context": _bpy_mock.context,
    "bpy.data": _bpy_mock.data,
}
_bpy_patcher = patch.dict("sys.modules", _modules_patch, clear=False)
_bpy_patcher.start()


def _reset_bpy():
    """Reset the shared mock bpy to a clean state between tests."""
    _bpy_mock.data = MockBpyData()
    _bpy_mock.context = MockBpyContext()
    _bpy_mock.context.scene.collection = MockBpyContextSceneCollection()
    # Re-patch the changed attributes
    import sys
    sys.modules["bpy.data"] = _bpy_mock.data
    sys.modules["bpy.context"] = _bpy_mock.context
    sys.modules["bpy"].data = _bpy_mock.data
    sys.modules["bpy"].context = _bpy_mock.context

from mu_blender_tools.builders.world_builder import (
    WorldBuilder,
    WORLD_COLLECTION_NAME,
    TERRAIN_COLLECTION_NAME,
    OBJECTS_COLLECTION_NAME,
    NPC_COLLECTION_NAME,
    MONSTER_COLLECTION_NAME,
    EFFECTS_COLLECTION_NAME,
    LIGHTS_COLLECTION_NAME,
    WATER_COLLECTION_NAME,
    MU_WORLD_SIZE,
)
from mu_blender_tools.readers.world_reader import (
    WorldObjectCategory,
    WorldData,
    WorldObject,
    WorldLight,
    WorldWater,
    WorldEffect,
    WorldNPC,
    WorldMonster,
)
from mu_blender_tools.builders.terrain_builder import (
    TerrainBuilderOutput,
    TerrainChunkMesh,
    TerrainVertex,
)


# ======================================================================
# Helpers
# ======================================================================

def _make_world_data(
    objects: list[tuple[int, float, float, float,
                         float, float, float, float]] | None = None,
) -> WorldData:
    """Create a minimal WorldData from object tuples."""
    data = WorldData(map_number=1)
    if objects:
        for t, px, py, pz, ax, ay, az, sc in objects:
            data.objects.append(WorldObject(
                type=t,
                category=WorldObjectCategory.Object,
                position_x=px, position_y=py, position_z=pz,
                angle_x=ax, angle_y=ay, angle_z=az,
                scale=sc,
                name=f"Obj{t:02d}",
                model_path=f"Object1/Object{t+1:02d}.bmd",
            ))
    return data


# ======================================================================
# Tests: Coordinate conversion
# ======================================================================

class TestCoordinateConversion(unittest.TestCase):
    """Test MU→Blender coordinate mapping."""

    def setUp(self) -> None:
        _reset_bpy()

    def test_origin(self) -> None:
        bx, by, bz = WorldBuilder._mu_to_blender_position(0, 0, 0)
        self.assertEqual(bx, 0.0)
        self.assertEqual(by, MU_WORLD_SIZE)  # world_size - 0
        self.assertEqual(bz, 0.0)

    def test_mu_y_becomes_blender_y_mirrored(self) -> None:
        bx, by, bz = WorldBuilder._mu_to_blender_position(100, 50, 30)
        expected_by = MU_WORLD_SIZE - 50
        self.assertAlmostEqual(by, expected_by)

    def test_mu_z_is_height(self) -> None:
        bx, by, bz = WorldBuilder._mu_to_blender_position(0, 0, 100)
        self.assertEqual(bz, 100.0)

    def test_angle_conversion(self) -> None:
        rx, ry, rz = WorldBuilder._mu_angle_to_blender_rotation(90, 45, 180)
        self.assertAlmostEqual(rx, math.pi / 2)
        self.assertAlmostEqual(ry, math.pi / 4)
        self.assertAlmostEqual(rz, math.pi)


# ======================================================================
# Tests: Collection creation
# ======================================================================

class TestCollectionCreation(unittest.TestCase):
    """Test collection hierarchy creation."""

    def setUp(self) -> None:
        _reset_bpy()
        self.builder = WorldBuilder(_make_world_data())

    def test_root_collection_created(self) -> None:
        self.builder.build()
        root = self.builder.root_collection
        self.assertIsNotNone(root)
        self.assertEqual(root.name, WORLD_COLLECTION_NAME)

    def test_all_sub_collections_created(self) -> None:
        self.builder.build()
        expected = [
            TERRAIN_COLLECTION_NAME,
            OBJECTS_COLLECTION_NAME,
            NPC_COLLECTION_NAME,
            MONSTER_COLLECTION_NAME,
            EFFECTS_COLLECTION_NAME,
            LIGHTS_COLLECTION_NAME,
            WATER_COLLECTION_NAME,
        ]
        for name in expected:
            self.assertIn(name, self.builder.collections, f"Missing {name}")

    def test_collections_are_nested(self) -> None:
        self.builder.build()
        root = self.builder.root_collection
        child_names = [c.name for c in root.children]
        for name, col in self.builder.collections.items():
            if col is not root:
                self.assertIn(name, child_names)


# ======================================================================
# Tests: Object placement
# ======================================================================

class TestObjectPlacement(unittest.TestCase):
    """Test world object creation."""

    def setUp(self) -> None:
        _reset_bpy()
        self.data = _make_world_data([
            (0, 100, 200, 30, 10, 20, 0, 1.5),
            (5, 300, 400, 50, 0, 90, 0, 2.0),
        ])
        self.builder = WorldBuilder(self.data)
        self.builder.build()

    def test_objects_created(self) -> None:
        self.assertEqual(len(self.builder.created_objects), 2)

    def test_object_position_mapped(self) -> None:
        obj = self.builder.created_objects[0]
        expected_y = MU_WORLD_SIZE - 200
        self.assertAlmostEqual(obj.location[0], 100)
        self.assertAlmostEqual(obj.location[1], expected_y)
        self.assertAlmostEqual(obj.location[2], 30)

    def test_object_rotation_converted(self) -> None:
        obj = self.builder.created_objects[1]
        self.assertAlmostEqual(obj.rotation_euler[1], math.radians(90))

    def test_object_scale(self) -> None:
        obj = self.builder.created_objects[0]
        self.assertAlmostEqual(obj.scale[0], 1.5)

    def test_custom_properties(self) -> None:
        obj = self.builder.created_objects[0]
        self.assertEqual(obj["mu_type"], 0)
        self.assertEqual(obj["mu_name"], "Obj00")
        self.assertIn("Object1/Object01.bmd", obj["mu_model_path"])

    def test_object_placed_in_objects_collection(self) -> None:
        col = self.builder.collections[OBJECTS_COLLECTION_NAME]
        self.assertEqual(len(col.objects), 2)


# ======================================================================
# Tests: Category routing
# ======================================================================

class TestCategoryRouting(unittest.TestCase):
    """Test objects routed to correct collections by category."""

    def setUp(self) -> None:
        _reset_bpy()
        data = WorldData(map_number=1)
        # One object of each category
        data.objects.append(WorldObject(
            type=0, category=WorldObjectCategory.Object,
            position_x=0, position_y=0, position_z=0,
            name="Obj", model_path="",
        ))
        data.objects.append(WorldObject(
            type=90, category=WorldObjectCategory.Light,
            position_x=0, position_y=0, position_z=0,
            name="Light", model_path="",
        ))
        data.objects.append(WorldObject(
            type=105, category=WorldObjectCategory.Water,
            position_x=0, position_y=0, position_z=0,
            name="Water", model_path="",
        ))
        data.objects.append(WorldObject(
            type=50, category=WorldObjectCategory.Effect,
            position_x=0, position_y=0, position_z=0,
            name="Effect", model_path="",
        ))
        data.objects.append(WorldObject(
            type=248, category=WorldObjectCategory.NPC,
            position_x=0, position_y=0, position_z=0,
            name="NPC", model_path="",
        ))
        data.objects.append(WorldObject(
            type=200, category=WorldObjectCategory.Monster,
            position_x=0, position_y=0, position_z=0,
            name="Monster", model_path="",
        ))
        self.builder = WorldBuilder(data)
        self.builder.build()

    def test_object_in_objects_collection(self) -> None:
        col = self.builder.collections[OBJECTS_COLLECTION_NAME]
        self.assertGreater(len(col.objects), 0)

    def test_light_in_lights_collection(self) -> None:
        col = self.builder.collections[LIGHTS_COLLECTION_NAME]
        self.assertEqual(len(col.objects), 1)

    def test_water_in_water_collection(self) -> None:
        col = self.builder.collections[WATER_COLLECTION_NAME]
        self.assertEqual(len(col.objects), 1)

    def test_effect_in_effects_collection(self) -> None:
        col = self.builder.collections[EFFECTS_COLLECTION_NAME]
        self.assertEqual(len(col.objects), 1)

    def test_npc_in_npc_collection(self) -> None:
        col = self.builder.collections[NPC_COLLECTION_NAME]
        self.assertEqual(len(col.objects), 1)

    def test_monster_in_monster_collection(self) -> None:
        col = self.builder.collections[MONSTER_COLLECTION_NAME]
        self.assertEqual(len(col.objects), 1)


# ======================================================================
# Tests: Terrain building
# ======================================================================

class TestTerrainBuilding(unittest.TestCase):
    """Test terrain mesh generation from TerrainBuilderOutput."""

    def setUp(self) -> None:
        _reset_bpy()
        # Create a minimal terrain chunk
        verts = [
            TerrainVertex(x=0, y=0, z=0, uv_u=0, uv_v=0),
            TerrainVertex(x=100, y=0, z=0, uv_u=1, uv_v=0),
            TerrainVertex(x=100, y=0, z=100, uv_u=1, uv_v=1),
            TerrainVertex(x=0, y=0, z=100, uv_u=0, uv_v=1),
        ]
        # Use a helper to create faces with proper attributes
        from mu_blender_tools.builders.terrain_builder import TerrainFace
        faces = [
            TerrainFace(v0=0, v1=1, v2=3, material_index=0),
            TerrainFace(v0=1, v1=2, v2=3, material_index=0),
        ]
        chunk = TerrainChunkMesh(
            vertices=verts,
            faces=faces,
            material_slots=["TestMat"],
        )
        terrain_out = TerrainBuilderOutput(
            chunks=[chunk],
            chunk_size_tiles=8,
            grid_size=256,
        )
        data = _make_world_data()
        self.builder = WorldBuilder(data, terrain_output=terrain_out)
        self.builder.build()

    def test_terrain_chunk_created(self) -> None:
        """Terrain chunk should create a mesh object."""
        col = self.builder.collections[TERRAIN_COLLECTION_NAME]
        self.assertGreater(len(col.objects), 0)

    def test_terrain_object_name(self) -> None:
        obj = self.builder.created_objects[0]  # Terrain is first
        self.assertIn("Terrain", obj.name)


# ======================================================================
# Tests: BMD loader callback
# ======================================================================

class TestBMDLoader(unittest.TestCase):
    """Test optional BMD model importing."""

    def setUp(self) -> None:
        _reset_bpy()

    def test_loader_called_for_each_object(self) -> None:
        loader_calls: list[str] = []

        def fake_loader(path: str, col: Any) -> Any:
            loader_calls.append(path)
            return None  # Simulate failure → fallback to empty

        data = _make_world_data([
            (0, 0, 0, 0, 0, 0, 0, 1.0),
            (1, 100, 0, 0, 0, 0, 0, 1.0),
        ])
        builder = WorldBuilder(data, bmd_loader=fake_loader)
        builder.build()

        # Both objects attempted BMD load
        self.assertEqual(len(loader_calls), 2)
        self.assertTrue(all("Object" in p for p in loader_calls))

    def test_loader_success_creates_object(self) -> None:
        def fake_loader(path: str, col: Any) -> Any:
            obj = MockObject(f"Imported_{path}")
            col.objects.link(obj)
            return obj

        data = _make_world_data([
            (0, 100, 200, 30, 0, 0, 0, 1.0),
        ])
        builder = WorldBuilder(data, bmd_loader=fake_loader)
        builder.build()

        obj = builder.created_objects[0]
        expected_y = MU_WORLD_SIZE - 200
        self.assertAlmostEqual(obj.location[0], 100)
        self.assertAlmostEqual(obj.location[1], expected_y)
        self.assertAlmostEqual(obj.location[2], 30)
        self.assertEqual(obj["mu_type"], 0)


# ======================================================================
# Tests: Empty world
# ======================================================================

class TestEmptyWorld(unittest.TestCase):
    """Test builder with no objects."""

    def setUp(self) -> None:
        _reset_bpy()

    def test_empty_data(self) -> None:
        data = _make_world_data()
        builder = WorldBuilder(data)
        result = builder.build()
        self.assertEqual(len(builder.created_objects), 0)
        self.assertIn(TERRAIN_COLLECTION_NAME, result)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)


