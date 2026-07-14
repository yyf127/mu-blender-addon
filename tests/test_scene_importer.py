# MU Online Blender Tools - Tests for Scene Importer
#
# Run with:  python -m unittest tests.test_scene_importer -v
#
# NOTE: SceneImporter requires bpy (Blender Python). These tests use mocking
# to verify the import pipeline logic without a running Blender instance.

"""
Tests for ``mu_blender_tools.operators.scene_importer``.

Verifies file discovery, pipeline orchestration, and operator
registration.
"""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, PropertyMock, patch
from typing import Any

sys.path.insert(0, ".")


# ======================================================================
# Mock bpy infrastructure
# ======================================================================

class MockObject:
    def __init__(self, name: str = "Object", data: Any = None) -> None:
        self.name = name
        self.data = data
        self.parent = None
        self.location = (0.0, 0.0, 0.0)
        self.rotation_euler = (0.0, 0.0, 0.0)
        self.scale = (1.0, 1.0, 1.0)
        self.empty_display_size = 1.0
        self.empty_display_type = "PLAIN_AXES"

    def __setitem__(self, key, value):
        pass


class MockMesh:
    def __init__(self, name: str = "Mesh") -> None:
        self.name = name
        self.materials: list[Any] = []
        self.user_data: dict[str, Any] = {}
        self.vertices = MagicMock()
        self.loops = MagicMock()
        self.polygons = MagicMock()
        self.uv_layers = MagicMock()
        self.uv_layers.new.return_value = MagicMock()

    def validate(self):
        pass

    def update(self):
        pass

    def normals_split_custom_set(self, normals):
        pass


class MockMaterial:
    def __init__(self, name: str = "Material") -> None:
        self.name = name

    def __setitem__(self, key, value):
        pass


class MockSceneChildren:
    def __init__(self):
        self._items: list[Any] = []

    def link(self, col):
        self._items.append(col)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __contains__(self, item):
        return item in self._items


class MockCollection:
    def __init__(self, name: str = "Collection") -> None:
        self.name = name
        self.children = MockSceneChildren()
        self.objects: list[Any] = []

    def link(self, obj):
        self.objects.append(obj)


class MockCollections:
    def __init__(self):
        self._store: dict[str, MockCollection] = {}

    def new(self, name):
        col = MockCollection(name)
        self._store[name] = col
        return col

    def get(self, name):
        return self._store.get(name)


class MockMeshes:
    def __init__(self):
        self._store: dict[str, MockMesh] = {}

    def new(self, name):
        mesh = MockMesh(name)
        self._store[name] = mesh
        return mesh


class MockObjects:
    def __init__(self):
        self._store: dict[str, MockObject] = {}

    def new(self, name, data):
        obj = MockObject(name, data)
        self._store[name] = obj
        return obj


class MockMaterials:
    def __init__(self):
        self._store: dict[str, MockMaterial] = {}

    def new(self, name):
        mat = MockMaterial(name)
        self._store[name] = mat
        return mat

    def get(self, name):
        return self._store.get(name)


class MockBpyData:
    def __init__(self):
        self.collections = MockCollections()
        self.meshes = MockMeshes()
        self.objects = MockObjects()
        self.materials = MockMaterials()


class MockProgress:
    def begin(self, a, b):
        pass

    def end(self):
        pass

    def update(self, v):
        pass


class MockWindowManager:
    def __init__(self):
        self.progress = MockProgress()
        self.fileselect_add = MagicMock()


class MockViewLayer:
    pass


class MockScene:
    def __init__(self):
        self.collection = MagicMock()
        self.collection.children = MockSceneChildren()


class MockContext:
    def __init__(self):
        self.window_manager = MockWindowManager()
        self.view_layer = MagicMock()
        self.view_layer.active_layer_collection = None
        self.scene = MockScene()


class MockOperator:
    """Mock for ``bpy.types.Operator`` — acts as a proper base class.

    Subclasses define ``bl_idname``, ``bl_label`` etc. as class variables.
    The default ``invoke`` shows a file browser; ``execute`` returns
    ``{'FINISHED'}``.
    """
    bl_idname = ""
    bl_label = ""
    bl_description = ""
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        pass


