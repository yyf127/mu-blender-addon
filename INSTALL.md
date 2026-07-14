# Installation Guide

## Requirements

- **Blender 4.0** or newer
- **Python 3.11+** (bundled with Blender)
- No external Python packages required

## Quick Install (Blender)

1. **Download the addon**
   - Clone this repository: `git clone https://github.com/yyf127/mu-blender-addon.git`
   - Or download the ZIP archive

2. **Install in Blender**
   - Open Blender
   - Go to **Edit → Preferences** (or **Blender → Settings** on macOS)
   - Switch to the **Add-ons** tab
   - Click **Install from Disk** (top-right)
   - Select the `mu-blender-addon` folder or a ZIP containing it
   - Search for "MU Online" in the addon list
   - Enable the checkbox next to **"MU Online Blender Tools"**

3. **Verify installation**
   - Press `N` in the 3D View to open the sidebar
   - You should see a **MU** tab
   - Go to **File → Import** — you should see three MU Online options

## Finding Your MU Online Data

The addon needs access to your MU Online client's `Data/` directory:

```
MU Online Client/
├── Data/
│   ├── World0/          ← Terrain files for Lorencia
│   │   ├── EncTerrain0.att
│   │   ├── EncTerrain0.map
│   │   ├── TerrainHeight.OZB
│   │   └── EncTerrain0.obj
│   ├── World1/          ← Dungeon
│   ├── Object0/         ← 3D models for Lorencia objects
│   │   ├── Object01.bmd
│   │   └── ...
│   ├── Texture/         ← Game textures (.ozj / .ozt)
│   └── ...
```

> **Note:** The addon does **not** include game assets. You must own a legitimate copy of MU Online.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **"No module named 'bpy'"** | This addon must run **inside Blender**, not in a standalone Python interpreter. |
| **Import menu missing** | Make sure the addon is enabled in Preferences → Add-ons. Try restarting Blender. |
| **Terrain files not found** | Verify your Data Folder path. The addon looks for `World{N}/` subdirectories. |
| **BMD models not found** | Check that `Object{N}/` folders exist alongside `World{N}/` folders. |
| **Missing textures** | Set your Data Folder in the MU panel → Advanced → Data Folder. |

## Manual Python Installation

If you need to install the package manually:

```bash
# From the repository root:
pip install -e .
```

Then in Blender's Scripting workspace:
```python
import mu_blender_tools
mu_blender_tools.register()
```

## Development Setup

See [DEVELOPMENT.md](DEVELOPMENT.md) for contributing guidelines.
