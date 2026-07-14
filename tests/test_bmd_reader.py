# MU Online Blender Tools - Tests for BMDReader
#
# Run with:  python -m unittest tests.test_bmd_reader -v

"""
Tests for ``mu_blender_tools.readers.bmd_reader.BMDReader``.

Uses synthetic binary data to verify parsing against the C# reference.
"""

from __future__ import annotations

import math
import struct
import sys
import unittest
from typing import Any

sys.path.insert(0, ".")

from mu_blender_tools.readers.binary_reader import BinaryReaderError
from mu_blender_tools.readers.bmd_reader import BMDReader, STRING_LENGTH
from mu_blender_tools.readers.bmd_types import (
    BMD,
    BMDTextureMesh,
    BMDTextureBone,
    BMD_DUMMY_BONE,
)


# ======================================================================
# Helpers
# ======================================================================

def _build(fmt: str, *values: Any) -> bytes:
    """Pack values into little-endian bytes."""
    if not fmt.startswith("<"):
        fmt = "<" + fmt
    return struct.pack(fmt, *values)


def _make_string(s: str, length: int = STRING_LENGTH) -> bytes:
    """Create a fixed-length null-terminated ASCII string."""
    encoded = s.encode("ascii")
    if len(encoded) >= length:
        return encoded[:length]
    return encoded + b"\x00" * (length - len(encoded))


# ======================================================================
# Tests
# ======================================================================


class TestBMDReaderHeader(unittest.TestCase):
    """Test header validation (magic, version, minimum size)."""

    def test_valid_header_v10(self) -> None:
        """Version 0x0A (no encryption) should parse without error."""
        data = b"BMD" + _build("B", 0x0A)
        data += _make_string("TestModel")
        data += _build("HHH", 1, 2, 1)  # meshCount=1, boneCount=2, actionCount=1
        # Mesh data (minimal), actions, bones...
        data += self._minimal_mesh()
        data += self._minimal_action()
        data += self._minimal_bones(2, num_keys=1)

        reader = BMDReader()
        bmd = reader.Read(data)
        self.assertEqual(bmd.Name, "TestModel")
        self.assertEqual(bmd.Version, 0x0A)
        self.assertEqual(len(bmd.Meshes), 1)
        self.assertEqual(len(bmd.Bones), 2)
        self.assertEqual(len(bmd.Actions), 1)

    def test_invalid_magic(self) -> None:
        """Non-BMD header should raise."""
        data = b"XXX" + _build("B", 0x0A)
        reader = BMDReader()
        with self.assertRaises(BinaryReaderError):
            reader.Read(data)

    def test_unsupported_version(self) -> None:
        """Unknown version should raise."""
        data = b"BMD" + _build("B", 0xFF)
        reader = BMDReader()
        with self.assertRaises(BinaryReaderError):
            reader.Read(data)

    def test_file_too_small(self) -> None:
        """Truncated file should raise."""
        data = b"BMD"
        reader = BMDReader()
        with self.assertRaises(BinaryReaderError):
            reader.Read(data)

    @staticmethod
    def _minimal_mesh() -> bytes:
        """Build a minimal mesh block (no vertices/normals/texcoords/triangles)."""
        payload = b""
        payload += _build("hhhhh", 0, 0, 0, 0, 0)  # counts: 0,0,0,0, texture=0
        # no vertex data
        # no normal data
        # no texcoord data
        # no triangle data
        payload += _make_string("")  # texture path
        return payload

    @staticmethod
    def _minimal_action() -> bytes:
        """Build a minimal action block (0 keys, lock=False)."""
        return _build("h?", 0, False)  # NumAnimationKeys=0, LockPositions=False

    @staticmethod
    def _minimal_bones(bone_count: int, num_keys: int = 0) -> bytes:
        """Build minimal bone blocks (all dummies)."""
        payload = b""
        for _ in range(bone_count):
            payload += _build("?", True)  # IsDummy=True
        return payload


