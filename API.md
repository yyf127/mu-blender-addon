# API Reference

## Package: `mu_blender_tools`

### `register()` / `unregister()`

Entry points for Blender addon lifecycle.  Register/unregister all operators, panels, and menus.

---

## Sub-package: `mu_blender_tools.readers`

### `BinaryReader`

```python
class BinaryReader(data: bytes)
```

Sequential binary reader wrapping a byte buffer (little-endian by default).

**Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `ReadByte()` | `int` | Read 1 byte |
| `ReadUInt16()` | `int` | Read 2-byte unsigned LE |
| `ReadUInt32()` | `int` | Read 4-byte unsigned LE |
| `ReadInt16()` | `int` | Read 2-byte signed LE |
| `ReadInt32()` | `int` | Read 4-byte signed LE |
| `ReadFloat()` | `float` | Read 4-byte IEEE 754 LE |
| `ReadDouble()` | `float` | Read 8-byte IEEE 754 LE |
| `ReadBool()` | `bool` | Read 1-byte boolean |
| `ReadString(length)` | `str` | Read *length* ASCII chars |
| `ReadCString()` | `str` | Read null-terminated ASCII string |
| `ReadBytes(count)` | `bytes` | Read *count* raw bytes |
| `PeekBytes(count)` | `bytes` | Read *count* bytes without advancing |
| `Tell()` | `int` | Current read position |
| `Seek(offset, origin)` | `None` | Seek to position |
| `Skip(count)` | `None` | Advance position by *count* |
| `Remaining` | `int` | Bytes left in buffer |
| `Size` | `int` | Total buffer size |
| `EOF` | `bool` | True if at end of buffer |
| `ReadVector3()` | `tuple[float,float,float]` | Read 3 consecutive `ReadFloat` values |

### `BMDReader`

```python
class BMDReader:
    def Read(self, data: bytes | bytearray) -> BMD
```

Parses a BMD v12/v15 model file. Returns a `BMD` dataclass.

### Terrain Readers

```python
def read_att(data: bytes) -> TerrainAttributeData
def read_map(data: bytes) -> TerrainMappingData
def read_ozb(data: bytes) -> OZBData
def read_obj(data: bytes) -> OBJData
```

Parse MU Online terrain format files. See `terrain_reader.py` for dataclass details.

### `read_world`

```python
def read_world(
    obj_data: OBJData,
    att_data: Optional[TerrainAttributeData] = None,
    map_data: Optional[TerrainMappingData] = None,
    height_data: Optional[OZBData] = None,
    light_data: Optional[OZBData] = None,
) -> WorldData
```

Classify OBJ objects into semantic categories (Object, Light, Water, NPC, Monster, etc.).

---

## Sub-package: `mu_blender_tools.builders`

### `MeshBuilder`

```python
class MeshBuilder:
    @staticmethod
    def build_all_meshes(bmd: BMD, name: str = "MUModel",
                         collection: Optional[Collection] = None) -> list[Object]
    @staticmethod
    def create_mesh(bmd_mesh: BMDTextureMesh, mesh_index: int = 0,
                    name: str = "MUModel",
                    collection: Optional[Collection] = None) -> Optional[Object]
```

Converts BMD mesh data into Blender Mesh objects. Uses `foreach_set` for performance.

### `MaterialBuilder`

```python
class MaterialBuilder:
    def get_or_create_material(self, texture_path: str) -> Optional[Material]
    def clear_cache(self) -> None
```

Creates Blender Materials with Principled BSDF + Image Texture. Caches by lowercase texture path.

### `ArmatureBuilder`

```python
class ArmatureBuilder:
    @staticmethod
    def build_armature(bmd: BMD, name: str = "MUArmature",
                       collection: Optional[Collection] = None) -> Optional[Object]
```

Creates a Blender Armature from BMD bone data.

### `AnimationBuilder`

```python
class AnimationBuilder:
    @staticmethod
    def build_actions(bmd: BMD, armature_object: Object) -> list[Action]
```

Creates Blender Actions from BMD action data (location + rotation_quaternion FCurves).

### `TerrainBuilder`

```python
class TerrainBuilder(att_data, map_data, height_data, light_data=None,
                     chunk_size=8, texture_path_resolver=None)
    def build(self) -> TerrainBuilderOutput

def build_terrain_mesh(...) -> TerrainBuilderOutput
```

Generates terrain mesh primitives (vertices, normals, UVs, triangles, material indices). No bpy.

### `WorldBuilder`

```python
class WorldBuilder(world_data, terrain_output=None, bmd_loader=None)
    def build(self) -> dict[str, Collection]
```

Creates a complete Blender scene with organised collections, empties, and optional BMD model loading.

---

## Sub-package: `mu_blender_tools.operators`

### `MU_OT_import_model`

- **bl_idname:** `mu.import_model`
- **File:** `.bmd`
- **Options:** Scale, Import Textures, Import Materials, Import Armature, Import Animations

### `MU_OT_import_terrain`

- **bl_idname:** `mu.import_terrain`
- **File:** `.att`, `.map`, `.ozb`
- **Options:** Scale, Chunk Terrain

### `MU_OT_import_world`

- **bl_idname:** `mu.import_world`
- **Requires:** Data directory with `World{N}/` + `Object{N}/` subfolders
- **Options:** World Number, Import Terrain, Import Objects, Chunk Terrain

---

## Sub-package: `mu_blender_tools.export`

### Base Classes

| Class | Purpose |
|-------|---------|
| `BaseSerializer[T]` | Convert data → bytes (`serialize(data) → bytes`) |
| `BaseWriter` | Write bytes → file (`write(data, path)`) |
| `BaseExporter` | Orchestrate validate → serialize → write |

### Stubs

| Exporter | Format | Status |
|----------|--------|--------|
| `BMDExporter` / `BMDSerializer` | `.bmd` | 🔜 Not yet implemented |
| `TerrainExporter` / `*Serializer` | `.att`, `.map`, `.ozb`, `.obj` | 🔜 Not yet implemented |
| `WorldExporter` | Multi-file world | 🔜 Not yet implemented |
| `SceneExporter` | All formats | 🔜 Not yet implemented |

---

## Sub-package: `mu_blender_tools.ui`

### `MUImportSettings`

PropertyGroup stored in `context.scene.mu_import`:

| Property | Type | Default |
|----------|------|---------|
| `scale` | `FloatProperty` | 1.0 |
| `up_axis` | `EnumProperty` | `"Z"` |
| `import_texture` | `BoolProperty` | True |
| `import_material` | `BoolProperty` | True |
| `import_armature` | `BoolProperty` | True |
| `import_animation` | `BoolProperty` | True |
| `debug` | `BoolProperty` | False |
| `data_folder` | `StringProperty` | `""` |
| `chunk_terrain` | `BoolProperty` | True |

### `MU_PT_import_panel`

Panel class registered in the 3D View sidebar under the "MU" category.

---

## Internal Utilities

### `mu_blender_tools._logging`

```python
def get_logger(name: Optional[str] = None) -> logging.Logger
```

### `mu_blender_tools._exceptions`

```python
MuBlenderError
├── ReaderError
│   ├── BinaryReaderError
│   ├── BMDParseError
│   ├── TerrainParseError
│   └── WorldParseError
├── TextureError
├── BuilderError
│   ├── MeshBuildError
│   ├── MaterialBuildError
│   ├── ArmatureBuildError
│   ├── AnimationBuildError
│   └── TerrainBuildError
├── ExportError
│   ├── SerializeError
│   └── WriteError
├── ImportError
└── ConfigurationError
```
