# MU Online Blender Tools - UI package
#
# This package contains ONLY user-interface code (panels, menus).
# No business logic lives here — all processing is delegated to
# the ``operators`` and ``builders`` modules.

def __getattr__(name):
    _lazy = {
        "MUImportSettings": ".panel",
        "MU_PT_import_panel": ".panel",
        "register_menus": ".menu",
        "unregister_menus": ".menu",
    }
    if name in _lazy:
        import importlib
        mod = importlib.import_module(_lazy[name], __package__)
        attr = getattr(mod, name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MUImportSettings",
    "MU_PT_import_panel",
    "register_menus",
    "unregister_menus",
]
