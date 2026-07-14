# MU Online Blender Tools - Tests for ArmatureBuilder
#
# Run with:  python -m unittest tests.test_armature_builder -v
#
# NOTE: ArmatureBuilder requires bpy (Blender Python). These tests use mocking
# to verify the builder logic without a running Blender instance.

"""
Tests for ``mu_blender_tools.builders.armature_builder.ArmatureBuilder``.
"""

from __future__ import annotations

import math
import sys
import unittest
from typing import Any

sys.path.insert(0, ".")


# ======================================================================
# Mock bpy infrastructure
# ======================================================================

class MockEditBone:
    """Mimics bpy.types.EditBone."""
    def __init__(self, name: str) -> None:
        self.name = name
        self.head: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.tail: tuple[float, float, float] = (0.0, 0.0, 1.0)
        self.roll: float = 0.0
        self.parent: Any = None
        self.length: float = 1.0


class MockEditBones:
    """Mimics bpy.types.ArmatureEditBones."""
    def __init__(self) -> None:
        self._bones: list[MockEditBone] = []

    def new(self, name: str) -> MockEditBone:
        bone = MockEditBone(name)
        self._bones.append(bone)
        return bone

    def remove(self, bone: MockEditBone) -> None:
        if bone in self._bones:
            self._bones.remove(bone)

    def __iter__(self):
        return iter(self._bones)

    def __len__(self) -> int:
        return len(self._bones)

    def __getitem__(self, index: int) -> MockEditBone:
        return self._bones[index]


class MockArmatureData:
    """Mimics bpy.types.Armature."""
    def __init__(self, name: str = "Armature") -> None:
        self.name = name
        self.edit_bones = MockEditBones()
        self.display_type = "WIRE"


class MockArmatureObject:
    """Mimics a Blender armature Object."""
    def __init__(self, name: str = "Armature") -> None:
        self.name = name
        self.data = MockArmatureData(name)

    def select_set(self, value: bool) -> None:
        pass


class MockViewLayer:
    """Mimics bpy.context.view_layer."""
    def __init__(self) -> None:
        self.active_collection = MagicMock()
        self.objects = MagicMock()
        self.objects.active = None


class MockContext:
    """Mimics bpy.context."""
    def __init__(self) -> None:
        self.view_layer = MockViewLayer()
        self.scene = MagicMock()
        self.scene.collection = MagicMock()
        self.active_object: Any = None
        self.mode = "OBJECT"

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)


class MockBpy:
    """Mimics the bpy module."""
    def __init__(self) -> None:
        self.data = MockBpyData()
        self.context = MockContext()
        self.ops = MockOps()
        self.types = MagicMock()


class MockBpyData:
    """Mimics bpy.data."""
    def __init__(self) -> None:
        self.armatures = MockArmatures()
        self.objects = MockBpyObjects()


class MockArmatures:
    """Mimics bpy.data.armatures."""
    def __init__(self) -> None:
        self._armatures: list[MockArmatureData] = []

    def new(self, name: str) -> MockArmatureData:
        arm = MockArmatureData(name)
        self._armatures.append(arm)
        return arm


class MockBpyObjects:
    """Mimics bpy.data.objects."""
    def __init__(self) -> None:
        self._objects: list[MockArmatureObject] = []

    def new(self, name: str, data: Any) -> MockArmatureObject:
        obj = MockArmatureObject(name)
        obj.data = data
        self._objects.append(obj)
        return obj


class MockOps:
    """Mimics bpy.ops."""
    def __init__(self) -> None:
        self.object = MockOpsObject()


class MockOpsObject:
    """Mimics bpy.ops.object."""
    def __init__(self) -> None:
        self._mode = "OBJECT"

    def mode_set(self, mode: str = "OBJECT") -> None:
        self._mode = mode


# Patch sys.modules BEFORE importing ArmatureBuilder
from unittest.mock import MagicMock

sys.modules["bpy"] = MockBpy()
sys.modules["bpy.types"] = MagicMock()

from mu_blender_tools.readers.bmd_types import (
    BMD,
    BMDTextureBone,
    BMDBoneMatrix,
    BMD_DUMMY_BONE,
)
from mu_blender_tools.builders.armature_builder import (
    ArmatureBuilder,
    _quaternion_to_bone_roll,
    _quaternion_to_tail_offset,
    _DEFAULT_BONE_LENGTH,
    _DUMMY_BONE_LENGTH,
)


# ======================================================================
# Test data helpers
# ======================================================================

def _make_bone_matrix(
    px: float = 0.0, py: float = 0.0, pz: float = 0.0,
    qx: float = 0.0, qy: float = 0.0, qz: float = 0.0, qw: float = 1.0,
) -> BMDBoneMatrix:
    """Create a BMDBoneMatrix with bind-pose data."""
    return BMDBoneMatrix(
        Position=[(px, py, pz)],
        Rotation=[(0.0, 0.0, 0.0)],
        Quaternion=[(qx, qy, qz, qw)],
    )


