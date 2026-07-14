# MU Online Blender Tools - Tests for MaterialBuilder
#
# Run with:  python -m unittest tests.test_material_builder -v
#
# NOTE: MaterialBuilder requires bpy (Blender Python). These tests use mocking
# to verify the builder logic without a running Blender instance.

"""
Tests for ``mu_blender_tools.builders.material_builder.MaterialBuilder``.

Uses ``unittest.mock`` to simulate Blender's bpy module.
"""

from __future__ import annotations

import sys
import unittest
from typing import Any
from unittest.mock import MagicMock

sys.path.insert(0, ".")


# ======================================================================
# Mock bpy infrastructure BEFORE importing MaterialBuilder
# ======================================================================

class MockImage:
    """Mimics bpy.types.Image."""
    _next_id: int = 0

    def __init__(self, name: str = "Image", width: int = 4, height: int = 4, alpha: bool = True) -> None:
        MockImage._next_id += 1
        self.name = name
        self.size = [width, height]
        self.width = width
        self.height = height
        self.pixels: list[float] = [0.0] * (width * height * 4)
        self.filepath = ""
        self.source = "FILE"


class MockMaterial:
    """Mimics bpy.types.Material."""
    def __init__(self, name: str = "Material") -> None:
        self.name = name
        self.use_nodes = True
        self.node_tree = MockNodeTree()
        self.blend_method = "OPAQUE"
        self.shadow_method = "OPAQUE"
        self.user_data: dict[str, Any] = {}


class MockNode:
    """Mimics a Blender shader node."""
    def __init__(self, type: str = "") -> None:
        self.type = type
        self.location = (0, 0)
        self.inputs = MockNodeInputs()
        self.outputs = MockNodeOutputs()
        self.image: Any = None


class MockNodeInputs:
    """Mimics node inputs."""
    def __init__(self) -> None:
        self._inputs: dict[str, MockSocket] = {}

    def __getitem__(self, key: str) -> MockSocket:
        if key not in self._inputs:
            self._inputs[key] = MockSocket(key)
        return self._inputs[key]

    def new(self, type: str, name: str) -> MockSocket:
        sock = MockSocket(name)
        self._inputs[name] = sock
        return sock


class MockNodeOutputs:
    """Mimics node outputs."""
    def __init__(self) -> None:
        self._outputs: dict[str, MockSocket] = {}

    def __getitem__(self, key: str) -> MockSocket:
        if key not in self._outputs:
            self._outputs[key] = MockSocket(key)
        return self._outputs[key]


class MockSocket:
    """Mimics a node socket."""
    def __init__(self, name: str) -> None:
        self.name = name
        self.default_value: Any = None
        self.links: list[MockLink] = []


class MockLink:
    """Mimics a node link."""
    def __init__(self, from_socket: MockSocket, to_socket: MockSocket) -> None:
        self.from_socket = from_socket
        self.to_socket = to_socket


class MockNodeTree:
    """Mimics bpy.types.NodeTree."""
    def __init__(self) -> None:
        self.nodes = MockNodes()
        self.links = MockLinks()


class MockNodes:
    """Mimics node collection."""
    def __init__(self) -> None:
        self._nodes: list[MockNode] = []

    def new(self, type: str) -> MockNode:
        node = MockNode(type)
        self._nodes.append(node)
        return node

    def remove(self, node: MockNode) -> None:
        if node in self._nodes:
            self._nodes.remove(node)

    def __iter__(self):
        return iter(self._nodes)


class MockLinks:
    """Mimics link collection."""
    def __init__(self) -> None:
        self._links: list[MockLink] = []

    def new(self, from_socket: MockSocket, to_socket: MockSocket) -> MockLink:
        link = MockLink(from_socket, to_socket)
        self._links.append(link)
        return link


class MockBpy:
    """Mock the ``bpy`` module."""
    def __init__(self) -> None:
        self.data = MockBpyData()
        self.context = MagicMock()
        self.types = MagicMock()
        self.types.Material = MockMaterial
        self.types.Image = MockImage


class MockBpyData:
    """Mimics bpy.data."""
    def __init__(self) -> None:
        self.materials = MockMaterials()
        self.images = MockImages()


class MockMaterials:
    """Mimics bpy.data.materials."""
    def __init__(self) -> None:
        self._materials: list[MockMaterial] = []

    def new(self, name: str) -> MockMaterial:
        mat = MockMaterial(name)
        self._materials.append(mat)
        return mat


