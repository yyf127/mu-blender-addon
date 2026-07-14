# MU Online Blender Tools - MeshBuilder
#
# Converts BMD mesh data (from BMDReader) into Blender Mesh objects.
#
# Design:
#   - Pure Blender Data API — no bpy.ops calls
#   - Batch writes via foreach_set for performance
#   - One Blender Mesh per BMDTextureMesh
#   - MeshBuilder does NOT read files, create materials, or build armatures
#
# BMD → Blender mapping:
#   BMDTextureVertex.Position → Mesh vertex coordinates
#   BMDTriangle.Polygon       → Polygon vertex count (3=tri, 4=quad)
#   BMDTriangle.VertexIndex[] → Loop vertex indices
#   BMDTriangle.NormalIndex[] → Split normal per loop (via BMDTextureNormal)
#   BMDTriangle.TexCoordIndex[] → UV coordinates (via BMDTexCoord)
#   BMDTextureMesh.Texture    → Polygon material_index
#   BMDTextureMesh.TexturePath → stored in mesh user_data for MaterialBuilder

from __future__ import annotations

import logging
from typing import Optional

import bpy
from bpy.types import Collection, Mesh, Object

from ..readers.bmd_types import BMD, BMDTextureMesh, BMDTriangle, BMD_DUMMY_BONE

_logger = logging.getLogger("mu_blender_tools")


# ======================================================================
# MeshBuilder
# ======================================================================