def _make_bone(
    name: str = "Bone",
    parent: int = -1,
    px: float = 0.0, py: float = 0.0, pz: float = 0.0,
) -> BMDTextureBone:
    """Create a BMDTextureBone with bind-pose matrix."""
    mat = _make_bone_matrix(px=px, py=py, pz=pz)
    return BMDTextureBone(Name=name, Parent=parent, Matrixes=[mat])


# ======================================================================
# Tests: math utilities
# ======================================================================

class TestQuaternionToBoneRoll(unittest.TestCase):
    """Test _quaternion_to_bone_roll."""

    def test_identity_zero_roll(self) -> None:
        roll = _quaternion_to_bone_roll((0.0, 0.0, 0.0, 1.0))
        self.assertAlmostEqual(roll, 0.0, places=5)

    def test_90_degrees_around_x(self) -> None:
        """90° around X should give a non-zero roll."""
        qx = math.sin(math.radians(45.0))
        qw = math.cos(math.radians(45.0))
        roll = _quaternion_to_bone_roll((qx, 0.0, 0.0, qw))
        self.assertNotAlmostEqual(roll, 0.0)


class TestQuaternionToTailOffset(unittest.TestCase):
    """Test _quaternion_to_tail_offset."""

    def test_identity_points_up_y(self) -> None:
        """Identity quaternion → tail along +Y."""
        dx, dy, dz = _quaternion_to_tail_offset((0.0, 0.0, 0.0, 1.0), 10.0)
        self.assertAlmostEqual(dx, 0.0)
        self.assertAlmostEqual(dy, 10.0)
        self.assertAlmostEqual(dz, 0.0)

    def test_90_around_x_tilts_y(self) -> None:
        """90° around X → Y rotates towards Z."""
        qx = math.sin(math.radians(45.0))
        qw = math.cos(math.radians(45.0))
        dx, dy, dz = _quaternion_to_tail_offset((qx, 0.0, 0.0, qw), 10.0)
        self.assertAlmostEqual(dy, 0.0, places=4)
        self.assertAlmostEqual(dz, 10.0, places=4)

    def test_zero_length(self) -> None:
        dx, dy, dz = _quaternion_to_tail_offset((0.0, 0.0, 0.0, 1.0), 0.0)
        self.assertEqual((dx, dy, dz), (0.0, 0.0, 0.0))


# ======================================================================
# Tests: _get_bind_position
# ======================================================================

class TestGetBindPosition(unittest.TestCase):
    """Test _get_bind_position."""

    def test_real_bone_returns_position(self) -> None:
        bone = _make_bone(px=10.0, py=20.0, pz=30.0)
        pos = ArmatureBuilder._get_bind_position(bone, 0)
        self.assertEqual(pos, (10.0, 20.0, 30.0))

    def test_dummy_returns_origin(self) -> None:
        pos = ArmatureBuilder._get_bind_position(BMD_DUMMY_BONE, 0)
        self.assertEqual(pos, (0.0, 0.0, 0.0))

    def test_bone_no_matrixes_returns_origin(self) -> None:
        bone = BMDTextureBone(Name="Empty")
        pos = ArmatureBuilder._get_bind_position(bone, 0)
        self.assertEqual(pos, (0.0, 0.0, 0.0))

    def test_bone_no_position_returns_origin(self) -> None:
        mat = BMDBoneMatrix(Position=[], Rotation=[], Quaternion=[])
        bone = BMDTextureBone(Name="NoPos", Parent=-1, Matrixes=[mat])
        pos = ArmatureBuilder._get_bind_position(bone, 0)
        self.assertEqual(pos, (0.0, 0.0, 0.0))


# ======================================================================
# Tests: _create_edit_bone
# ======================================================================

class TestCreateEditBone(unittest.TestCase):
    """Test _create_edit_bone with mocked edit_bones."""

    def setUp(self) -> None:
        self.edit_bones = MockEditBones()
        self.bone_heads: dict[int, tuple[float, float, float]] = {}

    def test_dummy_bone_created(self) -> None:
        ArmatureBuilder._create_edit_bone(
            self.edit_bones, BMD_DUMMY_BONE, 0, self.bone_heads,
        )
        self.assertEqual(len(self.edit_bones), 1)
        self.assertEqual(self.edit_bones[0].name, "Dummy_000")
        self.assertEqual(self.edit_bones[0].head, (0.0, 0.0, 0.0))

    def test_real_bone_created(self) -> None:
        bone = _make_bone(name="Root", px=5.0, py=10.0, pz=0.0)
        self.bone_heads[0] = (5.0, 10.0, 0.0)
        ArmatureBuilder._create_edit_bone(
            self.edit_bones, bone, 0, self.bone_heads,
        )
        self.assertEqual(len(self.edit_bones), 1)
        self.assertEqual(self.edit_bones[0].name, "Root")
        self.assertEqual(self.edit_bones[0].head, (5.0, 10.0, 0.0))

    def test_bone_with_parent_creates_tail_away_from_parent(self) -> None:
        """Bone with parent should have tail oriented correctly."""
        bone = _make_bone(name="Child", parent=0, px=0.0, py=100.0, pz=0.0)
        self.bone_heads[0] = (0.0, 0.0, 0.0)
        self.bone_heads[1] = (0.0, 100.0, 0.0)
        ArmatureBuilder._create_edit_bone(
            self.edit_bones, bone, 1, self.bone_heads,
        )
        ebone = self.edit_bones[0]
        # Tail should extend from head in bone's +Y direction
        self.assertEqual(ebone.head, (0.0, 100.0, 0.0))
        self.assertGreater(ebone.tail[1], 100.0)  # Y should increase