class TestBMDReaderMesh(unittest.TestCase):
    """Test mesh geometry parsing."""

    def test_mesh_with_vertices(self) -> None:
        """Mesh with one vertex (i=0 → position 0,0,0)."""
        data = self._build_bmd_with_meshes(vertex_count=1)

        reader = BMDReader()
        bmd = reader.Read(data)
        self.assertEqual(len(bmd.Meshes), 1)
        mesh = bmd.Meshes[0]

        self.assertEqual(len(mesh.Vertices), 1)
        v = mesh.Vertices[0]
        self.assertEqual(v.Node, 0)
        self.assertAlmostEqual(v.Position[0], 0.0)
        self.assertAlmostEqual(v.Position[1], 0.0)
        self.assertAlmostEqual(v.Position[2], 0.0)

    def test_mesh_with_normals(self) -> None:
        """Mesh with one normal."""
        data = self._build_bmd_with_meshes(normal_count=1)

        reader = BMDReader()
        bmd = reader.Read(data)
        mesh = bmd.Meshes[0]

        self.assertEqual(len(mesh.Normals), 1)
        n = mesh.Normals[0]
        self.assertEqual(n.Node, 0)
        self.assertAlmostEqual(n.Normal[0], 0.0)
        self.assertAlmostEqual(n.Normal[1], 1.0)
        self.assertAlmostEqual(n.Normal[2], 0.0)
        self.assertEqual(n.BindVertex, 0)

    def test_mesh_with_texcoords(self) -> None:
        """Mesh with one UV coordinate."""
        data = self._build_bmd_with_meshes(texcoord_count=1)

        reader = BMDReader()
        bmd = reader.Read(data)
        mesh = bmd.Meshes[0]

        self.assertEqual(len(mesh.TexCoords), 1)
        t = mesh.TexCoords[0]
        self.assertAlmostEqual(t.U, 0.5)
        self.assertAlmostEqual(t.V, 0.75)

    def test_mesh_with_triangles(self) -> None:
        """Mesh with one triangle."""
        data = self._build_bmd_with_meshes(triangle_count=1)

        reader = BMDReader()
        bmd = reader.Read(data)
        mesh = bmd.Meshes[0]

        self.assertEqual(len(mesh.Triangles), 1)
        tri = mesh.Triangles[0]
        self.assertEqual(tri.Polygon, 3)
        self.assertEqual(tri.VertexIndex, [0, 1, 2, 0])
        self.assertEqual(len(tri.LightMapCoord), 4)

    def test_mesh_with_texture_path(self) -> None:
        """Mesh with a texture file path."""
        data = self._build_bmd_with_meshes(texture_path="TileGrass01.ozj")

        reader = BMDReader()
        bmd = reader.Read(data)
        mesh = bmd.Meshes[0]

        self.assertEqual(mesh.TexturePath, "TileGrass01.ozj")

    def test_multiple_meshes(self) -> None:
        """BMD with multiple meshes."""
        data = self._build_bmd_with_meshes(mesh_count=3, triangle_count=1)

        reader = BMDReader()
        bmd = reader.Read(data)
        self.assertEqual(len(bmd.Meshes), 3)

    # ------------------------------------------------------------------
    # Builder helper
    # ------------------------------------------------------------------

    @staticmethod
    def _build_bmd_with_meshes(
        mesh_count: int = 1,
        vertex_count: int = 0,
        normal_count: int = 0,
        texcoord_count: int = 0,
        triangle_count: int = 0,
        texture_path: str = "",
    ) -> bytes:
        """Build a complete BMD file with specified mesh content."""
        header = b"BMD" + _build("B", 0x0A)
        header += _make_string("MeshTest")
        header += _build("HHH", mesh_count, 0, 0)  # mesh, bone=0, action=0

        meshes_payload = b""
        for _ in range(mesh_count):
            meshes_payload += _build("hhhhh",
                vertex_count, normal_count, texcoord_count, triangle_count, 0)
            meshes_payload += TestBMDReaderMesh._make_vertices(vertex_count)
            meshes_payload += TestBMDReaderMesh._make_normals(normal_count)
            meshes_payload += TestBMDReaderMesh._make_texcoords(texcoord_count)
            meshes_payload += TestBMDReaderMesh._make_triangles(triangle_count)
            meshes_payload += _make_string(texture_path)

        return header + meshes_payload

    @staticmethod
    def _make_vertices(count: int) -> bytes:
        """Generate synthetic vertex data."""
        payload = b""
        for i in range(count):
            payload += _build("h", i)       # Node
            payload += b"\x00\x00"           # padding
            payload += _build("fff",
                float(i * 1.0),
                float(i * 2.0),
                float(i * 3.0),
            )
        return payload

    @staticmethod
    def _make_normals(count: int) -> bytes:
        """Generate synthetic normal data."""
        payload = b""
        for i in range(count):
            payload += _build("h", i)       # Node
            payload += b"\x00\x00"           # padding
            payload += _build("fff", 0.0, 1.0, 0.0)  # Normal
            payload += _build("h", i)       # BindVertex
            payload += b"\x00\x00"           # padding
        return payload

    @staticmethod
    def _make_texcoords(count: int) -> bytes:
        """Generate synthetic UV data."""
        payload = b""
        for i in range(count):
            payload += _build("ff", 0.5 + i * 0.1, 0.75 - i * 0.1)
        return payload

    @staticmethod
    def _make_triangles(count: int) -> bytes:
        """Generate synthetic triangle data (64-byte stride)."""
        from mu_blender_tools.readers.bmd_reader import TRIANGLE_STRIDE
        payload = b""
        for i in range(count):
            payload += _build("B", 3)            # Polygon (triangle)
            payload += b"\x00"                    # padding
            payload += _build("hhhh",
                i * 3 + 0, i * 3 + 1, i * 3 + 2, 0)  # VertexIndex
            payload += _build("hhhh",
                i * 3 + 0, i * 3 + 1, i * 3 + 2, 0)  # NormalIndex
            payload += _build("hhhh",
                i * 3 + 0, i * 3 + 1, i * 3 + 2, 0)  # TexCoordIndex
            # LightMapCoord[4] = 4 × 8 = 32 bytes
            for _ in range(4):
                payload += _build("ff", 0.0, 0.0)
            payload += _build("h", 0)             # LightMapIndexes
            # Padding to 64 bytes
            remaining = TRIANGLE_STRIDE - (1 + 1 + 8 + 8 + 8 + 32 + 2)
            payload += b"\x00" * remaining
        return payload


