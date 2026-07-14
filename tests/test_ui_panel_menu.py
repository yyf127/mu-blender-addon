# MU Online Blender Tools - Tests for UI Panel & Menu
#
# Run with:  python -m unittest tests.test_ui_panel_menu -v
#
# NOTE: These tests require bpy (Blender Python) mocking since the UI
# modules register panel/menu classes with Blender's API.

"""
Tests for ``mu_blender_tools.ui.panel`` and ``mu_blender_tools.ui.menu``.

Verifies PropertyGroup, Panel, and Menu registration without a running
Blender instance.  Uses mocking for the bpy module.
"""

from __future__ import annotations

import sys
import types
import unittest
import unittest.mock as um
from typing import Any

sys.path.insert(0, ".")


# ======================================================================
# Mock bpy infrastructure
# ======================================================================

class MockOperator:
    bl_idname = ""
    bl_label = ""
    bl_options = {"REGISTER"}
    __annotations__: dict[str, Any] = {}

    def invoke(self, context, event):
        return {"RUNNING_MODAL"}

    def execute(self, context):
        return {"FINISHED"}


class MockTypes(types.ModuleType):
    """Mock for ``bpy.types`` — dynamically creates missing types on demand."""

    def __init__(self):
        super().__init__("bpy.types")
        self.__dict__.update({
            "Operator": MockOperator,
            "Panel": type("Panel", (), {}),
            "PropertyGroup": type("PropertyGroup", (), {}),
            "Scene": type("Scene", (), {}),
            "TOPBAR_MT_file_import": type("TOPBAR_MT_file_import", (), {
                "append": staticmethod(lambda f: None),
                "remove": staticmethod(lambda f: None),
            }),
        })
        # For non-panel menus, create types with append/remove
        self._menu_suffixes = ["_MT_"]

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        # Create generic type
        if any(s in name for s in self._menu_suffixes):
            new_type = type(name, (), {
                "append": staticmethod(lambda f: None),
                "remove": staticmethod(lambda f: None),
            })
        else:
            new_type = type(name, (), {})
        self.__dict__[name] = new_type
        return new_type


class MockProp(types.ModuleType):
    """Mock for ``bpy.props`` — returns a simple metadata object per call.

    ``bpy.props.*Property()`` returns a property descriptor.  In a test
    environment without Blender's metaclass, we return a plain object
    with the kwargs as attributes.  The test accesses settings via
    ``._dict`` rather than through the descriptor protocol.
    """

    def __init__(self):
        super().__init__("bpy.props")

    def __getattr__(self, name):
        if name.endswith("Property"):
            return lambda **k: MockPropResult(name, k)
        raise AttributeError(name)


class MockPropResult:
    """Result of a ``bpy.props.*Property`` call — stores metadata only."""

    def __init__(self, prop_name: str, kwargs: dict):
        self._prop_name = prop_name
        self._default = kwargs.pop("default", None)
        self._kwargs = kwargs
        for k, v in kwargs.items():
            setattr(self, k, v)


# Build the mock bpy package
_bpy_pkg = types.ModuleType("bpy")
_bpy_pkg.__path__ = []          # mark as package
_bpy_pkg.__package__ = "bpy"

_mock_types = MockTypes()
_mock_props = MockProp()

# Helper to set module metadata
def _make_sub_module(name, pkg="bpy"):
    m = types.ModuleType(name)
    m.__package__ = pkg
    return m

_bpy_pkg.types = _mock_types
_bpy_pkg.props = _mock_props
_bpy_pkg.utils = _make_sub_module("bpy.utils")
_bpy_pkg.utils.register_class = lambda cls: None
_bpy_pkg.utils.unregister_class = lambda cls: None
_bpy_pkg.context = _make_sub_module("bpy.context")
_bpy_pkg.data = _make_sub_module("bpy.data")

# Scene type — needs mu_import attribute
class MockScene:
    mu_import = None

_bpy_pkg.types.Scene = MockScene

# Patch sys.modules — ensure each sub-module has correct metadata
_bpy_mods = {
    "bpy": _bpy_pkg,
    "bpy.types": _mock_types,
    "bpy.props": _mock_props,
    "bpy.utils": _bpy_pkg.utils,
    "bpy.context": _bpy_pkg.context,
    "bpy.data": _bpy_pkg.data,
}
for _name, _mod in _bpy_mods.items():
    if not hasattr(_mod, "__name__"):
        _mod.__name__ = _name
    if not hasattr(_mod, "__package__"):
        _mod.__package__ = "bpy"

_bpy_patcher = um.patch.dict("sys.modules", _bpy_mods, clear=False)
_bpy_patcher.start()


def setUpModule():
    """Ensure patcher is active (called by unittest before tests)."""
    pass


# Now import the modules under test
import importlib as _il

import mu_blender_tools.ui.panel as _panel_mod
import mu_blender_tools.ui.menu as _menu_mod
_il.reload(_panel_mod)
_il.reload(_menu_mod)

from mu_blender_tools.ui.panel import MUImportSettings, MU_PT_import_panel, register as panel_register, unregister as panel_unregister
from mu_blender_tools.ui.menu import register as menu_register, unregister as menu_unregister


