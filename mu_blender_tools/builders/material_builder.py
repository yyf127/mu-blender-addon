# MU Online Blender Tools - MaterialBuilder
#
# Converts decoded texture data (from TextureLoader) into Blender Materials.
#
# Design:
#   - Pure Blender Data API — no bpy.ops calls
#   - Each material uses Principled BSDF with an Image Texture node
#   - Materials are cached by texture path to avoid duplicates
#   - Blend mode detection: from BMD BlendingMode field, texture path suffix,
#     or alpha channel analysis
#   - MaterialBuilder does NOT read files or create meshes
#
# Blend mode reference (TS TextureBlendHeuristics):
#   ADDITIVE: glow, flare, spark, fire, smoke, trail, aura, halo,
#             effect, fx, energy, beam, light, shine, flash, particle
#   ALPHA/NORMAL: alpha, mask, decal, leaf, foliage, hair, cape, cloth,
#                 shadow, smoke, wing
#   OPAQUE: skin, body, armor, armour, face, helm, helmet, pants,
#           gloves, boots, shield, sword, weapon

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import bpy
from bpy.types import Image, Material, Object

from ..loaders.texture_loader import TextureData

_logger = logging.getLogger("mu_blender_tools")


# ======================================================================
# Blend mode helpers
# ======================================================================

_ADDITIVE_HINTS: tuple[str, ...] = (
    "glow", "flare", "spark", "fire", "smoke", "trail",
    "aura", "halo", "effect", "fx", "energy", "beam",
    "light", "shine", "flash", "particle",
)

_OPAQUE_HINTS: tuple[str, ...] = (
    "skin", "body", "armor", "armour", "face", "helm",
    "helmet", "pants", "gloves", "boots", "shield",
    "sword", "weapon",
)


def _detect_blend_mode(
    texture_path: str,
    blending_mode: Optional[str] = None,
) -> str:
    """Determine the appropriate Blender blend mode.

    Priority:
      1. Explicit ``BlendingMode`` from BMD mesh (e.g. "additive", "alpha").
      2. MU texture filename suffix convention (``_a`` = alpha, ``_r`` = bright).
      3. Heuristic keyword matching against texture path.

    Returns:
        One of ``"OPAQUE"``, ``"BLEND"``, ``"ADD"`` (matching Blender's
        ``Material.blend_method`` enum).
    """
    # 1. Explicit blending mode from BMD data
    if blending_mode:
        mode_lower = blending_mode.lower().strip()
        if mode_lower in ("add", "additive", "ADD"):
            return "ADD"
        elif mode_lower in ("blend", "alpha", "alpha_blend", "BLEND"):
            return "BLEND"
        elif mode_lower in ("opaque", "OPAQUE"):
            return "OPAQUE"

    # 2. MU filename suffix convention
    stem = os.path.splitext(os.path.basename(texture_path))[0].lower()
    tokens = stem.split("_")
    if len(tokens) > 1:
        last = tokens[-1]
        if last == "a":
            return "BLEND"
        elif last == "r":
            # Bright/emissive — keep opaque but will add emission
            return "OPAQUE"
        elif last == "n":
            return "OPAQUE"

    # 3. Heuristic keyword match
    for hint in _ADDITIVE_HINTS:
        if hint in stem:
            return "ADD"
    for hint in _OPAQUE_HINTS:
        if hint in stem:
            return "OPAQUE"

    # Default: opaque
    return "OPAQUE"


# ======================================================================
# Emission detection
# ======================================================================

def _has_emission_hint(texture_path: str) -> bool:
    """Check if the texture path suggests an emissive/self-illuminated surface.

    MU convention: ``_r`` suffix means "bright" (emissive).
    """
    stem = os.path.splitext(os.path.basename(texture_path))[0].lower()
    tokens = stem.split("_")
    if len(tokens) > 1 and tokens[-1] == "r":
        return True
    # Hard-coded known emissive texture paths from C# reference
    if "mu_rgb_lights" in stem:
        return True
    return False


# ======================================================================
# MaterialBuilder
# ======================================================================


