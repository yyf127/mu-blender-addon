# MU Online Blender Tools - Operators package
#
# Operators are imported lazily so that this package can be loaded
# outside Blender (e.g. for documentation generation).


def __getattr__(name):
    _lazy = {
        "MU_OT_import_world": ".scene_importer",
        "MU_OT_import_model": ".import_model",
        "MU_OT_import_terrain": ".import_terrain",
    }
    if name in _lazy:
        import importlib
        mod = importlib.import_module(_lazy[name], __package__)
        cls = getattr(mod, name)
        globals()[name] = cls
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MU_OT_import_world",
    "MU_OT_import_model",
    "MU_OT_import_terrain",
]