# ======================================================================
# Tests: build_armature
# ======================================================================

class TestBuildArmature(unittest.TestCase):
    """Test end-to-end armature building."""

    def test_empty_bones_returns_none(self) -> None:
        bmd = BMD(Version=0x0A, Name="Empty", Bones=[])
        obj = ArmatureBuilder.build_armature(bmd, "Test")
        self.assertIsNone(obj)

    def test_single_dummy_bone(self) -> None:
        bmd = BMD(Version=0x0A, Name="DummyTest", Bones=[BMD_DUMMY_BONE])
        obj = ArmatureBuilder.build_armature(bmd, "Test")
        self.assertIsNotNone(obj)
        self.assertEqual(len(obj.data.edit_bones), 1)

    def test_single_real_bone(self) -> None:
        bone = _make_bone(name="Root")
        bmd = BMD(Version=0x0A, Name="RootTest", Bones=[bone])
        obj = ArmatureBuilder.build_armature(bmd, "Test")
        self.assertIsNotNone(obj)
        self.assertEqual(len(obj.data.edit_bones), 1)

    def test_hierarchy(self) -> None:
        root = _make_bone(name="Root", px=0.0, py=0.0, pz=0.0)
        child = _make_bone(name="Child", parent=0, px=0.0, py=50.0, pz=0.0)
        bmd = BMD(Version=0x0A, Name="Hierarchy", Bones=[root, child])
        obj = ArmatureBuilder.build_armature(bmd, "Test")
        self.assertIsNotNone(obj)
        bones = obj.data.edit_bones
        self.assertEqual(len(bones), 2)

    def test_mixed_real_and_dummy(self) -> None:
        real0 = _make_bone(name="Real0")
        dummy = BMD_DUMMY_BONE
        real1 = _make_bone(name="Real1")
        bmd = BMD(Version=0x0A, Name="Mixed", Bones=[real0, dummy, real1])
        obj = ArmatureBuilder.build_armature(bmd, "Test")
        self.assertIsNotNone(obj)
        bones = obj.data.edit_bones
        self.assertEqual(len(bones), 3)
        self.assertEqual(bones[0].name, "Real0")
        self.assertTrue(bones[1].name.startswith("Dummy"))
        self.assertEqual(bones[2].name, "Real1")

    def test_bone_count_logged(self) -> None:
        """build_armature should not crash with complex setups."""
        bones = [
            _make_bone(name=f"Bone_{i}", parent=i - 1, px=float(i * 10.0))
            for i in range(5)
        ]
        bmd = BMD(Version=0x0A, Name="Chain", Bones=bones)
        obj = ArmatureBuilder.build_armature(bmd, "Chain")
        self.assertIsNotNone(obj)
        self.assertEqual(len(obj.data.edit_bones), 5)


# ======================================================================
# Tests: _compute_bone_length
# ======================================================================

class TestComputeBoneLength(unittest.TestCase):
    """Test bone length estimation."""

    def test_root_no_children_uses_default(self) -> None:
        heads = {0: (0.0, 0.0, 0.0)}
        length = ArmatureBuilder._compute_bone_length(0, (0.0, 0.0, 0.0), -1, heads)
        self.assertEqual(length, _DEFAULT_BONE_LENGTH)

    def test_with_parent_uses_parent_distance(self) -> None:
        heads = {0: (0.0, 0.0, 0.0), 1: (0.0, 50.0, 0.0)}
        length = ArmatureBuilder._compute_bone_length(1, (0.0, 50.0, 0.0), 0, heads)
        self.assertAlmostEqual(length, 50.0 * 0.2, places=5)

    def test_with_nearby_child(self) -> None:
        heads = {0: (0.0, 0.0, 0.0), 1: (0.0, 20.0, 0.0)}
        length = ArmatureBuilder._compute_bone_length(0, (0.0, 0.0, 0.0), -1, heads)
        self.assertAlmostEqual(length, 20.0 * 0.2, places=5)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
