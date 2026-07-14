# MU Online Blender Tools

A Blender 4.x addon for importing, editing, and exporting MU Online client assets (.bmd models, terrain, textures, animations).

## Features

- **Model Import** — Import `.bmd` model files with meshes, materials, armatures, and animations
- **Terrain Import** — Import terrain data from `.att`, `.map`, `.ozb` files with heightmaps, texture layers, and blending
- **World Import** — Import a complete game world: terrain + object placements + NPCs + monsters
- **Texture Loading** — Decode `.ozj`, `.ozt`, `.tga`, `.dds` game textures
- **Organised Collections** — Auto-sorted by category (Terrain, Objects, NPC, Monster, Lights, Water, Effects)
- **Export Framework** — Extensible architecture for exporting back to game formats (stubs ready)

## Quick Start

### Install

1. Download or clone this repository.
2. In Blender, go to **Edit → Preferences → Add-ons → Install from Disk**.
3. Select the repository root folder (contains `mu_blender_tools/`).
4. Enable **"MU Online Blender Tools"** in the addon list.
5. Find import options under **File → Import** or in the **3D View sidebar → MU** tab.

### Import a World

1. Open the **3D View**, press `N` to show the sidebar, and switch to the **MU** tab.
2. Set your **Data Folder** to your MU Online client's `Data/` directory.
3. Click **MU World** and select the world number.
4. The addon will read all terrain files, build the mesh, and place object markers.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Blender UI (panel.py / menu.py)       │
│                    No business logic                     │
├──────────────────────────┬──────────────────────────────┤
│     Operators            │      Export Framework         │
│  (import_model.py,       │   (export/base_exporter.py,   │
│   import_terrain.py,     │    base_serializer.py,        │
│   scene_importer.py)     │    base_writer.py, ...)       │
├──────────┬───────────────┴──────────┬───────────────────┤
│ Readers  │        Builders          │  Loaders           │
│ (binary  │  (mesh, material,        │  (texture_         │
│  _reader,│   armature, animation,   │   loader.py)       │
│  bmd_    │   terrain, world)        │                    │
│  _reader)│                          │                    │
└──────────┴──────────────────────────┴────────────────────┘
     Pure data layer            Blender data layer
     (no bpy)                   (bpy API)
```

## Project Status

All 14 development phases are complete:

| Phase | Module | Tests |
|-------|--------|-------|
| 1 | BinaryReader | 37 ✅ |
| 2 | BMDReader + BMD Types | 23 ✅ |
| 3 | Texture Loader | 25 ✅ |
| 4 | Mesh Builder | 24 ✅ |
| 5 | Material Builder | 30 ✅ |
| 6 | Armature Builder | 21 ✅ |
| 7 | Animation Builder | 23 ✅ |
| 8 | Terrain Reader | 15 ✅ |
| 9 | Terrain Builder | 25 ✅ |
| 10 | World Reader | 25 ✅ |
| 11 | World Builder | 24 ✅ |
| 12 | Scene Importer | 16 ✅ |
| 13 | UI Panel & Menu | 9 ✅ |
| 14 | Export Framework | 18 ✅ |

> **Note:** Tests requiring `bpy` mocking (builders, operators, UI) must be
> run individually or in compatible groups.  Pure data-layer tests
> (readers, terrain_builder, export framework) run together via ``discover``.
>
> **Core data-layer tests: 143 ✅**
> **All bpy-dependent tests: 163 ✅**

## License

See [LICENSE](LICENSE) (if not included, MIT by default).