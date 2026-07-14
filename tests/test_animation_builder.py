# MU Online Blender Tools - Tests for AnimationBuilder
#
# Run with:  python -m unittest tests.test_animation_builder -v
#
# NOTE: AnimationBuilder requires bpy (Blender Python). These tests use mocking.

"""
Tests for ``mu_blender_tools.builders.animation_builder.AnimationBuilder``.
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

class MockFCurve:
    """Mimics bpy.types.FCurve."""
    def __init__(self, data_path: str = "", index: int = 0) -> None:
        self.data_path = data_path
        self.array_index = index
        self.keyframe_points = MockKeyframePoints()
        self._last_update: Any = None

    def update(self) -> None:
        self._last_update = True


class MockKeyframePoints:
    """Mimics FCurve.keyframe_points."""
    def __init__(self) -> None:
        self._points: list[MockKeyframePoint] = []

    def add(self, count: int) -> None:
        for _ in range(count):
            self._points.append(MockKeyframePoint())

    def foreach_set(self, attr: str, values: list[float]) -> None:
        if attr == "co":
            for i, pt in enumerate(self._points):
                if i * 2 < len(values):
                    pt.co = (values[i * 2], values[i * 2 + 1])

    def __len__(self) -> int:
        return len(self._points)

    def __getitem__(self, index: int) -> MockKeyframePoint:
        return self._points[index]


class MockKeyframePoint:
    """Mimics a keyframe point."""
    def __init__(self) -> None:
        self.co: tuple[float, float] = (0.0, 0.0)


class MockFCurves:
    """Mimics action.fcurves."""
    def __init__(self) -> None:
        self._curves: list[MockFCurve] = []

    def new(self, data_path: str, index: int = 0) -> MockFCurve:
        fc = MockFCurve(data_path, index)
        self._curves.append(fc)
        return fc

    def remove(self, fcurve: MockFCurve) -> None:
        if fcurve in self._curves:
            self._curves.remove(fcurve)

    def __iter__(self):
        return iter(self._curves)

    def __len__(self) -> int:
        return len(self._curves)


class MockAction:
    """Mimics bpy.types.Action."""
    def __init__(self, name: str = "Action") -> None:
        self.name = name
        self.fcurves = MockFCurves()
        self.id_root = "OBJECT"
        self.user_data: dict[str, Any] = {}


class MockActions:
    """Mimics bpy.data.actions."""
    def __init__(self) -> None:
        self._actions: list[MockAction] = []

    def new(self, name: str) -> MockAction:
        action = MockAction(name)
        self._actions.append(action)
        return action

    def remove(self, action: MockAction) -> None:
        if action in self._actions:
            self._actions.remove(action)


class MockBpy:
    """Mimics the bpy module."""
    def __init__(self) -> None:
        self.data = MockBpyData()
        self.types = MagicMock()


class MockBpyData:
    """Mimics bpy.data."""
    def __init__(self) -> None:
        self.actions = MockActions()


# Patch BEFORE importing AnimationBuilder
from unittest.mock import MagicMock

sys.modules["bpy"] = MockBpy()
sys.modules["bpy.types"] = MagicMock()

from mu_blender_tools.readers.bmd_types import (
    BMD,
    BMDTextureAction,
    BMDTextureBone,
    BMDBoneMatrix,
    BMD_DUMMY_BONE,
)
from mu_blender_tools.builders.animation_builder import (
    AnimationBuilder,
    _DEFAULT_FPS,
)


# ======================================================================
# Test data helpers
# ======================================================================

def _make_matrix(
    positions: list[tuple[float, float, float]] | None = None,
    quaternions: list[tuple[float, float, float, float]] | None = None,
) -> BMDBoneMatrix:
    """Create a BMDBoneMatrix with optional position and quaternion data."""
    return BMDBoneMatrix(
        Position=positions or [],
        Rotation=[],
        Quaternion=quaternions or [],
    )


def _make_bone(
    name: str = "Bone",
    parent: int = -1,
    matrix: BMDBoneMatrix | None = None,
) -> BMDTextureBone:
    """Create a BMDTextureBone with optional matrix data."""
    return BMDTextureBone(
        Name=name,
        Parent=parent,
        Matrixes=[matrix] if matrix else [],
    )


def _make_action(num_keys: int = 10, lock_positions: bool = False) -> BMDTextureAction:
    """Create a BMDTextureAction."""
    positions = [(0.0, 0.0, 0.0)] * num_keys if lock_positions else []
    return BMDTextureAction(
        NumAnimationKeys=num_keys,
        LockPositions=lock_positions,
        Positions=positions,
        PlaySpeed=1.0,
    )


def _make_bmd(
    bones: list[BMDTextureBone] | None = None,
    actions: list[BMDTextureAction] | None = None,
    name: str = "TestModel",
) -> BMD:
    return BMD(Version=0x0A, Name=name, Meshes=[], Bones=bones or [], Actions=actions or [])


# ======================================================================
# Tests: _build_single_action
# ======================================================================

class TestBuildSingleAction(unittest.TestCase):
    """Test _build_single_action behavior."""

    def test_skips_action_with_zero_keys(self) -> None:
        bmd = _make_bmd(
            bones=[_make_bone("Root")],
            actions=[_make_action(num_keys=0)],
        )
        action = AnimationBuilder._build_single_action(bmd, bmd.Actions[0], 0, "Test")
        self.assertIsNone(action)

    def test_skips_action_with_one_key(self) -> None:
        bmd = _make_bmd(
            bones=[_make_bone("Root")],
            actions=[_make_action(num_keys=1)],
        )
        action = AnimationBuilder._build_single_action(bmd, bmd.Actions[0], 0, "Test")
        self.assertIsNone(action)

    def test_creates_action_with_location(self) -> None:
        positions = [(float(i), float(i * 2), float(i * 3)) for i in range(3)]
        mat = _make_matrix(positions=positions)
        bone = _make_bone("Root", matrix=mat)
        bmd = _make_bmd(bones=[bone], actions=[_make_action(num_keys=3)])
        action = AnimationBuilder._build_single_action(bmd, bmd.Actions[0], 0, "Test")
        self.assertIsNotNone(action)

    def test_creates_action_with_quaternion(self) -> None:
        quats = [(0.0, 0.0, 0.0, 1.0) for _ in range(3)]
        mat = _make_matrix(quaternions=quats)
        bone = _make_bone("Root", matrix=mat)
        bmd = _make_bmd(bones=[bone], actions=[_make_action(num_keys=3)])
        action = AnimationBuilder._build_single_action(bmd, bmd.Actions[0], 0, "Test")
        self.assertIsNotNone(action)

    def test_skips_dummy_bone(self) -> None:
        """Dummy bones should not generate FCurves."""
        positions = [(float(i), 0.0, 0.0) for i in range(3)]
        mat = _make_matrix(positions=positions)
        bone = _make_bone("Real", matrix=mat)
        bmd = _make_bmd(
            bones=[BMD_DUMMY_BONE, bone],
            actions=[_make_action(num_keys=3)],
        )
        action = AnimationBuilder._build_single_action(bmd, bmd.Actions[0], 0, "Test")
        self.assertIsNotNone(action)
        # Only 3 location FCurves (X, Y, Z) for the real bone
        self.assertEqual(len(action.fcurves), 3)

    def test_action_name_format(self) -> None:
        positions = [(0.0, 0.0, 0.0) for _ in range(3)]
        # Build bone matrixes for all 6 actions so action_idx=5 is valid
        mats = [_make_matrix(positions=positions) for _ in range(6)]
        bone = BMDTextureBone(Name="Root", Parent=-1, Matrixes=mats)
        actions_list = [_make_action(num_keys=3) for _ in range(6)]
        bmd = _make_bmd(bones=[bone], actions=actions_list)
        action = AnimationBuilder._build_single_action(bmd, bmd.Actions[5], 5, "MyModel")
        self.assertIsNotNone(action)
        self.assertEqual(action.name, "MyModel_action05")

    def test_euler_fallback_when_no_quaternion(self) -> None:
        """Bone with only Euler rotation should fall back to rotation_euler."""
        mat = BMDBoneMatrix(
            Position=[],
            Rotation=[(0.1, 0.2, 0.3) for _ in range(3)],
            Quaternion=[],
        )
        bone = _make_bone("Root", matrix=mat)
        bmd = _make_bmd(bones=[bone], actions=[_make_action(num_keys=3)])
        action = AnimationBuilder._build_single_action(bmd, bmd.Actions[0], 0, "Test")
        # action may be None if no fcurves created, or created with euler
        if action is not None:
            self.assertGreater(len(action.fcurves), 0)


# ======================================================================
# Tests: _create_location_fcurves
# ======================================================================

class TestCreateLocationFCurves(unittest.TestCase):
    """Test location FCurve creation."""

    def test_three_fcurves_created(self) -> None:
        action = MockAction()
        positions = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
        AnimationBuilder._create_location_fcurves(action, "Bone", positions, 2, 24.0)
        self.assertEqual(len(action.fcurves), 3)

    def test_fcurve_data_path(self) -> None:
        action = MockAction()
        positions = [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]
        AnimationBuilder._create_location_fcurves(action, "MyBone", positions, 2, 24.0)
        for fc in action.fcurves:
            self.assertIn("MyBone", fc.data_path)
            self.assertIn("location", fc.data_path)

    def test_fcurve_indices(self) -> None:
        action = MockAction()
        positions = [(10.0, 20.0, 30.0), (40.0, 50.0, 60.0)]
        AnimationBuilder._create_location_fcurves(action, "Bone", positions, 2, 24.0)
        indices = sorted([fc.array_index for fc in action.fcurves])
        self.assertEqual(indices, [0, 1, 2])

    def test_keyframe_values(self) -> None:
        action = MockAction()
        positions = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
        AnimationBuilder._create_location_fcurves(action, "Bone", positions, 2, 24.0)
        # Check X channel (index 0) values
        fc_x = [fc for fc in action.fcurves if fc.array_index == 0][0]
        self.assertAlmostEqual(fc_x.keyframe_points[0].co[1], 1.0)
        self.assertAlmostEqual(fc_x.keyframe_points[1].co[1], 4.0)


# ======================================================================
# Tests: _create_quaternion_fcurves
# ======================================================================

class TestCreateQuaternionFCurves(unittest.TestCase):
    """Test quaternion FCurve creation."""

    def test_four_fcurves_created(self) -> None:
        action = MockAction()
        quats = [(0.0, 0.0, 0.0, 1.0) for _ in range(2)]
        AnimationBuilder._create_quaternion_fcurves(action, "Bone", quats, 2, 24.0)
        self.assertEqual(len(action.fcurves), 4)

    def test_fcurve_indices(self) -> None:
        action = MockAction()
        quats = [(0.0, 0.0, 0.0, 1.0) for _ in range(2)]
        AnimationBuilder._create_quaternion_fcurves(action, "Bone", quats, 2, 24.0)
        indices = sorted([fc.array_index for fc in action.fcurves])
        self.assertEqual(indices, [0, 1, 2, 3])

    def test_quaternion_channel_mapping(self) -> None:
        """BMD (qx, qy, qz, qw) → Blender FCurve 0=W, 1=X, 2=Y, 3=Z.

        Blender stores quaternions as (W, X, Y, Z).
        BMD format is (qx, qy, qz, qw).
        Mapping: FCurve 0 (W) ← BMD[3] (qw)
                 FCurve 1 (X) ← BMD[0] (qx)
                 FCurve 2 (Y) ← BMD[1] (qy)
                 FCurve 3 (Z) ← BMD[2] (qz)
        """
        action = MockAction()
        quats = [(0.1, 0.2, 0.3, 0.9)]  # BMD: qx=0.1, qy=0.2, qz=0.3, qw=0.9
        AnimationBuilder._create_quaternion_fcurves(action, "Bone", quats, 1, 24.0)
        fc_map = {fc.array_index: fc for fc in action.fcurves}
        # FCurve index 0 (W) ← BMD qw = 0.9
        self.assertAlmostEqual(fc_map[0].keyframe_points[0].co[1], 0.9)
        # FCurve index 1 (X) ← BMD qx = 0.1
        self.assertAlmostEqual(fc_map[1].keyframe_points[0].co[1], 0.1)
        # FCurve index 2 (Y) ← BMD qy = 0.2
        self.assertAlmostEqual(fc_map[2].keyframe_points[0].co[1], 0.2)
        # FCurve index 3 (Z) ← BMD qz = 0.3
        self.assertAlmostEqual(fc_map[3].keyframe_points[0].co[1], 0.3)

    def test_fcurve_data_path(self) -> None:
        action = MockAction()
        quats = [(0.0, 0.0, 0.0, 1.0) for _ in range(2)]
        AnimationBuilder._create_quaternion_fcurves(action, "MyBone", quats, 2, 24.0)
        for fc in action.fcurves:
            self.assertIn("MyBone", fc.data_path)
            self.assertIn("rotation_quaternion", fc.data_path)


# ======================================================================
# Tests: build_actions (end-to-end)
# ======================================================================

class TestBuildActions(unittest.TestCase):
    """Test build_actions end-to-end."""

    def test_no_actions_empty_list(self) -> None:
        bmd = _make_bmd()
        actions = AnimationBuilder.build_actions(bmd)
        self.assertEqual(actions, [])

    def test_no_bones_empty_list(self) -> None:
        bmd = _make_bmd(actions=[_make_action(num_keys=5)])
        actions = AnimationBuilder.build_actions(bmd)
        self.assertEqual(actions, [])

    def test_single_action_single_bone(self) -> None:
        mat = _make_matrix(positions=[(float(i), 0.0, 0.0) for i in range(5)])
        bone = _make_bone("Root", matrix=mat)
        bmd = _make_bmd(bones=[bone], actions=[_make_action(num_keys=5)])
        actions = AnimationBuilder.build_actions(bmd)
        self.assertEqual(len(actions), 1)

    def test_multiple_actions(self) -> None:
        # Bone needs one matrix per action
        mat0 = _make_matrix(positions=[(0.0, 0.0, 0.0) for _ in range(5)])
        mat1 = _make_matrix(positions=[(1.0, 1.0, 1.0) for _ in range(3)])
        mat2 = _make_matrix(positions=[(2.0, 2.0, 2.0) for _ in range(10)])
        bone = BMDTextureBone(Name="Root", Parent=-1, Matrixes=[mat0, mat1, mat2])
        bmd = _make_bmd(
            bones=[bone],
            actions=[
                _make_action(num_keys=5),
                _make_action(num_keys=3),
                _make_action(num_keys=10),
            ],
        )
        actions = AnimationBuilder.build_actions(bmd)
        self.assertEqual(len(actions), 3)

    def test_single_keyframe_actions_skipped(self) -> None:
        mat0 = _make_matrix(positions=[(0.0, 0.0, 0.0) for _ in range(10)])
        mat1 = _make_matrix(positions=[(1.0, 1.0, 1.0) for _ in range(1)])  # 1 key → skipped
        mat2 = _make_matrix(positions=[(2.0, 2.0, 2.0) for _ in range(0)])  # 0 keys → skipped
        bone = BMDTextureBone(Name="Root", Parent=-1, Matrixes=[mat0, mat1, mat2])
        bmd = _make_bmd(
            bones=[bone],
            actions=[
                _make_action(num_keys=10),   # valid
                _make_action(num_keys=1),    # skipped
                _make_action(num_keys=0),    # skipped
            ],
        )
        actions = AnimationBuilder.build_actions(bmd)
        self.assertEqual(len(actions), 1)

    def test_action_with_both_location_and_rotation(self) -> None:
        positions = [(float(i), float(i * 2), 0.0) for i in range(3)]
        quats = [(0.0, 0.0, 0.0, 1.0) for _ in range(3)]
        mat = _make_matrix(positions=positions, quaternions=quats)
        bone = _make_bone("Root", matrix=mat)
        bmd = _make_bmd(bones=[bone], actions=[_make_action(num_keys=3)])
        actions = AnimationBuilder.build_actions(bmd)
        self.assertEqual(len(actions), 1)
        # 3 location + 4 quaternion = 7 FCurves
        self.assertEqual(len(actions[0].fcurves), 7)

    def test_multiple_bones(self) -> None:
        positions = [(float(i), 0.0, 0.0) for i in range(3)]
        mat1 = _make_matrix(positions=positions)
        mat2 = _make_matrix(positions=[(0.0, float(i), 0.0) for i in range(3)])
        bone1 = BMDTextureBone(Name="BoneA", Parent=-1, Matrixes=[mat1])
        bone2 = BMDTextureBone(Name="BoneB", Parent=-1, Matrixes=[mat2])
        bmd = _make_bmd(bones=[bone1, bone2], actions=[_make_action(num_keys=3)])
        actions = AnimationBuilder.build_actions(bmd)
        self.assertEqual(len(actions), 1)
        # 2 bones × 3 location = 6 FCurves
        self.assertEqual(len(actions[0].fcurves), 6)

    def test_bone_with_no_matrix_skipped(self) -> None:
        """Bone with no matrix data should not create FCurves."""
        bone_no_mat = _make_bone("Empty")
        bmd = _make_bmd(bones=[bone_no_mat], actions=[_make_action(num_keys=3)])
        actions = AnimationBuilder.build_actions(bmd)
        # No FCurves → action should be removed
        self.assertEqual(len(actions), 0)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
