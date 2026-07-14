# MU Online Blender Tools - AnimationBuilder
#
# Converts BMD animation data (from BMDReader) into Blender Actions.
#
# Design:
#   - Pure Blender Data API — no bpy.ops calls
#   - One Blender Action per BMDTextureAction
#   - FCurves for bone Location (XYZ) and Rotation Quaternion (XYZW)
#   - Skips actions with 0 or 1 keyframes (bind-pose only)
#   - Skips dummy bones
#   - AnimationBuilder does NOT read files, create meshes, or create armatures
#
# BMD → Blender mapping:
#   BMDTextureAction.NumAnimationKeys → number of keyframes
#   BMDBoneMatrix.Position[]          → location FCurves (X, Y, Z)
#   BMDBoneMatrix.Quaternion[]        → rotation_quaternion FCurves (X, Y, Z, W)
#   BMDTextureBone.Name               → pose.bones["name"] data_path

from __future__ import annotations

import logging
from typing import Optional

import bpy
from bpy.types import Action, FCurve

from ..readers.bmd_types import (
    BMD,
    BMDTextureAction,
    BMDTextureBone,
    BMDBoneMatrix,
    BMD_DUMMY_BONE,
)

_logger = logging.getLogger("mu_blender_tools")


# ======================================================================
# Constants
# ======================================================================

_DEFAULT_FPS: float = 24.0
"""Default playback speed for MU Online animations (matching TS reference)."""


# ======================================================================
# AnimationBuilder
# ======================================================================