class MeshBuilder:
    """Creates Blender Mesh objects from parsed BMD mesh data.

    Usage::

        from mu_blender_tools.readers.bmd_reader import BMDReader
        from mu_blender_tools.builders.mesh_builder import MeshBuilder

        bmd = BMDReader().Read(raw_bytes)
        objects = MeshBuilder.build_all_meshes(bmd, name="MyModel")
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def build_all_meshes(
        bmd: BMD,
        name: str = "MUModel",
        collection: Optional[Collection] = None,
    ) -> list[Object]:
        """Create Blender Mesh objects for every mesh in a BMD model.

        Args:
            bmd: Parsed BMD data (from BMDReader).
            name: Base name for the created objects.
            collection: Target collection (defaults to active collection).

        Returns:
            List of created Blender Object instances (one per mesh).
        """
        objects: list[Object] = []
        target_collection = collection or MeshBuilder._active_collection()

        for mesh_index, bmd_mesh in enumerate(bmd.Meshes):
            try:
                obj = MeshBuilder._create_single_mesh(
                    bmd_mesh, mesh_index, name, target_collection,
                )
                if obj is not None:
                    objects.append(obj)
            except Exception as e:
                _logger.error(
                    "Failed to build mesh %d '%s': %s",
                    mesh_index, bmd_mesh.TexturePath, e,
                )

        _logger.info(
            "MeshBuilder: created %d/%d mesh objects for '%s'",
            len(objects), len(bmd.Meshes), name,
        )
        return objects

    @staticmethod
    def create_mesh(
        bmd_mesh: BMDTextureMesh,
        mesh_index: int = 0,
        name: str = "MUModel",
        collection: Optional[Collection] = None,
    ) -> Optional[Object]:
        """Create a single Blender Mesh object from one BMDTextureMesh.

        This is a convenience wrapper around the internal builder steps.

        Args:
            bmd_mesh: A single BMDTextureMesh to convert.
            mesh_index: Index of this mesh (for naming).
            name: Base name for the object.
            collection: Target collection.

        Returns:
            Created Blender Object, or None on failure.
        """
        target_collection = collection or MeshBuilder._active_collection()
        return MeshBuilder._create_single_mesh(
            bmd_mesh, mesh_index, name, target_collection,
        )

    # ------------------------------------------------------------------
    # Internal: single mesh creation
    # ------------------------------------------------------------------

    @staticmethod
    def _create_single_mesh(
        bmd_mesh: BMDTextureMesh,
        mesh_index: int,
        name: str,
        collection: Collection,
    ) -> Optional[Object]:
        """Internal: build one Blender mesh from one BMDTextureMesh.

        Each step is delegated to a dedicated method for clarity.
        """
        vertex_count = len(bmd_mesh.Vertices)
        tri_count = len(bmd_mesh.Triangles)

        if vertex_count == 0 or tri_count == 0:
            _logger.debug(
                "Skipping mesh %d '%s': no vertices or triangles",
                mesh_index, bmd_mesh.TexturePath,
            )
            return None

        mesh_name = f"{name}_mesh{mesh_index:02d}"
        mesh: Mesh = bpy.data.meshes.new(mesh_name)

        # Store original texture path for MaterialBuilder
        mesh.user_data["texture_path"] = bmd_mesh.TexturePath
        mesh.user_data["blending_mode"] = bmd_mesh.BlendingMode or ""
        mesh.user_data["mesh_index"] = mesh_index

        # ---- Build topology ----
        loop_counts, face_vertex_indices = MeshBuilder._build_face_data(bmd_mesh)
        total_loops = sum(loop_counts)

        mesh.vertices.add(vertex_count)
        mesh.loops.add(total_loops)
        mesh.polygons.add(tri_count)

        # ---- Vertices ----
        MeshBuilder._build_vertices(mesh, bmd_mesh, vertex_count)

        # ---- Faces (loops + polygons) ----
        MeshBuilder._build_faces(
            mesh, bmd_mesh, loop_counts, face_vertex_indices, tri_count,
        )

        # ---- UV ----
        uv_count = len(bmd_mesh.TexCoords)
        if uv_count > 0:
            MeshBuilder._build_uv(
                mesh, bmd_mesh, loop_counts, face_vertex_indices,
            )

        # ---- Normals (split per-loop) ----
        normal_count = len(bmd_mesh.Normals)
        if normal_count > 0:
            MeshBuilder._build_normals(
                mesh, bmd_mesh, loop_counts, face_vertex_indices,
            )

        # ---- Material indices ----
        MeshBuilder._build_material_indices(mesh, bmd_mesh, tri_count)

        # ---- Finalise mesh ----
        mesh.update()
        mesh.validate()

        _logger.info(
            "Created mesh '%s': %d vertices, %d triangles, %d materials",
            mesh_name, vertex_count, tri_count, len(set(
                t for t in [bmd_mesh.Texture] if t >= 0
            )),
        )

        # ---- Create object and link ----
        obj = bpy.data.objects.new(mesh_name, mesh)
        collection.objects.link(obj)

        # Create empty material slots (one per unique material index)
        MeshBuilder._build_material_slots(obj, bmd_mesh)

        return obj

    # ------------------------------------------------------------------
    # Build face data (loop counts + vertex indices per polygon)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_face_data(
        bmd_mesh: BMDTextureMesh,
    ) -> tuple[list[int], list[list[int]]]:
        """Extract polygon loop counts and vertex index lists from triangles.

        BMD Triangle.Polygon: 3 = triangle, 4 = quad.
        Falls back to triangle for unknown values.

        Returns:
            Tuple of (loop_counts, face_vertex_indices).
        """
        loop_counts: list[int] = []
        face_vertex_indices: list[list[int]] = []

        vertex_limit = len(bmd_mesh.Vertices)

        for tri in bmd_mesh.Triangles:
            if tri.Polygon == 4:
                count = 4
            else:
                count = 3  # default: triangle (Polygon=0 or 3)

            indices: list[int] = []
            for i in range(count):
                idx = tri.VertexIndex[i]
                if idx < 0 or idx >= vertex_limit:
                    _logger.warning(
                        "Vertex index %d out of range (0..%d), clamping to 0",
                        idx, vertex_limit - 1,
                    )
                    idx = 0
                indices.append(idx)

            loop_counts.append(count)
            face_vertex_indices.append(indices)

        return loop_counts, face_vertex_indices

    # ------------------------------------------------------------------
    # Vertices
    # ------------------------------------------------------------------

    @staticmethod
    def _build_vertices(
        mesh: Mesh, bmd_mesh: BMDTextureMesh, vertex_count: int,
    ) -> None:
        """Write vertex positions using foreach_set (batch)."""
        coords = [0.0] * (vertex_count * 3)
        for i, v in enumerate(bmd_mesh.Vertices):
            base = i * 3
            coords[base] = v.Position[0]
            coords[base + 1] = v.Position[1]
            coords[base + 2] = v.Position[2]
        mesh.vertices.foreach_set("co", coords)
        _logger.debug("Wrote %d vertex positions", vertex_count)

    # ------------------------------------------------------------------
    # Faces (loops + polygons)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_faces(
        mesh: Mesh,
        bmd_mesh: BMDTextureMesh,
        loop_counts: list[int],
        face_vertex_indices: list[list[int]],
        tri_count: int,
    ) -> None:
        """Write polygon and loop data using foreach_set (batch)."""
        # Build flat loop vertex index array
        loop_vertex_indices: list[int] = []
        for indices in face_vertex_indices:
            loop_vertex_indices.extend(indices)

        # Build loop_start and loop_total arrays
        loop_start = [0] * tri_count
        loop_total = [0] * tri_count
        current = 0
        for i, count in enumerate(loop_counts):
            loop_start[i] = current
            loop_total[i] = count
            current += count

        mesh.loops.foreach_set("vertex_index", loop_vertex_indices)
        mesh.polygons.foreach_set("loop_start", loop_start)
        mesh.polygons.foreach_set("loop_total", loop_total)

        # Default smooth shading
        mesh.polygons.foreach_set("use_smooth", [True] * tri_count)

        _logger.debug(
            "Wrote %d polygons, %d loops", tri_count, len(loop_vertex_indices),
        )

    # ------------------------------------------------------------------
    # UV coordinates
    # ------------------------------------------------------------------

    @staticmethod
    def _build_uv(
        mesh: Mesh,
        bmd_mesh: BMDTextureMesh,
        loop_counts: list[int],
        face_vertex_indices: list[list[int]],
    ) -> None:
        """Create a UV layer and write UV coordinates.

        Maps BMDTriangle.TexCoordIndex → BMDTexCoord.U/V per loop.
        Missing or invalid UV references use (0, 0).
        """
        uv_layer = mesh.uv_layers.new(name="UVMap")
        if uv_layer is None:
            _logger.warning("Failed to create UV layer")
            return

        texcoords = bmd_mesh.TexCoords
        total_loops = sum(loop_counts)
        uv_data = [0.0] * (total_loops * 2)
        uv_idx = 0

        for tri_idx, indices in enumerate(face_vertex_indices):
            tri = bmd_mesh.Triangles[tri_idx]
            for corner in range(len(indices)):
                tc_idx = tri.TexCoordIndex[corner]
                base = uv_idx * 2
                if 0 <= tc_idx < len(texcoords):
                    tc = texcoords[tc_idx]
                    uv_data[base] = tc.U
                    uv_data[base + 1] = tc.V
                else:
                    uv_data[base] = 0.0
                    uv_data[base + 1] = 0.0
                uv_idx += 1

        uv_layer.data.foreach_set("uv", uv_data)
        _logger.debug("Wrote %d UV coordinates", total_loops)

    # ------------------------------------------------------------------
    # Split normals (per-loop)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_normals(
        mesh: Mesh,
        bmd_mesh: BMDTextureMesh,
        loop_counts: list[int],
        face_vertex_indices: list[list[int]],
    ) -> None:
        """Write custom split normals per loop corner.

        Maps BMDTriangle.NormalIndex → BMDTextureNormal.Normal.
        Missing or invalid normal references use (0, 0, 1) as fallback.

        Enables ``use_auto_smooth`` to allow custom normals in Blender.
        """
        normals = bmd_mesh.Normals
        total_loops = sum(loop_counts)
        loop_normals = [0.0] * (total_loops * 3)
        n_idx = 0

        for tri_idx, indices in enumerate(face_vertex_indices):
            tri = bmd_mesh.Triangles[tri_idx]
            for corner in range(len(indices)):
                nrm_idx = tri.NormalIndex[corner]
                base = n_idx * 3
                if 0 <= nrm_idx < len(normals):
                    n = normals[nrm_idx].Normal
                    loop_normals[base] = n[0]
                    loop_normals[base + 1] = n[1]
                    loop_normals[base + 2] = n[2]
                else:
                    loop_normals[base] = 0.0
                    loop_normals[base + 1] = 0.0
                    loop_normals[base + 2] = 1.0
                n_idx += 1

        # Custom normals require auto-smooth to be enabled
        mesh.use_auto_smooth = True
        mesh.normals_split_custom_set(
            list(zip(*[iter(loop_normals)] * 3))
        )
        _logger.debug("Wrote %d loop normals", total_loops)

    # ------------------------------------------------------------------
    # Material indices (per polygon)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_material_indices(
        mesh: Mesh,
        bmd_mesh: BMDTextureMesh,
        tri_count: int,
    ) -> None:
        """Write material_index per polygon.

        The material index is derived from ``bmd_mesh.Texture`` (a short).
        If negative, defaults to 0.
        """
        mat_idx = max(0, int(bmd_mesh.Texture))
        material_indices = [mat_idx] * tri_count
        mesh.polygons.foreach_set("material_index", material_indices)
        _logger.debug(
            "Set material_index=%d for %d polygons", mat_idx, tri_count,
        )

    # ------------------------------------------------------------------
    # Material slots (empty, for MaterialBuilder to fill)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_material_slots(obj: Object, bmd_mesh: BMDTextureMesh) -> None:
        """Create empty material slots on the object.

        Slot count = number of unique material indices in the mesh.
        Materials are NOT created here — MaterialBuilder fills them later.
        """
        mat_idx = max(0, int(bmd_mesh.Texture))

        # Ensure enough slots exist
        while len(obj.material_slots) <= mat_idx:
            obj.data.materials.append(None)

        _logger.debug(
            "Created %d material slots for object '%s'",
            len(obj.material_slots), obj.name,
        )

    # ------------------------------------------------------------------
    # Collection helper
    # ------------------------------------------------------------------

    @staticmethod
    def _active_collection() -> Collection:
        """Return the active collection (view layer's active or master)."""
        view_layer = bpy.context.view_layer
        if view_layer and view_layer.active_collection:
            return view_layer.active_collection
        # Fallback: master scene collection
        return bpy.context.scene.collection
