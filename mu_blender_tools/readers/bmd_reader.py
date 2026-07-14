# MU Online Blender Tools - BMDReader
#
# Reads MU Online .bmd model files and produces a BMD data structure.
#
# Strictly follows the C# reference implementation:
#   https://github.com/xulek/muonline/blob/main/Client.Data/BMD/BMDReader.cs
#
# BMD file structure (all multi-byte values are little-endian):
#
#   [0-2]   Magic: "BMD" (3 bytes)
#   [3]     Version byte
#   [4..]   Optional: encrypted payload (version 0x0C = FileCryptor, 0x0F = LEA-256)
#   [4/8..] File body:
#       Name        (32 bytes, null-terminated ASCII)
#       MeshCount   (uint16)
#       BoneCount   (uint16)
#       ActionCount (uint16)
#       [Meshes]    MeshCount × MeshBlock
#       [Actions]   ActionCount × ActionBlock
#       [Bones]     BoneCount × BoneBlock
#
# Design:
#   - Uses BinaryReader from Phase 1
#   - No bpy imports — pure data layer, independently testable
#   - Field names match C# exactly
#   - Decryption placeholder: actual crypto logic will be in later phases

from __future__ import annotations

import logging
import math
from typing import Optional

from .binary_reader import BinaryReader, BinaryReaderError, SeekOrigin
from .bmd_types import (
    BMD,
    BMDTexCoord,
    BMDTriangle,
    BMDTextureVertex,
    BMDTextureNormal,
    BMDTextureMesh,
    BMDTextureAction,
    BMDTextureBone,
    BMDBoneMatrix,
    BMD_DUMMY_BONE,
)

_logger = logging.getLogger("mu_blender_tools")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_FILE_TYPE: str = "BMD"
"""Expected 3-byte magic string."""

MINIMAL_BUFFER_SIZE: int = 8
"""Smallest valid BMD file (4-byte header + 4-byte minimum content)."""

STRING_LENGTH: int = 32
"""Fixed length of name/path strings in the file (null-terminated ASCII)."""

TRIANGLE_STRIDE: int = 64
"""Byte size of a BMDTriangle struct on disk (verified against TS reference)."""

SUPPORTED_VERSIONS: tuple[int, ...] = (0x0A, 0x0C, 0x0F)
"""BMD format versions handled by this reader.

Version  Encryption
-------  ----------
0x0A     None (plain)
0x0C     FileCryptor (to be implemented in crypto module)
0x0F     LEA-256 (to be implemented in crypto module)
"""


# ======================================================================
# Helper: Euler → Quaternion conversion
# ======================================================================


def _angle_quaternion(
    rx: float, ry: float, rz: float
) -> tuple[float, float, float, float]:
    """Convert Euler angles (XYZ order) to a quaternion.

    Matches C# ``MathUtils.AngleQuaternion()`` and TypeScript
    ``bmdAngleToQuaternion()`` in the BMD viewer.

    Args:
        rx: Rotation around X-axis (Euler, radians).
        ry: Rotation around Y-axis (Euler, radians).
        rz: Rotation around Z-axis (Euler, radians).

    Returns:
        Tuple ``(x, y, z, w)`` quaternion.
    """
    hx = rx * 0.5
    hy = ry * 0.5
    hz = rz * 0.5

    sx = math.sin(hx)
    cx = math.cos(hx)
    sy = math.sin(hy)
    cy = math.cos(hy)
    sz = math.sin(hz)
    cz = math.cos(hz)

    qw = cx * cy * cz + sx * sy * sz
    qx = sx * cy * cz - cx * sy * sz
    qy = cx * sy * cz + sx * cy * sz
    qz = cx * cy * sz - sx * sy * cz

    return (qx, qy, qz, qw)


# ======================================================================
# BMDReader
# ======================================================================


