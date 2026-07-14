# MU Online Blender Tools - Manual MeshBuilder Test
#
# Run inside Blender 4.x:
#   blender --python tests/manual_test_mesh_builder.py
#
# Or from Blender's Text Editor: open and run this file.

"""
Manual test for MeshBuilder — creates synthetic BMD data and builds Blender meshes.

Creates:
  - "MU_Test_Single"  — one triangle mesh
  - "MU_Test_Multi"   — three meshes with different material indices
  - "MU_Test_Empty"   — empty (no mesh)
  - "MU_Test_UV_Normal" — mesh with UVs and custom normals
"""

import sys
import os

# Add addon root to path
ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_ROOT not in sys.path:
    sys.path.insert(0, ADDON_ROOT)

import bpy

# Clear scene
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

from mu_blender_tools.readers.bmd_types import (
    BMD,
    BMDTextureMesh,
    BMDTextureVertex,
    BMDTextureNormal,
    BMDTexCoord,
    BMDTriangle,
)
from mu_blender_tools.builders.mesh_builder import MeshBuilder


def make_vertex(node=0, x=0.0, y=0.0, z=0.0):
    return BMDTextureVertex(Node=node, Position=(x, y, z))


def make_normal(node=0, nx=0.0, ny=0.0, nz=1.0):
    return BMDTextureNormal(Node=node, Normal=(nx, ny, nz), BindVertex=0)


def make_texcoord(u=0.0, v=0.0):
    return BMDTexCoord(U=u, V=v)


def make_triangle(polygon=3, v=(0, 1, 2, 0), n=(0, 1, 2, 0), t=(0, 1, 2, 0)):
    return BMDTriangle(
        Polygon=polygon,
        VertexIndex=list(v),
        NormalIndex=list(n),
        TexCoordIndex=list(t),
        LightMapCoord=[],
        LightMapIndexes=0,
    )


def make_mesh(vertices=None, normals=None, texcoords=None, triangles=None, texture=0, texture_path=""):
    return BMDTextureMesh(
        Vertices=vertices or [],
        Normals=normals or [],
        TexCoords=texcoords or [],
        Triangles=triangles or [],
        Texture=texture,
        TexturePath=texture_path,
    )


# ======================================================================
# Test 1: Single triangle mesh
# ======================================================================

print("=" * 60)
print("Test 1: Single triangle mesh")
print("=" * 60)

verts = [
    make_vertex(x=0.0, y=0.0, z=0.0),
    make_vertex(x=1.0, y=0.0, z=0.0),
    make_vertex(x=0.5, y=1.0, z=0.0),
]
norms = [make_normal(nz=1.0) for _ in range(3)]
uvs = [
    make_texcoord(0.0, 0.0),
    make_texcoord(1.0, 0.0),
    make_texcoord(0.5, 1.0),
]
tris = [make_triangle(polygon=3, v=(0, 1, 2, 0), n=(0, 1, 2, 0), t=(0, 1, 2, 0))]

bmd_single = BMD(
    Version=0x0A, Name="MU_Test_Single",
    Meshes=[make_mesh(vertices=verts, normals=norms, texcoords=uvs, triangles=tris)],
)
objs = MeshBuilder.build_all_meshes(bmd_single, name="MU_Test_Single")
print(f"Created {len(objs)} object(s)")


# ======================================================================
# Test 2: Multiple meshes with different material indices
# ======================================================================

print("=" * 60)
print("Test 2: Multiple meshes (3) with material indices 0, 1, 2")
print("=" * 60)

multi_meshes = []
for mi in range(3):
    offset_x = mi * 2.0
    m_verts = [
        make_vertex(x=offset_x + 0.0, y=0.0, z=0.0),
        make_vertex(x=offset_x + 1.0, y=0.0, z=0.0),
        make_vertex(x=offset_x + 0.5, y=1.0, z=0.0),
    ]
    m_norms = [make_normal(nz=1.0) for _ in range(3)]
    m_uvs = [make_texcoord(0.0, 0.0), make_texcoord(1.0, 0.0), make_texcoord(0.5, 1.0)]
    m_tris = [make_triangle(polygon=3, v=(0, 1, 2, 0), n=(0, 1, 2, 0), t=(0, 1, 2, 0))]
    multi_meshes.append(make_mesh(
        vertices=m_verts, normals=m_norms, texcoords=m_uvs, triangles=m_tris,
        texture=mi, texture_path=f"mesh_{mi}.jpg",
    ))

bmd_multi = BMD(Version=0x0A, Name="MU_Test_Multi", Meshes=multi_meshes)
objs = MeshBuilder.build_all_meshes(bmd_multi, name="MU_Test_Multi")
print(f"Created {len(objs)} object(s)")


# ======================================================================
# Test 3: Empty BMD (no meshes)
# ======================================================================

print("=" * 60)
print("Test 3: Empty BMD (no meshes)")
print("=" * 60)

bmd_empty = BMD(Version=0x0A, Name="MU_Test_Empty", Meshes=[])
objs = MeshBuilder.build_all_meshes(bmd_empty, name="MU_Test_Empty")
print(f"Created {len(objs)} object(s)")


# ======================================================================
# Test 4: Mesh with UVs and normals (quad)
# ======================================================================

print("=" * 60)
print("Test 4: Quad mesh with UVs and custom normals")
print("=" * 60)

quad_verts = [
    make_vertex(x=-1.0, y=-1.0, z=0.0),
    make_vertex(x=1.0, y=-1.0, z=0.0),
    make_vertex(x=1.0, y=1.0, z=0.0),
    make_vertex(x=-1.0, y=1.0, z=0.0),
]
quad_norms = [make_normal(nz=1.0) for _ in range(4)]
quad_uvs = [
    make_texcoord(0.0, 0.0),
    make_texcoord(1.0, 0.0),
    make_texcoord(1.0, 1.0),
    make_texcoord(0.0, 1.0),
]
quad_tris = [make_triangle(polygon=4, v=(0, 1, 2, 3), n=(0, 1, 2, 3), t=(0, 1, 2, 3))]

bmd_quad = BMD(
    Version=0x0A, Name="MU_Test_Quad",
    Meshes=[make_mesh(
        vertices=quad_verts, normals=quad_norms, texcoords=quad_uvs, triangles=quad_tris,
        texture=0, texture_path="quad_tex.jpg",
    )],
)
objs = MeshBuilder.build_all_meshes(bmd_quad, name="MU_Test_Quad")
print(f"Created {len(objs)} object(s)")


# ======================================================================
# Summary
# ======================================================================

print("=" * 60)
print("All manual tests completed!")
print(f"Objects in scene: {len(bpy.data.objects)}")
for obj in bpy.data.objects:
    mesh = obj.data
    print(f"  {obj.name}: {len(mesh.vertices)} verts, {len(mesh.polygons)} polys, "
          f"{len(mesh.uv_layers)} UV, "
          f"material_slots={len(obj.material_slots)}")
print("=" * 60)
