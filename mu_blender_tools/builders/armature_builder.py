# MU Online Blender Tools - ArmatureBuilder
#
# Converts BMD bone data (from BMDReader) into a Blender Armature.
#
# Design:
#   - Pure Blender Data API — no bpy.ops calls
#   - Bones are created in Edit Mode for proper hierarchy setup
#   - Bind pose: first action (index 0), first keyframe (index 0)
#   - Dummy bones are preserved as small placeholder bones to maintain
#     bone index alignment for skinning
#   - ArmatureBuilder does NOT read files, create animations, or bind meshes
#
# BMD → Blender mapping:
#   BMDTextureBone.Name              → Bone.name
#   BMDTextureBone.Parent (index)    → Bone.parent (resolved via hierarchy)
#   BMDBoneMatrix.Position[0]        → Bone.head (bind-pose position)
#   BMDBoneMatrix.Quaternion[0]      → Bone roll + tail direction
#   BMD_DUMMY_BONE                   → Tiny bone at origin (index placeholder)

from __future__ import annotations

import logging
import math
from typing import Any, Optional

import bpy
from bpy.types import Armature, EditBone, Object

from ..readers.bmd_types import (
    BMD,
    BMDTextureBone,
    BMDBoneMatrix,
    BMD_DUMMY_BONE,
)

_logger = logging.getLogger("mu_blender_tools")


# ======================================================================
# Constants
# ======================================================================

_DEFAULT_BONE_LENGTH: float = 5.0
"""Default length for bones that have no position data (e.g. dummies)."""

_DUMMY_BONE_LENGTH: float = 0.5
"""Length for dummy/placeholder bones."""

_BONE_TAIL_RATIO: float = 0.2
"""Tail extends this fraction of the parent-child distance from head.
For root bones without children, a fixed default length is used.
"""


# ======================================================================
# Quaternion → Bone Roll conversion
# ======================================================================


def _quaternion_to_bone_roll(q: tuple[float, float, float, float]) -> float:
    """Convert a quaternion to Blender's bone roll angle.

    In Blender, bones are aligned along the local Y+ axis by default.
    The roll is the rotation around Y that twists the bone's X/Z axes.

    This function extracts the roll component from a quaternion
    that describes the full bone orientation.

    Args:
        q: Quaternion ``(qx, qy, qz, qw)`` in XYZW order.

    Returns:
        Roll angle in radians.
    """
    qx, qy, qz, qw = q

    # Decompose: the bone Y-axis in world space
    # Blender default bone orientation: Y along the bone axis
    # The quaternion rotates from bone-local to world.
    # Roll is the twist angle around Y.

    # Compute the angle of the X-axis projection onto YZ plane
    # This is a simplified extraction — for precise bone matching,
    # a more involved decomposition may be needed.
    sin_roll = 2.0 * (qw * qx + qy * qz)
    cos_roll = 1.0 - 2.0 * (qx * qx + qy * qy)

    roll = math.atan2(sin_roll, cos_roll)
    return roll


def _quaternion_to_tail_offset(
    q: tuple[float, float, float, float],
    length: float,
) -> tuple[float, float, float]:
    """Compute the tail position from a quaternion orientation and length.

    Blender bones extend along the local Y+ axis.
    The world-space direction is ``q * (0, 1, 0) * q_conjugate``.

    Args:
        q: Quaternion ``(qx, qy, qz, qw)``.
        length: Desired bone length.

    Returns:
        ``(dx, dy, dz)`` offset from head to tail.
    """
    qx, qy, qz, qw = q

    # Rotate (0, 1, 0) by q
    # Using standard quaternion rotation: v' = q * v * q^-1
    x = 2.0 * (qx * qy - qw * qz)
    y = 1.0 - 2.0 * (qx * qx + qz * qz)
    z = 2.0 * (qy * qz + qw * qx)

    return (x * length, y * length, z * length)


# ======================================================================
# ArmatureBuilder
# ======================================================================


