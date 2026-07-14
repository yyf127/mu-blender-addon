# Installation Guide

## Requirements

- **Blender 4.0** or newer (tested up to 5.1)
- **Python 3.11+** (bundled with Blender)
- No external Python packages required

## Quick Install (Blender) — Recommended

### Method A: Build the ZIP (easiest)

Run the build script from the repository root:

```bash
python build_addon.py
```

This creates `mu_blender_tools.zip` in the current directory. Then:

1. Open Blender → **Edit → Preferences** → **Add-ons** tab
2. Click **Install from Disk** (top-right)
3. Select the `mu_blender_tools.zip` file
4. Search for "MU Online" and enable the checkbox

### Method B: Manual folder install

1. Copy the `mu_blender_tools/` folder (the one containing `__init__.py`)
2. Paste it into Blender's addons directory:
   - **Windows**: `%APPDATA%\Blender Foundation\Blender\5.1\scripts\addons\`
   - **macOS**: `~/Library/Application Support/Blender/5.1/scripts/addons/`
   - **Linux**: `~/.config/blender/5.1/scripts/addons/`
3. Restart Blender
4. Enable the addon in **Preferences → Add-ons**

### ⚠️ Important: ZIP structure

If you download the repository ZIP from GitHub, **do NOT** install it directly.
The GitHub ZIP wraps everything in a `mu-blender-addon/` folder which Blender
cannot read.  Always use the build script (Method A) or copy only the
`mu_blender_tools/` folder (Method B).

Correct structure inside the ZIP that Blender expects:
```
mu_blender_tools.zip
├── mu_blender_tools/
│   ├── __init__.py       ← Required by Blender
│   ├── readers/
│   ├── builders/
│   ├── ...
```

## Verify installation

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
