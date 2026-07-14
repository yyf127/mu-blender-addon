# MU Online Blender Tools - BMD Data Types
#
# Python dataclasses matching the C# reference types in Client.Data.BMD/.
#
# Reference files:
#   BMD.cs, BMDTextureMesh.cs, BMDTextureVertex.cs, BMDTextureNormal.cs,
#   BMDTexCoord.cs, BMDTriangle.cs, BMDTextureAction.cs, BMDTextureBone.cs,
#   BMDBoneMatrix.cs
#
# Field names are kept identical to the C# source for traceability.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ======================================================================
# BMDTexCoord
# ======================================================================


@dataclass
class BMDTexCoord:
    """UV texture coordinate.

    C#: Client.Data.BMD.BMDTexCoord
    File: BMDTexCoord.cs

    StructLayout(Sequential, Pack = 4)
    Fields: U(float), V(float) — 8 bytes total.
    """
    U: float = 0.0
    V: float = 0.0


# ======================================================================
# BMDTriangle
# ======================================================================


@dataclass
class BMDTriangle:
    """A triangle (or quad) face with vertex/normal/texcoord indices.

    C#: Client.Data.BMD.BMDTriangle
    File: BMDTriangle.cs

    StructLayout(Sequential, Pack = 4)
    Stride: 64 bytes (verified against TypeScript reference).

    The Polygon field determines the primitive type:
      3 = triangle, 4 = quad (4th index is unused for triangles).
    """
    Polygon: int = 0                    # byte
    VertexIndex: list[int] = field(default_factory=lambda: [0, 0, 0, 0])   # short[4]
    NormalIndex: list[int] = field(default_factory=lambda: [0, 0, 0, 0])   # short[4]
    TexCoordIndex: list[int] = field(default_factory=lambda: [0, 0, 0, 0]) # short[4]
    LightMapCoord: list[BMDTexCoord] = field(default_factory=list)          # BMDTexCoord[4]
    LightMapIndexes: int = 0            # short


# ======================================================================
# BMDTextureVertex
# ======================================================================


@dataclass
class BMDTextureVertex:
    """Vertex with bone attachment and position.

    C#: Client.Data.BMD.BMDTextureVertex
    File: BMDTextureVertex.cs

    StructLayout(Sequential, Pack = 4)
    Fields: Node(short), padding(2 bytes), Position(3×float) — 16 bytes total.

    Node is the bone index that influences this vertex.
    """
    Node: int = 0                       # short — bone index
    Position: tuple[float, float, float] = (0.0, 0.0, 0.0)  # Vector3 (x, y, z)


# ======================================================================
# BMDTextureNormal
# ======================================================================


@dataclass
class BMDTextureNormal:
    """Normal vector with bone attachment.

    C#: Client.Data.BMD.BMDTextureNormal
    File: BMDTextureNormal.cs

    StructLayout(Sequential, Pack = 4)
    Fields: Node(short), padding(2), Normal(3×float), BindVertex(short), padding(2)
    — 20 bytes total.

    BindVertex is the index of the vertex this normal belongs to.
    """
    Node: int = 0                       # short — bone index
    Normal: tuple[float, float, float] = (0.0, 0.0, 0.0)  # Vector3 (nx, ny, nz)
    BindVertex: int = 0                 # short — links to vertex index


# ======================================================================
# BMDTextureMesh
# ======================================================================


@dataclass
class BMDTextureMesh:
    """A single mesh (subset) within a BMD model.

    C#: Client.Data.BMD.BMDTextureMesh
    File: BMDTextureMesh.cs
    """
    Vertices: list[BMDTextureVertex] = field(default_factory=list)
    Normals: list[BMDTextureNormal] = field(default_factory=list)
    TexCoords: list[BMDTexCoord] = field(default_factory=list)
    Triangles: list[BMDTriangle] = field(default_factory=list)
    Texture: int = 0                    # short — texture index
    TexturePath: str = ""               # string (32 bytes in file, null-terminated)

    # Custom blending mode (loaded from bmd_blending_config.json in C# reference).
    # Not part of the binary format; used by builders later.
    BlendingMode: Optional[str] = None


# ======================================================================
# BMDBoneMatrix
# ======================================================================


@dataclass
class BMDBoneMatrix:
    """Bone animation data for one action.

    C#: Client.Data.BMD.BMDBoneMatrix
    File: BMDBoneMatrix.cs

    Contains arrays of (position, rotation, quaternion) per keyframe.

    Position and Rotation are read directly from the file.
    Quaternion is computed from Rotation (Euler angles) at parse time,
    matching C# MathUtils.AngleQuaternion() and TS bmdAngleToQuaternion().
    """
    Position: list[tuple[float, float, float]] = field(default_factory=list)    # Vector3[]
    Rotation: list[tuple[float, float, float]] = field(default_factory=list)    # Vector3[] (Euler)
    Quaternion: list[tuple[float, float, float, float]] = field(default_factory=list)  # Quaternion[]


# ======================================================================
# BMDTextureBone
# ======================================================================


@dataclass
class BMDTextureBone:
    """A single bone in the skeleton.

    C#: Client.Data.BMD.BMDTextureBone
    File: BMDTextureBone.cs

    A "dummy" bone has no name/parent/matrices — it is a placeholder that
    maintains bone index alignment.
    """
    Name: str = ""                      # string (32 bytes in file)
    Parent: int = -1                    # short — parent bone index, -1 = root
    Matrixes: list[BMDBoneMatrix] = field(default_factory=list)  # one per Action


# Sentinel instance for dummy bones (matches C# BMDTextureBone.Dummy)
BMD_DUMMY_BONE = BMDTextureBone(Name="Dummy")


# ======================================================================
# BMDTextureAction
# ======================================================================


@dataclass
class BMDTextureAction:
    """An animation action (clip) with keyframe data.

    C#: Client.Data.BMD.BMDTextureAction
    File: BMDTextureAction.cs

    NumAnimationKeys: number of keyframes in this action.
    LockPositions: if True, bone positions are locked (only rotation animates).
    Positions: root/overall position offsets per keyframe (only if LockPositions).
    PlaySpeed: playback speed multiplier (default 1.0).
    """
    NumAnimationKeys: int = 0           # int (stored as Int16 in file)
    LockPositions: bool = False
    Positions: list[tuple[float, float, float]] = field(default_factory=list)  # Vector3[]
    PlaySpeed: float = 1.0


# ======================================================================
# BMD (Top-level container)
# ======================================================================


@dataclass
class BMD:
    """Top-level BMD model container.

    C#: Client.Data.BMD.BMD
    File: BMD.cs

    Meshes:   geometry data (vertices, normals, UVs, triangles, texture refs)
    Bones:    skeleton hierarchy (with per-action animation matrices)
    Actions:  animation action descriptors (keyframe counts, position locks)
    """
    Version: int = 0x0C                 # byte — file format version
    Name: str = ""                      # string (32 bytes in file)
    Meshes: list[BMDTextureMesh] = field(default_factory=list)
    Bones: list[BMDTextureBone] = field(default_factory=list)
    Actions: list[BMDTextureAction] = field(default_factory=list)
