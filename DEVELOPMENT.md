# Development Guide

## Project Structure

```
mu-blender-addon/
├── mu_blender_tools/
│   ├── __init__.py           # Addon entry point, bl_info, register/unregister
│   ├── _logging.py           # Centralised logging (get_logger)
│   ├── _exceptions.py        # Unified exception hierarchy
│   ├── readers/              # Pure data parsers (no bpy)
│   │   ├── binary_reader.py  # Sequential byte buffer reader
│   │   ├── bmd_reader.py     # BMD model parser
│   │   ├── bmd_types.py      # BMD data dataclasses
│   │   ├── terrain_reader.py # ATT / MAP / OZB / OBJ parsers
│   │   └── world_reader.py   # World data classifier
│   ├── builders/             # Blender data creators (bpy API)
│   │   ├── mesh_builder.py   # Mesh → Blender Mesh
│   │   ├── material_builder.py  # Texture → Material
│   │   ├── armature_builder.py  # Bones → Armature
│   │   ├── animation_builder.py # Actions → Animation
│   │   ├── terrain_builder.py   # Terrain data → Mesh primitives
│   │   └── world_builder.py  # World data → Blender scene
│   ├── loaders/              # External asset loaders
│   │   └── texture_loader.py # OZJ / OZT / TGA / DDS textures
│   ├── operators/            # Blender operators
│   │   ├── import_model.py   # MU_OT_import_model
│   │   ├── import_terrain.py # MU_OT_import_terrain
│   │   └── scene_importer.py # MU_OT_import_world (full pipeline)
│   ├── ui/                   # UI code only (no business logic)
│   │   ├── panel.py          # MUImportSettings + MU_PT_import_panel
│   │   └── menu.py           # File → Import menu entries
│   └── export/               # Export framework (stubs)
│       ├── base_exporter.py
│       ├── base_serializer.py
│       ├── base_writer.py
│       ├── bmd_exporter.py
│       ├── terrain_exporter.py
│       ├── world_exporter.py
│       └── scene_exporter.py
├── tests/                    # Unit tests (mocked bpy)
│   ├── test_binary_reader.py
│   ├── test_bmd_reader.py
│   ├── ...
│   └── test_export_framework.py
├── README.md
├── INSTALL.md
├── DEVELOPMENT.md
└── API.md
```

## Coding Conventions

### Type Hints

All code uses Python 3.11+ type hints:

```python
from typing import Optional

def read_att(data: bytes) -> TerrainAttributeData:
    ...
```

### Imports

- Standard library first, then third-party, then local.
- `from __future__ import annotations` at the top of every file.
- Use relative imports within the package: `from ..readers.binary_reader import BinaryReader`.

```python
from __future__ import annotations

import logging
from typing import Optional

import bpy

from ..readers.binary_reader import BinaryReader
```

### Logging

Use the centralised logger:

```python
from .._logging import get_logger

_logger = get_logger(__name__)
```

### Exceptions

Use the unified hierarchy:

```python
from .._exceptions import BinaryReaderError, ReaderError

raise BinaryReaderError("Unexpected end of data")
```

### Docstrings

- Use Google-style docstrings.
- All public functions, classes, and methods must have docstrings.
- Document args, returns, and raises.

```python
def read_att(data: bytes) -> TerrainAttributeData:
    """Parse an ATT terrain attribute file.

    Args:
        data: Raw ATT file bytes (with encryption).

    Returns:
        Parsed TerrainAttributeData.

    Raises:
        BinaryReaderError: On invalid format.
    """
```

## Running Tests

All tests can be run from the repository root:

```bash
# Run all tests
python -m unittest discover -s tests -p "test_*.py" -v

# Run a single test module
python -m unittest tests.test_binary_reader -v

# Run a single test class
python -m unittest tests.test_binary_reader.TestBinaryReaderReadMethods -v
```

> **Note:** Builders that require `bpy` use mocking (`unittest.mock`). They do not require a running Blender instance.

## Adding a New Reader

1. Create `mu_blender_tools/readers/new_reader.py`.
2. Define a dataclass for the output data.
3. Implement a `read_*` function that takes `bytes` and returns the dataclass.
4. Add tests in `tests/test_new_reader.py`.
5. Export the public API in `mu_blender_tools/readers/__init__.py`.

## Adding a New Builder

1. Create `mu_blender_tools/builders/new_builder.py`.
2. Use `bpy.data` API (no `bpy.ops`).
3. Return Blender objects (Object, Material, etc.).
4. Add tests with mocked `bpy`.
5. Export in `mu_blender_tools/builders/__init__.py`.

## Architecture Rules

- **Readers** are pure Python — no `bpy`, no file I/O. Input is `bytes`, output is a dataclass.
- **Builders** convert reader data into Blender objects. They import `bpy` and use `bpy.data` API.
- **Operators** wire readers → builders together and handle file dialogs.
- **UI** contains only panel/menu code — never import readers or builders directly.

## Pipeline Diagram

```
File bytes → Reader → Dataclass → Builder → Blender object
                ↑                      ↑
         Pure data layer         bpy data layer
         (testable without       (mocked in tests)
          Blender)
```