class MockImages:
    """Mimics bpy.data.images."""
    def __init__(self) -> None:
        self._images: list[MockImage] = []

    def new(self, name: str, width: int, height: int, alpha: bool = True) -> MockImage:
        img = MockImage(name, width, height, alpha)
        self._images.append(img)
        return img


# Patch sys.modules BEFORE importing MaterialBuilder
sys.modules["bpy"] = MockBpy()
sys.modules["bpy.types"] = MagicMock()

from mu_blender_tools.loaders.texture_loader import TextureData
from mu_blender_tools.builders.material_builder import (
    MaterialBuilder,
    _detect_blend_mode,
    _has_emission_hint,
)


# ======================================================================
# Test: _detect_blend_mode
# ======================================================================

class TestDetectBlendMode(unittest.TestCase):
    """Test blend mode detection logic (pure, no bpy needed)."""

    def test_explicit_additive(self) -> None:
        self.assertEqual(_detect_blend_mode("test.jpg", "additive"), "ADD")

    def test_explicit_alpha(self) -> None:
        self.assertEqual(_detect_blend_mode("test.jpg", "alpha"), "BLEND")

    def test_explicit_opaque(self) -> None:
        self.assertEqual(_detect_blend_mode("test.jpg", "opaque"), "OPAQUE")

    def test_suffix_a_means_alpha(self) -> None:
        self.assertEqual(_detect_blend_mode("some_tex_a.jpg"), "BLEND")

    def test_suffix_r_is_opaque(self) -> None:
        self.assertEqual(_detect_blend_mode("some_tex_r.jpg"), "OPAQUE")

    def test_glow_keyword_additive(self) -> None:
        self.assertEqual(_detect_blend_mode("fx_fire_glow.jpg"), "ADD")

    def test_armor_keyword_opaque(self) -> None:
        self.assertEqual(_detect_blend_mode("armor_body.jpg"), "OPAQUE")

    def test_unknown_default_opaque(self) -> None:
        self.assertEqual(_detect_blend_mode("something_random.png"), "OPAQUE")


# ======================================================================
# Test: _has_emission_hint
# ======================================================================

class TestHasEmissionHint(unittest.TestCase):
    """Test emission detection (pure, no bpy needed)."""

    def test_suffix_r_is_emissive(self) -> None:
        self.assertTrue(_has_emission_hint("light_orb_r.jpg"))

    def test_mu_rgb_lights(self) -> None:
        self.assertTrue(_has_emission_hint("mu_rgb_lights.jpg"))

    def test_regular_not_emissive(self) -> None:
        self.assertFalse(_has_emission_hint("armor_body.jpg"))


# ======================================================================
# Test: MaterialBuilder
# ======================================================================

class TestMaterialBuilderCreate(unittest.TestCase):
    """Test material creation with mocked bpy."""

    def setUp(self) -> None:
        self.builder = MaterialBuilder()

    def test_create_opaque_material(self) -> None:
        mat = self.builder.get_or_create_material("test_armor.jpg")
        self.assertIsNotNone(mat)
        self.assertEqual(mat.blend_method, "OPAQUE")

    def test_create_alpha_material(self) -> None:
        mat = self.builder.get_or_create_material("leaf_a.ozt")
        self.assertEqual(mat.blend_method, "BLEND")

    def test_create_additive_material(self) -> None:
        mat = self.builder.get_or_create_material("fire_glow.ozj")
        self.assertEqual(mat.blend_method, "ADD")

    def test_material_has_nodes(self) -> None:
        mat = self.builder.get_or_create_material("test.jpg")
        self.assertTrue(mat.use_nodes)
        self.assertIsNotNone(mat.node_tree)

    def test_cache_returns_same_object(self) -> None:
        mat1 = self.builder.get_or_create_material("test.jpg")
        mat2 = self.builder.get_or_create_material("test.jpg")
        self.assertIs(mat1, mat2)

    def test_different_paths_different_materials(self) -> None:
        mat1 = self.builder.get_or_create_material("test1.jpg")
        mat2 = self.builder.get_or_create_material("test2.jpg")
        self.assertIsNot(mat1, mat2)

    def test_cache_key_case_insensitive(self) -> None:
        mat1 = self.builder.get_or_create_material("Test.JPG")
        mat2 = self.builder.get_or_create_material("test.jpg")
        self.assertIs(mat1, mat2)

    def test_clear_cache(self) -> None:
        mat1 = self.builder.get_or_create_material("test.jpg")
        self.builder.clear_cache()
        mat2 = self.builder.get_or_create_material("test.jpg")
        self.assertIsNot(mat1, mat2)

    def test_cache_size(self) -> None:
        self.builder.get_or_create_material("a.jpg")
        self.builder.get_or_create_material("b.jpg")
        self.assertEqual(self.builder.cache_size, 2)