class BMDReader:
    """Reads a BMD file from raw bytes and returns a ``BMD`` data structure.

    Usage::

        with open("model.bmd", "rb") as f:
            data = f.read()
        reader = BMDReader()
        bmd = reader.Read(data)
        print(bmd.Name, len(bmd.Meshes), "meshes")

    The parsing flow matches ``BMDReader.Read()`` in the C# reference:

        1. ValidateHeader  — check magic and version
        2. DecryptIfNeeded — handle encrypted versions
        3. ReadHeader      — name, counts
        4. ReadMeshes      — geometry data
        5. ReadActions     — animation action descriptors
        6. ReadBones       — skeleton + per-action keyframe data
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def Read(self, data: bytes | bytearray) -> BMD:
        """Parse a complete BMD file from raw bytes.

        This is the main entry point, corresponding to
        ``BMDReader.Read(byte[] buffer)`` in the C# reference.

        Args:
            data: Raw file contents as bytes.

        Returns:
            A fully-populated ``BMD`` instance.

        Raises:
            BinaryReaderError: On invalid header, unsupported version,
                               or truncated data.
        """
        br = BinaryReader(data)

        self._ValidateHeader(br)

        # After ValidateHeader consumed 3 magic bytes, offset is at 3 (version byte)
        version = br.PeekBytes(1)[0]

        # Snapshot the full raw buffer BEFORE any decryption or seeking,
        # so _DecryptIfNeeded has access to the original encrypted content.
        _raw_buffer: bytes = br.PeekBytes(br.Remaining)  # bytes at offset 3..end

        if version not in SUPPORTED_VERSIONS:
            raise BinaryReaderError(
                f"Unsupported BMD version 0x{version:02X}. "
                f"Supported: {[f'0x{v:02X}' for v in SUPPORTED_VERSIONS]}"
            )

        self._DecryptIfNeeded(br, version, _raw_buffer)

        # After decryption (or skip of 4-byte header), read from offset 4
        br.Seek(4, SeekOrigin.Begin)

        name = br.ReadString(STRING_LENGTH)  # 32 bytes
        mesh_count = br.ReadUInt16()
        bone_count = br.ReadUInt16()
        action_count = br.ReadUInt16()

        _logger.debug(
            "BMD: name=%s meshes=%d bones=%d actions=%d",
            name, mesh_count, bone_count, action_count,
        )

        # File order: Meshes → Actions → Bones (matching C# BMDReader.Read())
        meshes = self._ReadMeshes(br, mesh_count)
        actions = self._ReadActions(br, action_count)
        bones = self._ReadBones(br, bone_count, actions)

        return BMD(
            Version=version,
            Name=name,
            Meshes=meshes,
            Bones=bones,
            Actions=actions,
        )

    # ------------------------------------------------------------------
    # Header validation
    # ------------------------------------------------------------------

    @staticmethod
    def _ValidateHeader(br: BinaryReader) -> None:
        """Validate the BMD magic number and minimum size.

        C#: ``ValidateBuffer(byte[] buffer)``
        """
        if br.Size < MINIMAL_BUFFER_SIZE:
            raise BinaryReaderError(
                f"BMD file too small: {br.Size} bytes "
                f"(minimum {MINIMAL_BUFFER_SIZE})."
            )

        magic = br.ReadBytes(3)
        if magic.decode("ascii", errors="replace") != EXPECTED_FILE_TYPE:
            raise BinaryReaderError(
                f"Invalid BMD magic: expected '{EXPECTED_FILE_TYPE}', "
                f"got '{magic.decode('ascii', errors='replace')}'."
            )

    # ------------------------------------------------------------------
    # Decryption
    # ------------------------------------------------------------------

    @staticmethod
    def _DecryptIfNeeded(
        br: BinaryReader, version: int,
        raw_from_offset_3: bytes,
    ) -> None:
        """Decrypt the buffer in-place if the version requires it.

        C#: ``DecryptBufferIfNeeded(byte[] buffer, byte version)``

        Version 0x0C → FileCryptor (XOR-based)
        Version 0x0F → LEA-256 (128-bit block cipher, 256-bit key)

        Encrypted layout (from C# reference):
            offset 4:  encrypted size (Int32, little-endian)
            offset 8:  encrypted payload of *size* bytes
            After decryption the plain data is written back at offset 4.

        Args:
            br: BinaryReader positioned at offset 3 (version byte).
            version: BMD format version (0x0C or 0x0F).
            raw_from_offset_3: Snapshot of the buffer from offset 3 onward,
                taken before any decryption or seeking.
        """
        if version not in (0x0C, 0x0F):
            return  # plain — nothing to do

        # The version byte is the first byte of raw_from_offset_3.
        # Reconstruct the full original buffer:
        #   bytes 0-2: "BMD" (we peeked them earlier, prepend them)
        #   bytes 3..: raw_from_offset_3
        full_raw = b"BMD" + raw_from_offset_3
        raw = bytearray(full_raw)

        # Read encrypted size at offset 4 (little-endian Int32)
        import struct as _struct
        enc_size = _struct.unpack_from("<I", raw, 4)[0]
        enc_end = 8 + enc_size  # data at offset 8..(8+enc_size-1)

        # Read encrypted payload
        enc_bytes = bytes(raw[8:enc_end])

        # Validate payload size
        if version == 0x0F and len(enc_bytes) % 16 != 0:
            raise BinaryReaderError(
                f"LEA-256 encrypted payload size ({len(enc_bytes)}) "
                f"is not a multiple of 16 — file may be corrupted"
            )

        # Decrypt
        if version == 0x0C:
            from ._file_cryptor import decrypt as _file_decrypt
            dec_bytes = _file_decrypt(enc_bytes)
        elif version == 0x0F:
            from ._lea_cipher import lea256_decrypt
            dec_bytes = lea256_decrypt(enc_bytes)
        else:
            raise BinaryReaderError(
                f"Unsupported encryption version 0x{version:02X}"
            )

        # Replace encrypted region with decrypted data
        raw[4:4 + len(dec_bytes)] = dec_bytes

        # Create a fresh BinaryReader with the decrypted buffer
        new_br = BinaryReader(bytes(raw))
        br._buffer = new_br._buffer
        br._size = new_br._size
        br._offset = 0

    # ------------------------------------------------------------------
    # Mesh reading
    # ------------------------------------------------------------------

    @staticmethod
    def _ReadMeshes(br: BinaryReader, count: int) -> list[BMDTextureMesh]:
        """Read all mesh blocks.

        C#: ``ReadMeshes(BinaryReader br, int meshCount)``

        Each mesh block:
            numVertices  (Int16)
            numNormals   (Int16)
            numTexCoords (Int16)
            numTriangles (Int16)
            texture      (Int16)
            vertices     (BMDTextureVertex × numVertices)
            normals      (BMDTextureNormal × numNormals)
            texCoords    (BMDTexCoord × numTexCoords)
            triangles    (BMDTriangle × numTriangles)
            texturePath  (String × 32)
        """
        meshes: list[BMDTextureMesh] = []

        for _ in range(count):
            num_vertices = br.ReadInt16()
            num_normals = br.ReadInt16()
            num_texcoords = br.ReadInt16()
            num_triangles = br.ReadInt16()
            texture = br.ReadInt16()

            vertices = BMDReader._ReadTextureVertices(br, num_vertices)
            normals = BMDReader._ReadTextureNormals(br, num_normals)
            texcoords = BMDReader._ReadTexCoords(br, num_texcoords)
            triangles = BMDReader._ReadTriangles(br, num_triangles)
            texture_path = br.ReadString(STRING_LENGTH)

            meshes.append(BMDTextureMesh(
                Vertices=vertices,
                Normals=normals,
                TexCoords=texcoords,
                Triangles=triangles,
                Texture=texture,
                TexturePath=texture_path,
            ))

        return meshes

    # ------------------------------------------------------------------
    # Vertex / Normal / TexCoord / Triangle readers
    # ------------------------------------------------------------------

    @staticmethod
    def _ReadTextureVertices(
        br: BinaryReader, count: int
    ) -> list[BMDTextureVertex]:
        """Read an array of BMDTextureVertex.

        C#: ``br.ReadStructArray<BMDTextureVertex>(numVertices)``

        Layout (16 bytes each):
            Node       (Int16)      — bone index
            padding    (2 bytes)
            Position.X (Float32)
            Position.Y (Float32)
            Position.Z (Float32)
        """
        result: list[BMDTextureVertex] = []
        for _ in range(count):
            node = br.ReadInt16()
            br.Skip(2)  # padding
            x = br.ReadFloat()
            y = br.ReadFloat()
            z = br.ReadFloat()
            result.append(BMDTextureVertex(
                Node=node,
                Position=(x, y, z),
            ))
        return result

    @staticmethod
    def _ReadTextureNormals(
        br: BinaryReader, count: int
    ) -> list[BMDTextureNormal]:
        """Read an array of BMDTextureNormal.

        C#: ``br.ReadStructArray<BMDTextureNormal>(numNormals)``

        Layout (20 bytes each):
            Node          (Int16)
            padding       (2 bytes)
            Normal.X      (Float32)
            Normal.Y      (Float32)
            Normal.Z      (Float32)
            BindVertex    (Int16)
            padding       (2 bytes)
        """
        result: list[BMDTextureNormal] = []
        for _ in range(count):
            node = br.ReadInt16()
            br.Skip(2)  # padding
            nx = br.ReadFloat()
            ny = br.ReadFloat()
            nz = br.ReadFloat()
            bind_vertex = br.ReadInt16()
            br.Skip(2)  # padding
            result.append(BMDTextureNormal(
                Node=node,
                Normal=(nx, ny, nz),
                BindVertex=bind_vertex,
            ))
        return result

    @staticmethod
    def _ReadTexCoords(br: BinaryReader, count: int) -> list[BMDTexCoord]:
        """Read an array of BMDTexCoord.

        C#: ``br.ReadStructArray<BMDTexCoord>(numTexCoords)``

        Layout (8 bytes each):
            U (Float32)
            V (Float32)
        """
        result: list[BMDTexCoord] = []
        for _ in range(count):
            u = br.ReadFloat()
            v = br.ReadFloat()
            result.append(BMDTexCoord(U=u, V=v))
        return result

    @staticmethod
    def _ReadTriangles(br: BinaryReader, count: int) -> list[BMDTriangle]:
        """Read an array of BMDTriangle.

        C#: ``br.ReadStructArray<BMDTriangle>(numTriangles)``

        Stride: 64 bytes per triangle (verified against TS reference).

        Layout:
            offset  size  field
            ------  ----  -----
             0       1    Polygon (byte)
             1       1    padding
             2       8    VertexIndex[4]   (4 × Int16)
            10       8    NormalIndex[4]   (4 × Int16)
            18       8    TexCoordIndex[4] (4 × Int16)
            26      32    LightMapCoord[4] (4 × BMDTexCoord = 4 × 8)
            58       2    LightMapIndexes  (Int16)
            60       4    padding (to 64-byte stride)
        """
        result: list[BMDTriangle] = []
        for _ in range(count):
            polygon = br.ReadByte()
            br.Skip(1)  # padding to align next Int16

            v_idx = [br.ReadInt16() for _ in range(4)]
            n_idx = [br.ReadInt16() for _ in range(4)]
            t_idx = [br.ReadInt16() for _ in range(4)]

            # LightMapCoord[4] — read as 4 × BMDTexCoord
            lightmap: list[BMDTexCoord] = []
            for _ in range(4):
                lu = br.ReadFloat()
                lv = br.ReadFloat()
                lightmap.append(BMDTexCoord(U=lu, V=lv))

            lm_idx = br.ReadInt16()

            # Skip remaining padding (60 + 2 = 62, need 64)
            br.Skip(TRIANGLE_STRIDE - 62)

            result.append(BMDTriangle(
                Polygon=polygon,
                VertexIndex=v_idx,
                NormalIndex=n_idx,
                TexCoordIndex=t_idx,
                LightMapCoord=lightmap,
                LightMapIndexes=lm_idx,
            ))

        return result

    # ------------------------------------------------------------------
    # Action reading
    # ------------------------------------------------------------------

    @staticmethod
    def _ReadActions(br: BinaryReader, count: int) -> list[BMDTextureAction]:
        """Read all animation action descriptors.

        C#: ``ReadActions(BinaryReader br, int actionCount)``

        Each action block:
            NumAnimationKeys (Int16)
            LockPositions    (Bool — 1 byte)
            [if LockPositions] Positions (Vector3 × NumAnimationKeys)

        Note: NumAnimationKeys is stored as Int16 in the file but used as
        int in the C# data class.
        """
        actions: list[BMDTextureAction] = []

        for _ in range(count):
            num_keys = br.ReadInt16()
            lock_pos = br.ReadBool()

            positions: list[tuple[float, float, float]] = []
            if lock_pos:
                for _ in range(num_keys):
                    x = br.ReadFloat()
                    y = br.ReadFloat()
                    z = br.ReadFloat()
                    positions.append((x, y, z))

            actions.append(BMDTextureAction(
                NumAnimationKeys=num_keys,
                LockPositions=lock_pos,
                Positions=positions,
                PlaySpeed=1.0,
            ))

        return actions

    # ------------------------------------------------------------------
    # Bone reading
    # ------------------------------------------------------------------

    @staticmethod
    def _ReadBones(
        br: BinaryReader, count: int, actions: list[BMDTextureAction]
    ) -> list[BMDTextureBone]:
        """Read all bone blocks.

        C#: ``ReadBones(BinaryReader br, int boneCount, BMDTextureAction[] actions)``

        Each bone block:
            IsDummy (Bool — 1 byte)
            [if not dummy]:
                Name   (String × 32)
                Parent (Int16)
                [for each action]:
                    Positions   (Vector3 × action.NumAnimationKeys)
                    Rotations   (Vector3 × action.NumAnimationKeys)
                    [quaternions — computed, not stored]

        A "dummy" bone (IsDummy = True) has no further data and is used
        to maintain bone index alignment.
        """
        bones: list[BMDTextureBone] = []

        for _ in range(count):
            is_dummy = br.ReadBool()

            if is_dummy:
                bones.append(BMD_DUMMY_BONE)
                continue

            name = br.ReadString(STRING_LENGTH)
            parent = br.ReadInt16()

            matrixes: list[BMDBoneMatrix] = []

            for action in actions:
                num_keys = action.NumAnimationKeys

                # Position per keyframe
                positions: list[tuple[float, float, float]] = []
                for _ in range(num_keys):
                    x = br.ReadFloat()
                    y = br.ReadFloat()
                    z = br.ReadFloat()
                    positions.append((x, y, z))

                # Rotation per keyframe (Euler angles)
                rotations: list[tuple[float, float, float]] = []
                for _ in range(num_keys):
                    rx = br.ReadFloat()
                    ry = br.ReadFloat()
                    rz = br.ReadFloat()
                    rotations.append((rx, ry, rz))

                # Compute quaternions from Euler angles
                quaternions: list[tuple[float, float, float, float]] = []
                for rot in rotations:
                    q = _angle_quaternion(rot[0], rot[1], rot[2])
                    quaternions.append(q)

                matrixes.append(BMDBoneMatrix(
                    Position=positions,
                    Rotation=rotations,
                    Quaternion=quaternions,
                ))

            bones.append(BMDTextureBone(
                Name=name,
                Parent=parent,
                Matrixes=matrixes,
            ))

        return bones