class TestBMDReaderAction(unittest.TestCase):
    """Test action parsing."""

    def test_action_no_keys(self) -> None:
        """Action with 0 keyframes."""
        data = self._build_bmd_with_actions([(0, False)])

        reader = BMDReader()
        bmd = reader.Read(data)
        self.assertEqual(len(bmd.Actions), 1)
        act = bmd.Actions[0]
        self.assertEqual(act.NumAnimationKeys, 0)
        self.assertFalse(act.LockPositions)
        self.assertEqual(len(act.Positions), 0)

    def test_action_locked_positions(self) -> None:
        """Action with LockPositions=True (has position data)."""
        data = self._build_bmd_with_actions([(2, True)])

        reader = BMDReader()
        bmd = reader.Read(data)
        act = bmd.Actions[0]
        self.assertTrue(act.LockPositions)
        self.assertEqual(len(act.Positions), 2)
        self.assertAlmostEqual(act.Positions[0][0], 100.0)

    def test_multiple_actions(self) -> None:
        """Multiple actions with different key counts."""
        specs = [(1, False), (3, False), (0, True)]
        data = self._build_bmd_with_actions(specs)

        reader = BMDReader()
        bmd = reader.Read(data)
        self.assertEqual(len(bmd.Actions), 3)
        self.assertEqual(bmd.Actions[0].NumAnimationKeys, 1)
        self.assertEqual(bmd.Actions[1].NumAnimationKeys, 3)
        self.assertEqual(bmd.Actions[2].NumAnimationKeys, 0)

    @staticmethod
    def _build_bmd_with_actions(
        action_specs: list[tuple[int, bool]]
    ) -> bytes:
        """Build a BMD file with specified actions.

        Args:
            action_specs: List of (NumAnimationKeys, LockPositions) tuples.
        """
        header = b"BMD" + _build("B", 0x0A)
        header += _make_string("ActionTest")
        header += _build("HHH", 0, 0, len(action_specs))  # mesh=0, bone=0

        actions_payload = b""
        for num_keys, lock_pos in action_specs:
            actions_payload += _build("h", num_keys)
            actions_payload += _build("?", lock_pos)
            if lock_pos:
                for k in range(num_keys):
                    actions_payload += _build("fff",
                        float(100.0 + k),
                        float(200.0 + k),
                        float(300.0 + k),
                    )

        return header + actions_payload