class TestMaterialBuilderWithTextureData(unittest.TestCase):
    """Test material creation with actual TextureData."""

    def setUp(self) -> None:
        self.builder = MaterialBuilder()
        # 4x4 RGBA texture — fully opaque white
        self.opaque_data = TextureData(
            width=4, height=4, channels=4,
            data=b"\xFF\xFF\xFF\xFF" * 16,
        )
        # 4x4 RGBA texture — has alpha
        self.alpha_data = TextureData(
            width=4, height=4, channels=4,
            data=b"\xFF\xFF\xFF\x80" * 16,
        )
        # 4x4 RGB texture (no alpha)
        self.rgb_data = TextureData(
            width=4, height=4, channels=3,
            data=b"\xFF\xFF\xFF" * 16,
        )

    def test_material_with_texture_data(self) -> None:
        mat = self.builder.get_or_create_material(
            "test.jpg", texture_data=self.opaque_data,
        )
        self.assertIsNotNone(mat)

    def test_alpha_detected(self) -> None:
        self.assertTrue(self.builder._has_alpha_channel(self.alpha_data))

    def test_alpha_not_detected_opaque(self) -> None:
        self.assertFalse(self.builder._has_alpha_channel(self.opaque_data))

    def test_rgb_no_alpha(self) -> None:
        self.assertFalse(self.builder._has_alpha_channel(self.rgb_data))

    def test_none_texture_no_alpha(self) -> None:
        self.assertFalse(self.builder._has_alpha_channel(None))

    def test_rgba_to_floats(self) -> None:
        # 2 pixels: red and green
        rgba = b"\xFF\x00\x00\xFF\x00\xFF\x00\xFF"
        floats = MaterialBuilder._rgba_bytes_to_floats(rgba)
        self.assertAlmostEqual(floats[0], 1.0)  # R
        self.assertAlmostEqual(floats[1], 0.0)  # G
        self.assertAlmostEqual(floats[2], 0.0)  # B
        self.assertAlmostEqual(floats[3], 1.0)  # A
        self.assertAlmostEqual(floats[4], 0.0)  # R
        self.assertAlmostEqual(floats[5], 1.0)  # G
        self.assertAlmostEqual(floats[6], 0.0)  # B
        self.assertAlmostEqual(floats[7], 1.0)  # A

    def test_material_name(self) -> None:
        name = MaterialBuilder._material_name("Player/human_face.jpg")
        self.assertEqual(name, "MU_human_face")

    def test_material_name_ozj(self) -> None:
        name = MaterialBuilder._material_name("World1/TileGrass01.ozj")
        self.assertEqual(name, "MU_TileGrass01")


class TestMaterialBuilderAssign(unittest.TestCase):
    """Test assign_to_object with mocked objects."""

    def setUp(self) -> None:
        self.builder = MaterialBuilder()
        self.mock_obj = MagicMock()
        self.mock_obj.material_slots = []
        self.mock_obj.data = MagicMock()
        self.mock_obj.data.materials = MagicMock()
        self.mock_obj.data.materials.append = lambda x: self.mock_obj.material_slots.append(
            MagicMock()
        )

    def test_assign_to_slot(self) -> None:
        mat = self.builder.get_or_create_material("test.jpg")
        result = self.builder.assign_to_object(self.mock_obj, mat, slot_index=0)
        self.assertTrue(result)
        self.assertEqual(len(self.mock_obj.material_slots), 1)

    def test_assign_to_high_slot_creates_slots(self) -> None:
        mat = self.builder.get_or_create_material("test.jpg")
        result = self.builder.assign_to_object(self.mock_obj, mat, slot_index=3)
        self.assertTrue(result)
        self.assertGreaterEqual(len(self.mock_obj.material_slots), 4)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