class MockTypes(types.ModuleType):
    """Mock for ``bpy.types`` — supports any attribute so all builders can import.

    Inherits from ModuleType so ``from bpy.types import X`` works.
    All types are stored in the module's ``__dict__``.
    """

    def __init__(self):
        super().__init__("bpy.types")
        # Populate __dict__ with common Blender types
        self.__dict__.update({
            "Collection": type("Collection", (), {}),
            "Context": type("Context", (), {}),
            "Image": type("Image", (), {}),
            "Material": type("Material", (), {}),
            "Mesh": type("Mesh", (), {}),
            "Object": type("Object", (), {}),
            "Operator": MockOperator,
        })

    def __getattr__(self, name):
        """Dynamically create and cache missing types.

        Menu classes (``TOPBAR_MT_*``, ``VIEW3D_MT_*``) are given
        an ``append`` classmethod for registering menu items.
        """
        if name.startswith("_"):
            raise AttributeError(name)

        # Menu types get an ``append`` method
        if "_MT_" in name:
            new_type = type(name, (), {
                "append": staticmethod(lambda func: None),
                "remove": staticmethod(lambda func: None),
                "prepend": staticmethod(lambda func: None),
            })
        else:
            new_type = type(name, (), {})

        self.__dict__[name] = new_type
        return new_type


def mock_string_property(**kwargs):
    """Mock ``bpy.props.StringProperty`` returns a descriptor-like object."""
    return PropertyMock(**kwargs)


def mock_int_property(**kwargs):
    return PropertyMock(**kwargs)


def mock_bool_property(**kwargs):
    return PropertyMock(**kwargs)


class MockProps(types.ModuleType):
    """Mock for ``bpy.props`` — supports ``from bpy.props import X`` for any ``X`` ending in ``Property``."""

    def __init__(self):
        super().__init__("bpy.props")
        # Pre-define common property types
        for name in ["StringProperty", "IntProperty", "BoolProperty",
                      "FloatProperty", "PointerProperty", "EnumProperty"]:
            setattr(self, name, lambda **k: MockPropResult(name, k))

    def __getattr__(self, name):
        if name.endswith("Property"):
            return lambda **k: MockPropResult(name, k)
        raise AttributeError(name)


class MockBpy:
    def __init__(self):
        self.data = MockBpyData()
        self.context = MockContext()
        self.types = MockTypes()
        self.utils = MagicMock()
        self.props = MockProps()


# Build the mock bpy package that will be injected into sys.modules.
_bpy_pkg = types.ModuleType("bpy")
_bpy_pkg.__path__ = []  # mark as package so sub-modules can be found

_bpy_mock = MockBpy()
_bpy_pkg.data = _bpy_mock.data
_bpy_pkg.context = _bpy_mock.context
_bpy_pkg.types = _bpy_mock.types
_bpy_pkg.utils = _bpy_mock.utils
_bpy_pkg.props = _bpy_mock.props

# Use a patcher so the mocks are properly cleaned up after all tests.
import unittest.mock as _umock
_bpy_patcher = _umock.patch.dict("sys.modules", {
    "bpy": _bpy_pkg,
    "bpy.types": _bpy_mock.types,
    "bpy.context": _bpy_mock.context,
    "bpy.data": _bpy_mock.data,
    "bpy.utils": _bpy_mock.utils,
    "bpy.props": _bpy_mock.props,
}, clear=False)
_bpy_patcher.start()


# Now import the module under test.
# Force a reload so the class definition picks up our mocks.
import mu_blender_tools.operators.scene_importer as _si_mod
import importlib
importlib.reload(_si_mod)

from mu_blender_tools.operators.scene_importer import (
    MU_OT_import_world,
    _scan_available_worlds,
    _find_file,
    _find_object_bmd,
    _make_bmd_loader,
    register,
    unregister,
)


# ======================================================================
# Tests: File discovery
# ======================================================================