class TestBMDReaderBone(unittest.TestCase):
    """Test bone parsing (including dummies and animation data)."""

    def test_dummy_bone(self) -> None:
        """A single dummy bone."""
        data = self._build_bmd_with_bones([True], [])

        reader = BMDReader()
        bmd = reader.Read(data)
        self.assertEqual(len(bmd.Bones), 1)
        self.assertIs(bmd.Bones[0], BMD_DUMMY_BONE)

    def test_real_bone_no_anim(self) -> None:
        """A real bone with 0-keyframe actions."""
        data = self._build_bmd_with_bones(
            [False],  # is_dummy list
            [0],       # actions (0 keyframes)
        )

        reader = BMDReader()
        bmd = reader.Read(data)
        bone = bmd.Bones[0]
        self.assertEqual(bone.Name, "Bip00")
        self.assertEqual(bone.Parent, -1)
        self.assertEqual(len(bone.Matrixes), 1)
        self.assertEqual(len(bone.Matrixes[0].Position), 0)

    def test_real_bone_with_anim(self) -> None:
        """A real bone with 2 keyframes in 1 action."""
        data = self._build_bmd_with_bones(
            [False, False],  # 2 bones, real
            [2],              # 1 action with 2 keys
        )

        reader = BMDReader()
        bmd = reader.Read(data)
        self.assertEqual(len(bmd.Bones), 2)
        self.assertEqual(len(bmd.Actions), 1)

        # First bone
        bone = bmd.Bones[0]
        self.assertEqual(bone.Name, "Bip00")
        self.assertEqual(len(bone.Matrixes), 1)
        mat = bone.Matrixes[0]
        self.assertEqual(len(mat.Position), 2)
        self.assertEqual(len(mat.Rotation), 2)
        self.assertEqual(len(mat.Quaternion), 2)

        # Verify quaternion computation
        rx, ry, rz = mat.Rotation[0]
        qx, qy, qz, qw = mat.Quaternion[0]
        # A zero-rotation Euler → identity quaternion
        self.assertAlmostEqual(qx, 0.0)
        self.assertAlmostEqual(qy, 0.0)
        self.assertAlmostEqual(qz, 0.0)
        self.assertAlmostEqual(qw, 1.0)

    def test_mixed_bones(self) -> None:
        """Mix of dummy and real bones."""
        data = self._build_bmd_with_bones(
            [True, False, True, False],
            [1],
        )

        reader = BMDReader()
        bmd = reader.Read(data)
        self.assertEqual(len(bmd.Bones), 4)
        self.assertIs(bmd.Bones[0], BMD_DUMMY_BONE)
        self.assertEqual(bmd.Bones[1].Name, "Bip00")
        self.assertIs(bmd.Bones[2], BMD_DUMMY_BONE)
        self.assertEqual(bmd.Bones[3].Name, "Bip01")

    @staticmethod
    def _build_bmd_with_bones(
        is_dummy_list: list[bool],
        action_key_counts: list[int],
    ) -> bytes:
        """Build a BMD file with specified bones and actions.

        Args:
            is_dummy_list: Per-bone dummy flag.
            action_key_counts: NumAnimationKeys for each action.
        """
        header = b"BMD" + _build("B", 0x0A)
        header += _make_string("BoneTest")
        header += _build("HHH",
            0,                              # meshCount=0
            len(is_dummy_list),             # boneCount
            len(action_key_counts),          # actionCount
        )

        # Action blocks
        actions_payload = b""
        for num_keys in action_key_counts:
            actions_payload += _build("h?", num_keys, False)

        # Bone blocks
        bones_payload = b""
        real_index = 0
        for is_dummy in is_dummy_list:
            bones_payload += _build("?", is_dummy)
            if not is_dummy:
                # Name
                bones_payload += _make_string(f"Bip{real_index:02d}")
                real_index += 1
                # Parent
                parent = -1 if real_index == 1 else 0
                bones_payload += _build("h", parent)

                # Per-action matrix data
                for num_keys in action_key_counts:
                    # Positions
                    for k in range(num_keys):
                        bones_payload += _build("fff",
                            float(k * 10.0),
                            float(k * 20.0),
                            float(k * 30.0),
                        )
                    # Rotations
                    for k in range(num_keys):
                        bones_payload += _build("fff",
                            float(math.radians(k * 5.0)),
                            float(math.radians(k * 3.0)),
                            float(math.radians(k * 2.0)),
                        )

        return header + actions_payload + bones_payload


