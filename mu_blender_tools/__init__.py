# MU Online Blender Tools
# Blender 4.x addon for importing, editing, and exporting MU Online client assets.

bl_info = {
    "name": "MU Online Blender Tools",
    "author": "MU Blender Tools Contributors",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "File > Import > MU Model / MU Terrain / MU World / MU Scene",
    "description": "Import, edit, and export MU Online client assets",
    "category": "Import-Export",
}


def _register_submodules() -> None:
    """Register all sub-modules in dependency-safe order."""
    from . import ui
    from .operators import scene_importer, import_model, import_terrain
    from .ui import panel, menu

    # 1. Operators (contain business logic)
    scene_importer.register()
    import_model.register()
    import_terrain.register()

    # 2. UI (panels, menus)
    panel.register()
    menu.register()


def _unregister_submodules() -> None:
    """Unregister all sub-modules in reverse order."""
    from .ui import menu, panel
    from .operators import import_terrain, import_model, scene_importer

    menu.unregister()
    panel.unregister()
    import_terrain.unregister()
    import_model.unregister()
    scene_importer.unregister()


def register() -> None:
    """Register all MU Online Blender Tools modules."""
    _register_submodules()


def unregister() -> None:
    """Unregister all MU Online Blender Tools modules."""
    _unregister_submodules()