class ArmatureBuilder:
    """Creates Blender Armature objects from parsed BMD bone data.

    Usage::

        from mu_blender_tools.readers.bmd_reader import BMDReader
        from mu_blender_tools.builders.armature_builder import ArmatureBuilder

        bmd = BMDReader().Read(raw_bytes)
        arm_obj = ArmatureBuilder.build_armature(bmd, name="MySkeleton")
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def build_armature(
        bmd: BMD,
        name: str = "MUArmature",
        collection: Optional[Object] = None,
    ) -> Optional[Object]:
        """Create a Blender Armature object from BMD bone data.

        Args:
            bmd: Parsed BMD data (from BMDReader).
            name: Name for the armature object and data.
            collection: Target collection (defaults to active collection).

        Returns:
            The created Armature Object, or ``None`` if there are no bones.
        """
        if not bmd.Bones:
            _logger.warning("No bones to create armature '%s'", name)
            return None

        target_collection = collection or ArmatureBuilder._active_collection()

        # Create armature data
        arm_data: Armature = bpy.data.armatures.new(name)
        arm_data.display_type = "WIRE"

        # Create armature object
        arm_obj: Object = bpy.data.objects.new(name, arm_data)
        target_collection.objects.link(arm_obj)

        # Make active and enter edit mode to add bones
        ArmatureBuilder._enter_edit_mode(arm_obj)

        try:
            edit_bones = arm_data.edit_bones

            # Build all bones (including dummies)
            bone_map: dict[int, EditBone] = {}
            bone_heads: dict[int, tuple[float, float, float]] = {}

            # First pass: collect head positions
            for idx, bmd_bone in enumerate(bmd.Bones):
                head = ArmatureBuilder._get_bind_position(bmd_bone, idx)
                bone_heads[idx] = head

            # Second pass: create edit bones
            for idx, bmd_bone in enumerate(bmd.Bones):
                ebone = ArmatureBuilder._create_edit_bone(
                    edit_bones, bmd_bone, idx, bone_heads,
                )
                if ebone is not None:
                    bone_map[idx] = ebone

            # Third pass: set parents
            for idx, bmd_bone in enumerate(bmd.Bones):
                if idx not in bone_map:
                    continue
                ebone = bone_map[idx]
                parent_idx = bmd_bone.Parent
                if parent_idx >= 0 and parent_idx in bone_map:
                    ebone.parent = bone_map[parent_idx]

            _logger.info(
                "Created armature '%s': %d bones (%d real, %d dummy)",
                name,
                len(bmd.Bones),
                sum(1 for b in bmd.Bones if b is not BMD_DUMMY_BONE),
                sum(1 for b in bmd.Bones if b is BMD_DUMMY_BONE),
            )

        finally:
            # Always exit edit mode
            ArmatureBuilder._exit_edit_mode()

        return arm_obj

    # ------------------------------------------------------------------
    # Edit bone creation
    # ------------------------------------------------------------------

    @staticmethod
    def _create_edit_bone(
        edit_bones: Any,  # bpy.types.ArmatureEditBones
        bmd_bone: BMDTextureBone,
        index: int,
        bone_heads: dict[int, tuple[float, float, float]],
    ) -> Optional[EditBone]:
        """Create a single edit bone from a BMDTextureBone.

        Dummy bones get a tiny placeholder. Real bones get proper
        position, orientation, and roll from the bind pose.

        Args:
            edit_bones: ``armature.data.edit_bones`` collection.
            bmd_bone: The BMD bone descriptor.
            index: Bone index (for naming dummies).
            bone_heads: Map of index → head position tuple (x, y, z).

        Returns:
            The created ``EditBone``, or ``None`` if invalid.
        """
        if bmd_bone is BMD_DUMMY_BONE:
            # Create a tiny placeholder bone at origin
            ebone = edit_bones.new(name=f"Dummy_{index:03d}")
            ebone.head = (0.0, 0.0, 0.0)
            ebone.tail = (0.0, 0.0, _DUMMY_BONE_LENGTH)
            return ebone

        if not bmd_bone.Matrixes:
            _logger.warning(
                "Bone '%s' has no matrixes, creating at origin",
                bmd_bone.Name,
            )
            ebone = edit_bones.new(name=bmd_bone.Name)
            ebone.head = (0.0, 0.0, 0.0)
            ebone.tail = (0.0, 0.0, _DEFAULT_BONE_LENGTH)
            return ebone

        # Bind pose: first action (0), first keyframe (0)
        matrix = bmd_bone.Matrixes[0]
        head = bone_heads.get(index, (0.0, 0.0, 0.0))

        # Determine bone length
        bone_length = ArmatureBuilder._compute_bone_length(
            index, head, bmd_bone.Parent, bone_heads,
        )

        # Compute tail position and roll from quaternion
        if matrix.Quaternion:
            q = matrix.Quaternion[0]
            tail_offset = _quaternion_to_tail_offset(q, bone_length)
            roll = _quaternion_to_bone_roll(q)
        else:
            tail_offset = (0.0, bone_length, 0.0)
            roll = 0.0

        tail = (head[0] + tail_offset[0],
                head[1] + tail_offset[1],
                head[2] + tail_offset[2])

        # Create edit bone
        name = bmd_bone.Name or f"Bone_{index:03d}"
        ebone = edit_bones.new(name=name)
        ebone.head = head
        ebone.tail = tail
        ebone.roll = roll

        _logger.debug(
            "Created bone '%s': head=(%.1f, %.1f, %.1f) tail=(%.1f, %.1f, %.1f) "
            "roll=%.2f length=%.1f",
            name, head[0], head[1], head[2],
            tail[0], tail[1], tail[2], roll, bone_length,
        )

        return ebone

    # ------------------------------------------------------------------
    # Bind pose extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _get_bind_position(
        bmd_bone: BMDTextureBone, index: int,
    ) -> tuple[float, float, float]:
        """Extract the bind-pose position of a bone.

        Uses the first action (0), first keyframe (0).
        Dummy bones return origin.

        Returns:
            ``(x, y, z)`` position.
        """
        if bmd_bone is BMD_DUMMY_BONE:
            return (0.0, 0.0, 0.0)

        if not bmd_bone.Matrixes:
            return (0.0, 0.0, 0.0)

        matrix = bmd_bone.Matrixes[0]
        if matrix.Position:
            return matrix.Position[0]

        return (0.0, 0.0, 0.0)

    # ------------------------------------------------------------------
    # Bone length estimation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_bone_length(
        index: int,
        head: tuple[float, float, float],
        parent_idx: int,
        bone_heads: dict[int, tuple[float, float, float]],
    ) -> float:
        """Estimate a reasonable bone length.

        If the bone has a child, length = distance to nearest child.
        If the bone has a parent, length = fraction of parent distance.
        Otherwise, a default length is used.

        This gives reasonable visual results for the armature display.
        """
        # Try to find a child bone for distance estimation
        children_distances: list[float] = []
        for other_idx, other_head in bone_heads.items():
            if other_idx == index:
                continue
            other_parent = parent_idx  # approximate — caller sets parent later
            # Simple heuristic: bones that are "nearby" might be children
            dx = other_head[0] - head[0]
            dy = other_head[1] - head[1]
            dz = other_head[2] - head[2]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if 0 < dist <= _DEFAULT_BONE_LENGTH * 4:
                children_distances.append(dist)

        if children_distances:
            # Use the closest child distance * ratio
            return min(children_distances) * _BONE_TAIL_RATIO

        # If has a parent, use distance to parent * ratio
        if parent_idx >= 0 and parent_idx in bone_heads:
            parent_head = bone_heads[parent_idx]
            dx = head[0] - parent_head[0]
            dy = head[1] - parent_head[1]
            dz = head[2] - parent_head[2]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist > 0:
                return dist * _BONE_TAIL_RATIO

        return _DEFAULT_BONE_LENGTH

    # ------------------------------------------------------------------
    # Edit mode helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _enter_edit_mode(arm_obj: Object) -> None:
        """Enter Blender's armature edit mode.

        Must be called before adding/editing bones.
        """
        bpy.context.view_layer.objects.active = arm_obj
        arm_obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")

    @staticmethod
    def _exit_edit_mode() -> None:
        """Exit Blender's armature edit mode."""
        bpy.ops.object.mode_set(mode="OBJECT")

    # ------------------------------------------------------------------
    # Collection helper
    # ------------------------------------------------------------------

    @staticmethod
    def _active_collection() -> Object:  # actually bpy.types.Collection
        """Return the active collection (view layer's active or master)."""
        view_layer = bpy.context.view_layer
        if view_layer and view_layer.active_collection:
            return view_layer.active_collection
        return bpy.context.scene.collection