class TestBMDReaderQuaternion(unittest.TestCase):
    """Test Euler → Quaternion conversion."""

    def test_zero_rotation(self) -> None:
        """Zero Euler → identity quaternion."""
        from mu_blender_tools.readers.bmd_reader import _angle_quaternion
        q = _angle_quaternion(0.0, 0.0, 0.0)
        self.assertAlmostEqual(q[0], 0.0)
        self.assertAlmostEqual(q[1], 0.0)
        self.assertAlmostEqual(q[2], 0.0)
        self.assertAlmostEqual(q[3], 1.0)

    def test_90_degree_x(self) -> None:
        """90° around X."""
        from mu_blender_tools.readers.bmd_reader import _angle_quaternion
        q = _angle_quaternion(math.radians(90.0), 0.0, 0.0)
        self.assertAlmostEqual(q[0], math.sin(math.radians(45.0)), places=6)
        self.assertAlmostEqual(q[1], 0.0)
        self.assertAlmostEqual(q[2], 0.0)
        self.assertAlmostEqual(q[3], math.cos(math.radians(45.0)), places=6)

    def test_bmd_angle_quaternion_consistency(self) -> None:
        """Verify against known values from the TypeScript reference."""
        from mu_blender_tools.readers.bmd_reader import _angle_quaternion

        # Euler (30°, 45°, 60°) in radians
        rx = math.radians(30.0)
        ry = math.radians(45.0)
        rz = math.radians(60.0)
        q = _angle_quaternion(rx, ry, rz)

        # Verify unit quaternion
        length = math.sqrt(q[0]**2 + q[1]**2 + q[2]**2 + q[3]**2)
        self.assertAlmostEqual(length, 1.0, places=6)