class TestScanAvailableWorlds(unittest.TestCase):
    """Test world folder scanning."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = self.tmpdir.name

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_empty_directory(self) -> None:
        worlds = _scan_available_worlds(self.data_dir)
        self.assertEqual(worlds, [])

    def test_detects_world_folders(self) -> None:
        for i in [0, 1, 3]:
            os.makedirs(os.path.join(self.data_dir, f"World{i}"))
        worlds = _scan_available_worlds(self.data_dir)
        self.assertEqual(worlds, [0, 1, 3])

    def test_detects_lowercase_world_folders(self) -> None:
        os.makedirs(os.path.join(self.data_dir, "world0"))
        os.makedirs(os.path.join(self.data_dir, "world10"))
        worlds = _scan_available_worlds(self.data_dir)
        self.assertEqual(worlds, [0, 10])

    def test_ignores_non_world_folders(self) -> None:
        os.makedirs(os.path.join(self.data_dir, "World0"))
        os.makedirs(os.path.join(self.data_dir, "Data"))
        os.makedirs(os.path.join(self.data_dir, "Textures"))
        worlds = _scan_available_worlds(self.data_dir)
        self.assertEqual(worlds, [0])


class TestFindFile(unittest.TestCase):
    """Test terrain file discovery."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = self.tmpdir.name

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_finds_existing_file(self) -> None:
        world_dir = os.path.join(self.data_dir, "World1")
        os.makedirs(world_dir)
        open(os.path.join(world_dir, "EncTerrain1.att"), "w").close()

        path = _find_file(self.data_dir, 1, "EncTerrain1.att")
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isfile(path))

    def test_returns_none_for_missing_file(self) -> None:
        path = _find_file(self.data_dir, 999, "nonexistent.att")
        self.assertIsNone(path)

    def test_finds_lowercase_world_dir(self) -> None:
        world_dir = os.path.join(self.data_dir, "world0")
        os.makedirs(world_dir)
        open(os.path.join(world_dir, "TerrainHeight.OZB"), "w").close()

        path = _find_file(self.data_dir, 0, "TerrainHeight.OZB")
        self.assertIsNotNone(path)


class TestFindObjectBMD(unittest.TestCase):
    """Test BMD model file discovery."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = self.tmpdir.name

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_finds_object_bmd(self) -> None:
        obj_dir = os.path.join(self.data_dir, "Object1")
        os.makedirs(obj_dir)
        open(os.path.join(obj_dir, "Object01.bmd"), "w").close()

        path = _find_object_bmd(self.data_dir, 1, "Object1/Object01.bmd")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith("Object01.bmd"))

    def test_returns_none_for_missing_bmd(self) -> None:
        path = _find_object_bmd(self.data_dir, 1, "Object1/Missing.bmd")
        self.assertIsNone(path)


# ======================================================================
# Tests: Operator
# ======================================================================

class TestOperatorRegistration(unittest.TestCase):
    """Test operator registration/unregistration."""

    def test_register_unregister(self) -> None:
        """Should not crash."""
        try:
            register()
            unregister()
        except Exception as e:
            self.fail(f"register/unregister raised: {e}")

    def test_bl_idname(self) -> None:
        self.assertEqual(MU_OT_import_world.bl_idname, "mu.import_world")

    def test_bl_label(self) -> None:
        self.assertEqual(MU_OT_import_world.bl_label, "Import MU World")

    def test_operator_properties(self) -> None:
        op = MU_OT_import_world
        # ``bl_idname`` and ``bl_label`` are plain class attributes (set with
        # ``=``), so they are always accessible.
        self.assertEqual(op.bl_idname, "mu.import_world")
        self.assertEqual(op.bl_label, "Import MU World")
        self.assertEqual(op.bl_description,
                         "Import an entire MU Online world from the Data directory")
        self.assertTrue("UNDO" in op.bl_options or "REGISTER" in op.bl_options)

        # ``directory`` etc. are defined via ``bpy.props.StringProperty(...)``
        # using the annotation syntax.  In real Blender the metaclass lifts
        # these from ``__annotations__`` during registration; in our mock
        # they are not stored as class attributes without the metaclass.
        # We verify they exist in ``__annotations__`` instead.
        self.assertIn("directory", MU_OT_import_world.__annotations__)
        self.assertIn("world_number", MU_OT_import_world.__annotations__)
        self.assertIn("import_terrain", MU_OT_import_world.__annotations__)


class TestOperatorInvoke(unittest.TestCase):
    """Test operator invoke shows file browser."""

    def setUp(self) -> None:
        self.op = MU_OT_import_world()
        self.ctx = _bpy_mock.context

    def test_invoke_opens_file_browser(self) -> None:
        result = self.op.invoke(self.ctx, None)
        self.assertIn("RUNNING_MODAL", result)
        self.ctx.window_manager.fileselect_add.assert_called_once()


# ======================================================================
# Tests: BMD loader creation
# ======================================================================

class TestBMDLoaderFactory(unittest.TestCase):
    """Test the BMD loader callback factory."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = self.tmpdir.name

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_loader_created(self) -> None:
        loader = _make_bmd_loader(self.data_dir, 0)
        self.assertTrue(callable(loader))

    def test_loader_returns_none_for_missing_bmd(self) -> None:
        loader = _make_bmd_loader(self.data_dir, 0)
        col = MockCollection()
        result = loader("Object0/Missing.bmd", col)
        self.assertIsNone(result)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