class MaterialBuilder:
    """Creates and caches Blender Materials from MU Online textures.

    Usage::

        from mu_blender_tools.loaders.texture_loader import TextureLoader
        from mu_blender_tools.builders.material_builder import MaterialBuilder

        tex_loader = TextureLoader(data_path="/path/to/Data")
        mat_builder = MaterialBuilder(tex_loader)

        mat = mat_builder.get_or_create_material(
            "Player/human_face.jpg",
            blending_mode=None,
        )
        # Assign to object
        mat_builder.assign_to_object(obj, mat, slot_index=0)
    """

    def __init__(
        self,
        texture_loader: Any = None,
    ) -> None:
        """Initialize the material builder.

        Args:
            texture_loader: An optional ``TextureLoader`` instance used to
                            load texture data on demand. If not provided,
                            materials will be created without textures
                            (useful for testing). Type is ``TextureLoader``
                            but kept as ``Any`` to avoid circular import.
        """
        self._texture_loader: Any = texture_loader
        # Cache: texture_path → bpy.types.Material
        self._cache: dict[str, Material] = {}
        # Cache: texture_path → bpy.types.Image
        self._image_cache: dict[str, Image] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_or_create_material(
        self,
        texture_path: str,
        blending_mode: Optional[str] = None,
        texture_data: Optional[TextureData] = None,
    ) -> Material:
        """Return a cached material for *texture_path*, or create one.

        Args:
            texture_path: Relative or absolute path to the texture file.
                          Used as the cache key and material name basis.
            blending_mode: Explicit blend mode hint from BMD data.
            texture_data: Pre-decoded texture data. If ``None``, the builder
                          will attempt to load via ``texture_loader``.

        Returns:
            A Blender Material with Principled BSDF and Image Texture.
        """
        # Check cache
        cache_key = texture_path.lower().replace("\\", "/")
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Create new material
        mat = self._build_material(
            texture_path, blending_mode, texture_data,
        )
        self._cache[cache_key] = mat
        return mat

    def assign_to_object(
        self,
        obj: Object,
        material: Material,
        slot_index: int = 0,
    ) -> bool:
        """Assign a material to the specified slot on an object.

        Ensures the slot exists before assigning.

        Args:
            obj: Target Blender object.
            material: Material to assign.
            slot_index: Slot index (0-based).

        Returns:
            True if the assignment succeeded.
        """
        # Ensure enough slots
        while len(obj.material_slots) <= slot_index:
            obj.data.materials.append(None)

        obj.material_slots[slot_index].material = material
        _logger.debug(
            "Assigned material '%s' to slot %d on '%s'",
            material.name, slot_index, obj.name,
        )
        return True

    def clear_cache(self) -> None:
        """Clear the material and image caches."""
        self._cache.clear()
        self._image_cache.clear()

    @property
    def cache_size(self) -> int:
        """Number of cached materials."""
        return len(self._cache)

    # ------------------------------------------------------------------
    # Internal: material creation
    # ------------------------------------------------------------------

    def _build_material(
        self,
        texture_path: str,
        blending_mode: Optional[str] = None,
        texture_data: Optional[TextureData] = None,
    ) -> Material:
        """Create a new Blender Material with Principled BSDF.

        Steps:
          1. Create material with appropriate name and blend mode.
          2. Create Principled BSDF shader node group.
          3. If texture data is available, create Image Texture node.
          4. Connect Base Color (and optionally Alpha, Emission).
        """
        # Derive material name from texture file name
        mat_name = self._material_name(texture_path)

        # Create material
        mat: Material = bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Clear default nodes
        for node in list(nodes):
            nodes.remove(node)

        # -------- Create node tree --------

        # Output → Material Output
        output = nodes.new(type="ShaderNodeOutputMaterial")
        output.location = (300, 0)

        # Principled BSDF
        principled = nodes.new(type="ShaderNodeBsdfPrincipled")
        principled.location = (0, 0)
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        has_texture = texture_data is not None

        if has_texture:
            # Image Texture node
            img = self._get_or_create_image(texture_path, texture_data)
            tex_node = nodes.new(type="ShaderNodeTexImage")
            tex_node.image = img
            tex_node.location = (-300, 0)

            # Base Color ← Image Texture (Color)
            links.new(tex_node.outputs["Color"], principled.inputs["Base Color"])

            # Alpha handling
            has_alpha = self._has_alpha_channel(texture_data)
            if has_alpha:
                # Alpha ← Image Texture (Alpha)
                links.new(
                    tex_node.outputs["Alpha"],
                    principled.inputs["Alpha"],
                )

        # Blend mode
        blend = _detect_blend_mode(texture_path, blending_mode)
        if blend == "BLEND":
            mat.blend_method = "BLEND"
            mat.shadow_method = "HASHED"
        elif blend == "ADD":
            mat.blend_method = "ADD"
            mat.shadow_method = "NONE"
        else:
            mat.blend_method = "OPAQUE"
            mat.shadow_method = "OPAQUE"

        # Emission
        if _has_emission_hint(texture_path) and has_texture:
            # Connect texture color to Emission as well
            links.new(
                tex_node.outputs["Color"],
                principled.inputs["Emission Color"],
            )
            principled.inputs["Emission Strength"].default_value = 0.5

        # Store metadata
        mat.user_data["texture_path"] = texture_path
        mat.user_data["blending_mode"] = blend

        _logger.info(
            "Created material '%s' (blend=%s, alpha=%s, emission=%s)",
            mat_name, blend,
            texture_data is not None and self._has_alpha_channel(texture_data),
            _has_emission_hint(texture_path),
        )

        return mat

    # ------------------------------------------------------------------
    # Image creation / caching
    # ------------------------------------------------------------------

    def _get_or_create_image(
        self,
        texture_path: str,
        texture_data: TextureData,
    ) -> Image:
        """Return a cached Blender Image for this texture, or create one.

        Args:
            texture_path: Original texture file path (used as cache key).
            texture_data: Decoded RGBA pixel data.

        Returns:
            A Blender Image with the pixel data loaded.
        """
        cache_key = texture_path.lower().replace("\\", "/")
        cached = self._image_cache.get(cache_key)
        if cached is not None:
            return cached

        # Create Blender image
        img_name = os.path.basename(texture_path)
        img: Image = bpy.data.images.new(
            name=img_name,
            width=texture_data.width,
            height=texture_data.height,
            alpha=True,
        )

        # Assign pixel data (RGBA, float)
        pixels = self._rgba_bytes_to_floats(texture_data.data)
        img.pixels[:] = pixels

        # Store file path for reference
        img.filepath = texture_path
        img.source = "FILE"

        self._image_cache[cache_key] = img
        _logger.debug("Created image '%s' (%dx%d)", img_name, texture_data.width, texture_data.height)

        return img

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _material_name(texture_path: str) -> str:
        """Derive a human-readable material name from the texture path.

        Examples::

            "Player/human_face.jpg" → "MU_human_face"
            "World1/TileGrass01.ozj" → "MU_TileGrass01"
        """
        stem = os.path.splitext(os.path.basename(texture_path))[0]
        # Sanitise for Blender name
        name = "MU_" + stem.replace(" ", "_")
        return name

    @staticmethod
    def _has_alpha_channel(texture_data: Optional[TextureData]) -> bool:
        """Check if the texture has a non-trivial alpha channel.

        A texture is considered to have meaningful alpha if:
          - It has 4 channels, AND
          - Not all alpha values are 255 (fully opaque).

        Args:
            texture_data: Decoded texture data.

        Returns:
            True if the texture has meaningful alpha.
        """
        if texture_data is None:
            return False
        if texture_data.channels < 4:
            return False

        data = texture_data.data
        # Sample every 4th byte starting at offset 3 (alpha channel)
        # Quick check: look at first 1024 pixels for any alpha < 255
        pixel_count = min(len(data) // 4, 1024)
        for i in range(pixel_count):
            if data[i * 4 + 3] < 255:
                return True
        return False

    @staticmethod
    def _rgba_bytes_to_floats(rgba_bytes: bytes) -> list[float]:
        """Convert RGBA byte array to Blender pixel float array.

        Blender stores pixels as ``[R, G, B, A, R, G, B, A, ...]``
        with each channel as a float in 0..1 range.
        """
        n = len(rgba_bytes) // 4
        floats = [0.0] * (n * 4)
        for i in range(n):
            base = i * 4
            floats[base] = rgba_bytes[base] / 255.0       # R
            floats[base + 1] = rgba_bytes[base + 1] / 255.0  # G
            floats[base + 2] = rgba_bytes[base + 2] / 255.0  # B
            floats[base + 3] = rgba_bytes[base + 3] / 255.0  # A
        return floats