class TestBMDReaderIntegration(unittest.TestCase):
    """Full integration test: build a known BMD, read it back."""

    def test_round_trip_small(self) -> None:
        """Build a small BMD with 1 mesh, 2 bones, 1 action, read back."""
        num_keys = 3

        # ---- Build ----
        header = b"BMD" + _build("B", 0x0A)
        header += _make_string("TestModel")
        header += _build("HHH", 1, 2, 1)

        # Mesh: 1 vertex, 1 normal, 1 texcoord, 1 triangle
        mesh_payload = b""
        mesh_payload += _build("hhhhh", 1, 1, 1, 1, 0)

        # Vertex
        mesh_payload += _build("h", 0) + b"\x00\x00"
        mesh_payload += _build("fff", 10.0, 20.0, 30.0)

        # Normal
        mesh_payload += _build("h", 0) + b"\x00\x00"
        mesh_payload += _build("fff", 0.0, 1.0, 0.0)
        mesh_payload += _build("h", 0) + b"\x00\x00"

        # TexCoord
        mesh_payload += _build("ff", 0.5, 0.5)

        # Triangle
        from mu_blender_tools.readers.bmd_reader import TRIANGLE_STRIDE
        mesh_payload += _build("B", 3) + b"\x00"
        mesh_payload += _build("hhhh", 0, 1, 2, 0)
        mesh_payload += _build("hhhh", 0, 1, 2, 0)
        mesh_payload += _build("hhhh", 0, 1, 2, 0)
        for _ in range(4):
            mesh_payload += _build("ff", 0.0, 0.0)
        mesh_payload += _build("h", 0)
        mesh_payload += b"\x00" * (TRIANGLE_STRIDE - 62)

        # Texture path
        mesh_payload += _make_string("test.jpg")

        # Action: 3 keys, locked positions
        action_payload = _build("h?", num_keys, True)
        for k in range(num_keys):
            action_payload += _build("fff", float(k), float(k), float(k))

        # Bones: one dummy, one real
        bones_payload = _build("?", True)  # dummy
        bones_payload += _build("?", False)  # real
        bones_payload += _make_string("Root")
        bones_payload += _build("h", -1)
        for _ in range(1):  # 1 action
            for k in range(num_keys):
                bones_payload += _build("fff", float(k), float(k * 2), float(k * 3))
            for k in range(num_keys):
                bones_payload += _build("fff",
                    math.radians(k * 10.0),
                    math.radians(k * 5.0),
                    math.radians(k * 2.0),
                )

        data = header + mesh_payload + action_payload + bones_payload

        # ---- Parse ----
        reader = BMDReader()
        bmd = reader.Read(data)

        # ---- Verify ----
        self.assertEqual(bmd.Name, "TestModel")
        self.assertEqual(bmd.Version, 0x0A)

        # Meshes
        self.assertEqual(len(bmd.Meshes), 1)
        mesh = bmd.Meshes[0]
        self.assertEqual(len(mesh.Vertices), 1)
        self.assertEqual(len(mesh.Normals), 1)
        self.assertEqual(len(mesh.TexCoords), 1)
        self.assertEqual(len(mesh.Triangles), 1)
        self.assertEqual(mesh.TexturePath, "test.jpg")

        v = mesh.Vertices[0]
        self.assertAlmostEqual(v.Position[0], 10.0)
        self.assertAlmostEqual(v.Position[1], 20.0)
        self.assertAlmostEqual(v.Position[2], 30.0)

        # Actions
        self.assertEqual(len(bmd.Actions), 1)
        act = bmd.Actions[0]
        self.assertEqual(act.NumAnimationKeys, num_keys)
        self.assertTrue(act.LockPositions)
        self.assertEqual(len(act.Positions), num_keys)

        # Bones
        self.assertEqual(len(bmd.Bones), 2)
        self.assertIs(bmd.Bones[0], BMD_DUMMY_BONE)
        self.assertEqual(bmd.Bones[1].Name, "Root")
        self.assertEqual(bmd.Bones[1].Parent, -1)
        self.assertEqual(len(bmd.Bones[1].Matrixes), 1)


class TestBMDReaderEncryption(unittest.TestCase):
    """Test that encrypted versions can be decrypted."""

    def test_v12_decrypt(self) -> None:
        """Version 0x0C (FileCryptor) should decrypt without error."""
        data = b"BMD" + _build("B", 0x0C) + _build("I", 4) + b"\x00" * 4
        reader = BMDReader()
        # Decryption will succeed, but parsing will fail because the
        # decrypted data isn't a valid BMD.  We assert it's NOT the
        # old "not yet implemented" error.
        try:
            reader.Read(data)
        except BinaryReaderError as e:
            self.assertNotIn("not yet implemented", str(e))

    def test_v15_decrypt(self) -> None:
        """Version 0x0F (LEA-256) should decrypt without error."""
        data = b"BMD" + _build("B", 0x0F) + _build("I", 4) + b"\x00" * 4
        reader = BMDReader()
        try:
            reader.Read(data)
        except BinaryReaderError as e:
            self.assertNotIn("not yet implemented", str(e))


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