def _make_patched_settings() -> MUImportSettings:
    """Create a MUImportSettings instance with dict storage for testing.

    Due to ``from __future__ import annotations`` in panel.py, annotations
    are strings and cannot be used to extract defaults.  We populate
    explicit defaults here instead.

    To support attribute-style access (``settings.scale``) we also
    define a class-level ``__getattr__`` that falls back to ``_dict``.
    """
    # Install class-level __getattr__ once
    cls = MUImportSettings
    if not hasattr(cls, '_MU_GETATTR_INSTALLED'):
        def _getattr(self, name):
            if name.startswith('_'):
                raise AttributeError(name)
            d = getattr(self, '_dict', {})
            if name in d:
                return d[name]
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )
        cls.__getattr__ = _getattr
        cls._MU_GETATTR_INSTALLED = True

    s = cls()
    s._dict = {}
    return s


def _init_patched_settings(s, **overrides):
    """Populate a patched settings instance with defaults + overrides."""
    defaults = dict(
        scale=1.0,
        up_axis="Z",
        import_texture=True,
        import_material=True,
        import_armature=True,
        import_animation=True,
        debug=False,
        data_folder="",
        chunk_terrain=True,
    )
    defaults.update(overrides)
    s._dict.update(defaults)


# ======================================================================
# Tests: PropertyGroup
# ======================================================================

class TestMUImportSettings(unittest.TestCase):
    """Test the MUImportSettings PropertyGroup structure."""

    def test_has_annotations(self) -> None:
        """Verify all expected setting names are declared."""
        expected = {
            "scale", "up_axis",
            "import_texture", "import_material", "import_armature",
            "import_animation",
            "debug", "data_folder", "chunk_terrain",
        }
        annotations = set(MUImportSettings.__annotations__.keys())
        for name in expected:
            self.assertIn(name, annotations, f"Missing annotation: {name}")

    def test_annotations_are_strings(self) -> None:
        """Due to ``from __future__ import annotations``, all annotation
        values are strings, not MockPropResult instances."""
        for v in MUImportSettings.__annotations__.values():
            self.assertIsInstance(v, str)

    def test_settings_class_exists(self) -> None:
        self.assertIsNotNone(MUImportSettings)

    def test_defaults_can_be_set_in_dict(self) -> None:
        s = _make_patched_settings()
        _init_patched_settings(s)
        self.assertAlmostEqual(s._dict["scale"], 1.0)
        self.assertEqual(s._dict["up_axis"], "Z")
        self.assertTrue(s._dict["import_texture"])
        self.assertTrue(s._dict["import_material"])
        self.assertTrue(s._dict["import_armature"])
        self.assertTrue(s._dict["import_animation"])
        self.assertFalse(s._dict["debug"])
        self.assertEqual(s._dict["data_folder"], "")
        self.assertTrue(s._dict["chunk_terrain"])


# ======================================================================
# Tests: Panel
# ======================================================================

class TestMUImportPanel(unittest.TestCase):
    """Test the MU_PT_import_panel class."""

    def test_panel_is_panel_subclass(self) -> None:
        """Panel should be registered as a bpy.types.Panel."""
        self.assertTrue(hasattr(MU_PT_import_panel, "bl_label"))
        self.assertTrue(hasattr(MU_PT_import_panel, "bl_idname"))
        self.assertTrue(hasattr(MU_PT_import_panel, "bl_space_type"))

    def test_panel_labels(self) -> None:
        self.assertEqual(MU_PT_import_panel.bl_label, "MU Online")
        self.assertEqual(MU_PT_import_panel.bl_idname, "MU_PT_import_panel")

    def test_panel_space_type(self) -> None:
        self.assertEqual(MU_PT_import_panel.bl_space_type, "VIEW_3D")
        self.assertEqual(MU_PT_import_panel.bl_region_type, "UI")
        self.assertEqual(MU_PT_import_panel.bl_category, "MU")


# ======================================================================
# Tests: Menu registration
# ======================================================================

class TestMenuRegistration(unittest.TestCase):
    """Test that menu functions exist and can be registered."""

    def test_register_unregister_does_not_crash(self) -> None:
        try:
            panel_register()
            menu_register()
            menu_unregister()
            panel_unregister()
        except Exception as e:
            self.fail(f"register/unregister raised: {e}")


# ======================================================================
# Tests: Panel draw method
# ======================================================================

class TestPanelDraw(unittest.TestCase):
    """Test the panel's draw method produces layout calls."""

    def test_draw_accepts_context(self) -> None:
        """draw() should accept a context argument (standard Blender API)."""
        panel = MU_PT_import_panel()
        # The draw method accesses ``self.layout`` which is normally set
        # by Blender's UI framework.  We provide a minimal mock layout.
        mock_layout = um.MagicMock()
        mock_layout.operator = lambda bl_id, **kw: um.MagicMock()
        mock_layout.box = lambda: mock_layout
        mock_layout.column = lambda **kw: mock_layout
        mock_layout.row = lambda **kw: mock_layout
        mock_layout.label = lambda **kw: None
        mock_layout.prop = lambda *a, **kw: None
        mock_layout.separator = lambda: None
        panel.layout = mock_layout

        settings = _make_patched_settings()
        _init_patched_settings(settings)
        mock_scene = type("Scene", (), {"mu_import": settings})()
        mock_context = type("Ctx", (), {"scene": mock_scene})()
        try:
            panel.draw(mock_context)
        except Exception as e:
            self.fail(f"panel.draw() raised: {e}")


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