class AnimationBuilder:
    """Creates Blender Actions from parsed BMD animation data.

    Usage::

        from mu_blender_tools.readers.bmd_reader import BMDReader
        from mu_blender_tools.builders.animation_builder import AnimationBuilder

        bmd = BMDReader().Read(raw_bytes)
        actions = AnimationBuilder.build_actions(bmd, armature_obj)
        # actions is a list of bpy.types.Action
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def build_actions(
        bmd: BMD,
        armature_name: str = "",
    ) -> list[Action]:
        """Create Blender Actions for every action in a BMD model.

        Each ``BMDTextureAction`` with more than 1 keyframe produces
        one ``bpy.types.Action`` containing FCurves for each non-dummy
        bone's location and rotation.

        Args:
            bmd: Parsed BMD data (from BMDReader).
            armature_name: Optional armature name used in action naming.
                           If empty, the BMD model name is used.

        Returns:
            List of created Blender Actions.
        """
        if not bmd.Actions or not bmd.Bones:
            _logger.warning(
                "No actions (%d) or bones (%d) to animate",
                len(bmd.Actions), len(bmd.Bones),
            )
            return []

        base_name = armature_name or bmd.Name or "MUModel"
        created_actions: list[Action] = []

        for action_idx, bmd_action in enumerate(bmd.Actions):
            try:
                action = AnimationBuilder._build_single_action(
                    bmd, bmd_action, action_idx, base_name,
                )
                if action is not None:
                    created_actions.append(action)
            except Exception as e:
                _logger.error(
                    "Failed to build action %d: %s", action_idx, e,
                )

        _logger.info(
            "AnimationBuilder: created %d action(s) for '%s'",
            len(created_actions), base_name,
        )
        return created_actions

    # ------------------------------------------------------------------
    # Single action creation
    # ------------------------------------------------------------------

    @staticmethod
    def _build_single_action(
        bmd: BMD,
        bmd_action: BMDTextureAction,
        action_idx: int,
        base_name: str,
    ) -> Optional[Action]:
        """Create one Blender Action from one BMDTextureAction.

        Skips actions with 0 or 1 keyframes (they define only the
        bind-pose which is already baked into the armature).

        Args:
            bmd: Full BMD data (needed for bone list).
            bmd_action: The action descriptor.
            action_idx: Index of this action (for naming).
            base_name: Base name for the action.

        Returns:
            The created Blender Action, or ``None`` if skipped.
        """
        num_keys = bmd_action.NumAnimationKeys

        if num_keys <= 1:
            _logger.debug(
                "Skipping action %d '%s_action%02d': %d keyframe(s)",
                action_idx, base_name, action_idx, num_keys,
            )
            return None

        action_name = f"{base_name}_action{action_idx:02d}"
        action: Action = bpy.data.actions.new(action_name)

        # Mark as a non-legacy action suitable for bones
        action.id_root = "OBJECT"

        fps = _DEFAULT_FPS * bmd_action.PlaySpeed
        bone_count = len(bmd.Bones)

        for bone_idx, bmd_bone in enumerate(bmd.Bones):
            # Skip dummy bones
            if bmd_bone is BMD_DUMMY_BONE:
                continue

            # Skip bones without matrix data for this action
            if action_idx >= len(bmd_bone.Matrixes):
                continue

            matrix = bmd_bone.Matrixes[action_idx]

            # Skip if no keyframe data
            if not matrix.Position and not matrix.Quaternion:
                continue

            bone_name = bmd_bone.Name or f"Bone_{bone_idx:03d}"

            # ---- Location FCurves (X, Y, Z) ----
            if matrix.Position and len(matrix.Position) >= num_keys:
                AnimationBuilder._create_location_fcurves(
                    action, bone_name, matrix.Position, num_keys, fps,
                )

            # ---- Rotation Quaternion FCurves (X, Y, Z, W) ----
            if matrix.Quaternion and len(matrix.Quaternion) >= num_keys:
                AnimationBuilder._create_quaternion_fcurves(
                    action, bone_name, matrix.Quaternion, num_keys, fps,
                )
            elif matrix.Rotation and len(matrix.Rotation) >= num_keys:
                # Fallback: use Euler rotation if quaternion not available
                _logger.debug(
                    "Bone '%s' has no quaternion data, using Euler",
                    bone_name,
                )
                AnimationBuilder._create_rotation_euler_fcurves(
                    action, bone_name, matrix.Rotation, num_keys, fps,
                )

        # Check if any FCurves were added
        if not action.fcurves:
            _logger.debug(
                "Action '%s' has no FCurves (all bones were dummy?)",
                action_name,
            )
            bpy.data.actions.remove(action)
            return None

        _logger.info(
            "Created action '%s': %d keys, %d FCurves, %.1f FPS",
            action_name, num_keys, len(action.fcurves), fps,
        )
        return action

    # ------------------------------------------------------------------
    # Location FCurves
    # ------------------------------------------------------------------

    @staticmethod
    def _create_location_fcurves(
        action: Action,
        bone_name: str,
        positions: list[tuple[float, float, float]],
        num_keys: int,
        fps: float,
    ) -> None:
        """Create FCurves for bone location (X, Y, Z).

        Args:
            action: Target action.
            bone_name: Name of the bone (for data_path).
            positions: List of (x, y, z) tuples for each keyframe.
            num_keys: Number of keyframes.
            fps: Frames per second for timing.
        """
        data_path = f'pose.bones["{bone_name}"].location'

        # Pre-allocate keyframe points
        for axis in range(3):
            fcurve = action.fcurves.new(data_path, index=axis)
            fcurve.keyframe_points.add(num_keys)

            # Use foreach_set for batch performance
            coords = [0.0] * (num_keys * 2)
            for k in range(num_keys):
                frame = float(k) / fps * fps  # frame = k (one per frame)
                # Actually: time = k / fps (in seconds), frame = time * fps = k
                # Blender keyframe_points use (frame, value) pairs
                # frame number = k (since we set FPS to match)
                time = float(k)
                coords[k * 2] = time
                coords[k * 2 + 1] = positions[k][axis]

            fcurve.keyframe_points.foreach_set("co", coords)
            fcurve.update()

    # ------------------------------------------------------------------
    # Quaternion rotation FCurves
    # ------------------------------------------------------------------

    @staticmethod
    def _create_quaternion_fcurves(
        action: Action,
        bone_name: str,
        quaternions: list[tuple[float, float, float, float]],
        num_keys: int,
        fps: float,
    ) -> None:
        """Create FCurves for bone rotation (quaternion XYZW).

        Blender stores quaternions as ``(w, x, y, z)`` internally but
        the FCurve indices are 0=X, 1=Y, 2=Z, 3=W (matching Blender's
        ``rotation_quaternion`` property indexing).

        BMD quaternions are ``(qx, qy, qz, qw)`` order — we remap to
        Blender's ``(qw, qx, qy, qz)`` storage order via the channel
        indices.

        Args:
            action: Target action.
            bone_name: Name of the bone.
            quaternions: List of (qx, qy, qz, qw) tuples.
            num_keys: Number of keyframes.
            fps: Frames per second.
        """
        data_path = f'pose.bones["{bone_name}"].rotation_quaternion'

        # Blender quaternion channel mapping:
        #   index 0 = W, index 1 = X, index 2 = Y, index 3 = Z
        # BMD format: (qx, qy, qz, qw)
        axis_map = [
            (1, 0),  # FCurve index 0 → BMD qx
            (2, 1),  # FCurve index 1 → BMD qy
            (3, 2),  # FCurve index 2 → BMD qz
            (0, 3),  # FCurve index 3 → BMD qw
        ]

        for fcurve_idx, bmd_idx in axis_map:
            fcurve = action.fcurves.new(data_path, index=fcurve_idx)
            fcurve.keyframe_points.add(num_keys)

            coords = [0.0] * (num_keys * 2)
            for k in range(num_keys):
                time = float(k)
                coords[k * 2] = time
                coords[k * 2 + 1] = quaternions[k][bmd_idx]

            fcurve.keyframe_points.foreach_set("co", coords)
            fcurve.update()

    # ------------------------------------------------------------------
    # Euler rotation FCurves (fallback)
    # ------------------------------------------------------------------

    @staticmethod
    def _create_rotation_euler_fcurves(
        action: Action,
        bone_name: str,
        rotations: list[tuple[float, float, float]],
        num_keys: int,
        fps: float,
    ) -> None:
        """Create FCurves for bone rotation using Euler angles (fallback).

        Only used when quaternion data is not available.

        Args:
            action: Target action.
            bone_name: Name of the bone.
            rotations: List of (rx, ry, rz) Euler angle tuples (radians).
            num_keys: Number of keyframes.
            fps: Frames per second.
        """
        data_path = f'pose.bones["{bone_name}"].rotation_euler'

        for axis in range(3):
            fcurve = action.fcurves.new(data_path, index=axis)
            fcurve.keyframe_points.add(num_keys)

            coords = [0.0] * (num_keys * 2)
            for k in range(num_keys):
                time = float(k)
                coords[k * 2] = time
                coords[k * 2 + 1] = rotations[k][axis]

            fcurve.keyframe_points.foreach_set("co", coords)
            fcurve.update()
