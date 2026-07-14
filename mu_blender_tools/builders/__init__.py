# MU Online Blender Tools - Builders
#
# Blender integration layer: convert parsed data into bpy objects.
# These modules import bpy and create Blender-native data.
#
# NOTE: We import the *terrain_builder* at package level because it is
# pure data (no bpy).  Builders that require bpy are imported lazily
# via ``__getattr__`` so that unit tests outside Blender can still
# import this package without a ``ModuleNotFoundError``.

from .terrain_builder import TerrainBuilder, TerrainBuilderOutput, TerrainChunkMesh, build_terrain_mesh


def __getattr__(name):
    """Lazy-import bpy-dependent builders on demand."""
    _lazy = {
        "MeshBuilder": ".mesh_builder",
        "MaterialBuilder": ".material_builder",
        "ArmatureBuilder": ".armature_builder",
        "AnimationBuilder": ".animation_builder",
        "WorldBuilder": ".world_builder",
    }
    if name in _lazy:
        import importlib
        mod = importlib.import_module(_lazy[name], __package__)
        cls = getattr(mod, name)
        globals()[name] = cls
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MeshBuilder",
    "MaterialBuilder",
    "ArmatureBuilder",
    "AnimationBuilder",
    "TerrainBuilder", "TerrainBuilderOutput", "TerrainChunkMesh",
    "build_terrain_mesh",
    "WorldBuilder",
]
