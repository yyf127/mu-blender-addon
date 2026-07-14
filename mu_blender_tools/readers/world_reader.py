# MU Online Blender Tools - World Reader
#
# Parses MU Online world data — object placements, lights, water, effects,
# NPCs, and monsters — from parsed TerrainReader data.
#
# Unlike terrain readers (ATT/MAP/OZB/OBJ) this module does NOT read raw
# file bytes.  It takes already-parsed OBJData + metadata and classifies
# each object by its type number into semantic categories.
#
# Reference implementations:
#   src/terrain/TerrainObjects.ts  (TypeScript — object loading/classification)
#   Client.Main.Objects.*          (C# — per-type world object behaviours)
#   Client.Data.ATT.TWFlags        (C# — terrain flags)
#
# Design:
#   - Pure data layer — no file I/O, no bpy
#   - Object classification via type-range heuristics + lookup tables
#   - Coordinate conversion: MU Z-up → Blender Y-up (preserved as data)

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from .terrain_reader import (
    TERRAIN_SIZE,
    TERRAIN_SCALE,
    TerrainAttributeData,
    TerrainMappingData,
    OZBData,
    OBJData,
    MapObject,
)

_logger = logging.getLogger("mu_blender_tools")


# ======================================================================
# World object classification
# ======================================================================


class WorldObjectCategory(IntEnum):
    """Semantic category of a world-placed object."""
    Object = 0      # Regular static world object (trees, stones, buildings, etc.)
    Light = 1       # Dynamic or baked light source
    Water = 2       # Water surface / splashing object
    Effect = 3      # Particle effect / ambient effect (leaves, fire, etc.)
    NPC = 4         # Non-player character (merchant, quest giver, etc.)
    Monster = 5     # Aggressive NPC / monster spawn
    Item = 6        # Dropped item / treasure
    Gate = 7        # Teleport gate / entrance
    PlayerSpawn = 8 # Default player spawn point
    Invalid = 15    # Unknown / invalid


# ======================================================================
# Data types
# ======================================================================


@dataclass
class WorldObject:
    """A single object placed in the world.

    Carries enough data for a future builder to create the corresponding
    Blender object, empty, light, or collection instance.
    """
    type: int = 0
    """OBJ type number (0-255).  Determines the BMD model and behaviour."""

    category: WorldObjectCategory = WorldObjectCategory.Object
    """Semantic category derived from ``type``."""

    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    """World-space position (MU convention: Z-up)."""

    angle_x: float = 0.0
    angle_y: float = 0.0
    angle_z: float = 0.0
    """Euler rotation in degrees (MU convention)."""

    scale: float = 1.0
    """Uniform scale factor."""

    name: str = ""
    """Human-readable name resolved from type lookup table."""

    model_path: str = ""
    """Relative BMD model path, e.g. ``Object1/Tree01.bmd``."""

    extra: bytes | None = None
    """Version-specific extra bytes from the OBJ record."""


@dataclass
class WorldLight:
    """A light source placed in the world.

    Extracted from WorldObject entries whose category is ``Light``.
    The C# client creates ``DynamicLight`` instances for these.
    """
    type: int = 0
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    color_r: float = 1.0
    color_g: float = 1.0
    color_b: float = 1.0
    radius: float = 500.0
    intensity: float = 1.0


@dataclass
class WorldWater:
    """A water surface / splashing object in the world."""
    type: int = 0
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    scale: float = 1.0


@dataclass
class WorldEffect:
    """An ambient or particle effect in the world.

    Examples: leaf effects, fire, smoke, light beams.
    """
    type: int = 0
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    scale: float = 1.0


@dataclass
class WorldNPC:
    """An NPC placed in the world.

    The C# client annotates these with ``[NpcInfo(type, name)]``.
    """
    type: int = 0
    name: str = ""
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    angle: float = 0.0  # Y-rotation (facing direction)
    model_path: str = ""


@dataclass
class WorldMonster:
    """A monster spawn point in the world.

    The C# client creates ``MonsterObject`` subclasses for these.
    Some have special properties like scale, blend mesh, etc.
    """
    type: int = 0
    name: str = ""
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    angle: float = 0.0  # Y-rotation (facing direction)
    model_path: str = ""
    scale: float = 1.0


@dataclass
class WorldData:
    """Complete parsed world data.

    This is the top-level output of ``read_world()``.  It aggregates
    terrain references and all classified world objects.
    """
    map_number: int = 0
    """World index (matches the MAP file's mapNumber)."""

    # Terrain references (optional — the world reader may receive
    # already-parsed terrain data but does NOT require it).
    terrain_att: Optional[TerrainAttributeData] = None
    terrain_map: Optional[TerrainMappingData] = None
    terrain_height: Optional[OZBData] = None
    terrain_light: Optional[OZBData] = None

    # World objects (all categories)
    objects: list[WorldObject] = field(default_factory=list)
    """All world objects, including those classified as lights/water etc."""

    # Semantic convenience groupings
    lights: list[WorldLight] = field(default_factory=list)
    water: list[WorldWater] = field(default_factory=list)
    effects: list[WorldEffect] = field(default_factory=list)
    npcs: list[WorldNPC] = field(default_factory=list)
    monsters: list[WorldMonster] = field(default_factory=list)

    # Player spawn (first player-spawn-type object found)
    spawn_x: float = 0.0
    spawn_y: float = 0.0
    spawn_z: float = 0.0


# ======================================================================
# Type classification tables
# ======================================================================

# ── Light type ranges ──────────────────────────────────────────────
# These object types are known to be light sources in the C# client.
LIGHT_TYPES: set[int] = {
    50,   # FireLight01
    51,   # FireLight02
    52,   # BonFire01
    90,   # StreetLight01
    130,  # Light01
    131,  # Light02
    132,  # Light03
}

# ── Water / liquid type ranges ────────────────────────────────────
WATER_TYPES: set[int] = {
    105,  # Waterspout01
}

# ── Effect / ambient type ranges ──────────────────────────────────
EFFECT_TYPES: set[int] = {
    # Light beams / glow effects (used in LostTower, Tarkan)
    # These are ModelObject subclasses with BlendState.Additive
}

# ── NPC type ranges ───────────────────────────────────────────────
# From Client.Main.Objects.NPCS namespace.
# The C# client maps NPC types via [NpcInfo(type, name)] attributes.
# This is an incomplete sample covering well-known NPCs.
NPC_TYPES: dict[int, str] = {
    236: "Mirage",
    237: "Charon",
    238: "Jewel Binder",
    239: "Seed Master",
    240: "Seed Researcher",
    241: "Seed Extractor",
    242: "Seed Transcender",
    243: "Osbourne",
    244: "Jerridon",
    245: "Silvia",
    246: "Rhea",
    247: "Marlon",
    248: "Elf Lala",
    249: "Eo the Craftsman",
    250: "Wandering Merchant",
    251: "Weapon Merchant",
    252: "Guard",
    253: "Gatekeeper",
    254: "Warehouse Keeper",
    255: "Golden Archer",
    256: "Guild Master",
    257: "Elf Soldier",
    258: "Catapult Merchant",
    259: "Siege Merchant",
    260: "Guild Map Manager",
}

# ── Monster type mapping ──────────────────────────────────────────
# From Client.Main.Objects.Monsters namespace.
# Monster type → (name, scale, model_index)
# type 0 → Monster01.bmd, type 1 → Monster02.bmd, etc.
MONSTER_NAMES: dict[int, str] = {
    0: "Spider",
    1: "Hound",
    2: "Budra Dragon",
    3: "Death Cow",
    4: "Ghost",
    5: "Hell Spider",
    6: "Sai Tear",
    7: "Larva",
    8: "Poison Bull",
    9: "Giant",
    10: "Yeti",
    11: "Yeti 2",
    12: "Elite Yeti",
    13: "Elite Hobgoblin",
    14: "Dark Knight",
    15: "Shadow",
    16: "Elite Skeleton",
    17: "Elite Giant",
    18: "Golem",
    19: "Mutant",
    20: "Elite Mutant",
    21: "Tantalos",
    22: "Ice Monster",
    23: "Elite Ice Monster",
    24: "Worm",
    25: "Elite Worm",
    26: "Knight of Darkness",
    27: "Death Gorgon",
    28: "Budge Dragon",
    29: "Gorgon",
    30: "Forest Monster",
    31: "Forest Elite",
    32: "Forest Golem",
    33: "Queen Bee",
    34: "Horned Mutant",
    35: "Death Angel",
    36: "Death Centurion",
    37: "Death Knight",
    38: "Balrog",
    39: "Iron Wheel",
    40: "Knight of Inferno",
    41: "Satyr",
    42: "Satyr of Inferno",
    43: "Tantallos",
    44: "Lizard King",
    45: "Lizard Warrior",
    46: "Lizard Mage",
    47: "Berserker",
    48: "Dragon",
    49: "Behemoth",
    50: "Sea Worm",
    51: "Silver Lizard Warrior",
    52: "Silver Lizard Mage",
    53: "Lizard Soldier",
    54: "Lizard Knight",
    55: "Silver Lizard Knight",
    56: "Mutant 2",
    57: "Mutant 3",
    58: "Mutant 4",
    59: "Mutant 5",
    60: "Mutant 6",
    61: "Mutant 7",
    62: "Mutant 8",
    63: "Mutant 9",
    64: "Mutant 10",
    65: "Mutant 11",
    66: "Mutant 12",
    67: "Mutant 13",
    68: "Mutant 14",
    69: "Mutant 15",
    70: "Phoenix of Darkness",
    71: "Dark Phoenix",
    72: "Phoenix of Darkness 2",
    73: "Dark Phoenix 2",
    74: "Dark Phoenix 3",
    75: "Dark Phoenix 4",
    76: "Lycanus 1",
    77: "Lycanus 2",
    78: "Lycanus 3",
    79: "Hydra",
    80: "Dark Wyvern",
    81: "Dark Wyvern 2",
    82: "Dark Wyvern 3",
    83: "Damaged Wyvern",
    84: "Red Wyvern",
    85: "Red Wyvern 2",
    86: "Red Wyvern 3",
    87: "Red Wyvern 4",
    88: "Wyvern Lord",
    89: "Werewolf",
    90: "Werewolf 2",
    91: "Alquamos",
    92: "Alquamos 2",
    93: "Werecat",
    94: "Werecat 2",
    95: "Fire Golem",
    96: "Fire Golem 2",
    97: "Fire Golem 3",
    98: "Fire Golem 4",
    99: "Fire Golem 5",
    100: "Fire Golem 6",
    101: "Fire Golem 7",
    102: "Fire Golem 8",
    103: "Skeleton Warrior",
    104: "Skeleton Warrior 2",
    105: "Skeleton Warrior 3",
    106: "Skeleton Warrior 4",
    107: "Skeleton Warrior 5",
    108: "Skeleton Warrior 6",
    109: "Skeleton Warrior 7",
    110: "Skeleton Warrior 8",
    111: "Skeleton Warrior 9",
    112: "Skeleton Warrior 10",
    113: "Skeleton Warrior 11",
    114: "Skeleton Warrior 12",
    115: "Skeleton Warrior 13",
    116: "Skeleton Warrior 14",
    117: "Skeleton Warrior 15",
    118: "Skeleton Warrior 16",
    119: "Skeleton Warrior 17",
    120: "Skeleton Warrior 18",
    121: "Skeleton Warrior 19",
    122: "Skeleton Warrior 20",
    123: "Boss Balrog",
    124: "Boss Balrog 2",
    125: "Kundun",
    126: "Kundun 2",
    127: "Dark Elf",
    128: "Dark Elf 2",
    129: "Dark Elf 3",
    130: "Dark Elf 4",
    131: "Dark Elf 5",
    132: "Dark Elf 6",
    133: "Dark Elf 7",
    134: "Dark Elf 8",
    135: "Dark Elf 9",
    136: "Phoenix of Darkness 3",
    137: "Medusa",
    138: "Medusa 2",
    139: "Medusa 3",
    140: "Medusa 4",
    141: "Medusa 5",
    142: "Medusa 6",
    143: "Medusa 7",
    144: "Medusa 8",
    145: "Medusa 9",
    146: "Uber Ghost",
    147: "Uber Ghost 2",
    148: "Uber Ghost 3",
    149: "Uber Ghost 4",
}

# Monsters that have special tweaks in the C# client
_MONSTER_SCALES: dict[int, float] = {
    8: 1.0,      # Poison Bull
    24: 1.0,     # Worm
    30: 0.75,    # Forest Monster
    38: 1.0,     # Balrog
    50: 1.8,     # Sea Worm
    307: 1.0,    # Forest Orc
    340: 1.0,    # Dark Elf
    344: 1.0,    # Balram
    351: 0.8,    # Splinter Wolf
    355: 1.1,    # Kentauros
    365: 1.0,    # Pouch Of Blessing
    455: 1.0,    # Giant Mammoth
    457: 1.0,    # Coolutin
    575: 1.0,    # Condra
}

# Monster model file index: most use Monster{type+1:03d}.bmd.
# Some override this; this table stores the file index for exceptions.
_MONSTER_MODEL_OVERRIDES: dict[int, int] = {
    38: 28,   # Balrog → Monster028.bmd
    50: 39,   # Sea Worm → Monster039.bmd
    22: 16,   # Ice Monster → Monster016.bmd
    24: 18,   # Worm → Monster018.bmd
    30: 24,   # Forest Monster → Monster024.bmd
}

# ── Monster type threshold ────────────────────────────────────────
# In MU Online the same numeric type can refer to a world object
# (e.g. Tree01 on map 1) OR a monster (e.g. Spider → Monster01.bmd).
# The distinction is context-dependent.  We treat types below this
# threshold as regular world objects by default.
_WORLD_OBJECT_TYPE_MAX: int = 149


# ======================================================================
# Classification helpers
# ======================================================================


def classify_object_type(type_id: int) -> WorldObjectCategory:
    """Classify an OBJ type number into a semantic category.

    Only types we can reliably identify are given a special category;
    everything else defaults to ``Object``.  Monsters and NPCs whose
    type numbers overlap with world objects cannot be automatically
    classified from OBJ data alone.

    Args:
        type_id: Object type number (0-65535).

    Returns:
        WorldObjectCategory.
    """
    if type_id in LIGHT_TYPES:
        return WorldObjectCategory.Light
    if type_id in WATER_TYPES:
        return WorldObjectCategory.Water
    if type_id in EFFECT_TYPES:
        return WorldObjectCategory.Effect
    if type_id in NPC_TYPES:
        return WorldObjectCategory.NPC
    return WorldObjectCategory.Object


def resolve_object_name(type_id: int, map_number: int = 0) -> str:
    """Resolve a human-readable name for an object type.

    Priority: known special types (light, water, NPC) > monster names
    > generic fallback.

    Args:
        type_id: Object type number.
        map_number: World map number (for per-world name tables).

    Returns:
        Human-readable name string.
    """
    # Known special types take priority
    if type_id in NPC_TYPES:
        return NPC_TYPES[type_id]
    if type_id in LIGHT_TYPES:
        _names = {50: "FireLight", 51: "FireLight", 52: "BonFire",
                  90: "StreetLight", 130: "Light", 131: "Light",
                  132: "Light"}
        return _names.get(type_id, "Light")
    if type_id in WATER_TYPES:
        return "WaterSpout"
    # Monster names (these are less specific but better than "ObjectNN")
    if type_id in MONSTER_NAMES:
        return MONSTER_NAMES[type_id]
    return f"Object{type_id:02d}"


def resolve_model_path(type_id: int, map_number: int = 0) -> str:
    """Resolve the expected BMD model path for an object type.

    Args:
        type_id: Object type number.
        map_number: World map number.

    Returns:
        Relative model path, e.g. ``Object1/Object01.bmd``.
    """
    if type_id in MONSTER_NAMES and type_id > _WORLD_OBJECT_TYPE_MAX:
        # Only resolve as monster path for types beyond the
        # world-object range (where overlap is unlikely).
        file_idx = _MONSTER_MODEL_OVERRIDES.get(type_id, type_id + 1)
        return f"Monster/Monster{file_idx:03d}.bmd"
    if type_id in NPC_TYPES:
        return f"NPC/Npc{type_id:03d}.bmd"
    # World objects: Object{mapNumber}/Object{type+1:02d}.bmd
    file_idx = type_id + 1
    return f"Object{map_number}/Object{file_idx:02d}.bmd"


# ======================================================================
# World reader
# ======================================================================


def read_world(
    obj_data: OBJData,
    att_data: Optional[TerrainAttributeData] = None,
    map_data: Optional[TerrainMappingData] = None,
    height_data: Optional[OZBData] = None,
    light_data: Optional[OZBData] = None,
) -> WorldData:
    """Build a complete world description from parsed terrain data.

    This is the main entry point.  It takes already-parsed OBJ data
    (from ``read_obj()``) and classifies every object by type.

    Args:
        obj_data: Parsed OBJ object placement data (required).
        att_data: Optional parsed ATT terrain attributes.
        map_data: Optional parsed MAP texture mapping.
        height_data: Optional parsed OZB heightmap.
        light_data: Optional parsed OZB lightmap.

    Returns:
        WorldData with classified objects.
    """
    world = WorldData(
        map_number=obj_data.map_number,
        terrain_att=att_data,
        terrain_map=map_data,
        terrain_height=height_data,
        terrain_light=light_data,
    )

    for mo in obj_data.objects:
        cat = classify_object_type(mo.type)
        name = resolve_object_name(mo.type, obj_data.map_number)

        world_obj = WorldObject(
            type=mo.type,
            category=cat,
            position_x=mo.position_x,
            position_y=mo.position_y,
            position_z=mo.position_z,
            angle_x=mo.angle_x,
            angle_y=mo.angle_y,
            angle_z=mo.angle_z,
            scale=mo.scale,
            name=name,
            model_path=resolve_model_path(mo.type, obj_data.map_number),
            extra=mo.extra,
        )
        world.objects.append(world_obj)

        # Route into semantic sub-lists
        if cat == WorldObjectCategory.Light:
            world.lights.append(WorldLight(
                type=mo.type,
                position_x=mo.position_x,
                position_y=mo.position_y,
                position_z=mo.position_z,
            ))
        elif cat == WorldObjectCategory.Water:
            world.water.append(WorldWater(
                type=mo.type,
                position_x=mo.position_x,
                position_y=mo.position_y,
                position_z=mo.position_z,
                scale=mo.scale,
            ))
        elif cat == WorldObjectCategory.Effect:
            world.effects.append(WorldEffect(
                type=mo.type,
                position_x=mo.position_x,
                position_y=mo.position_y,
                position_z=mo.position_z,
                scale=mo.scale,
            ))
        elif cat == WorldObjectCategory.NPC:
            npc_model = resolve_model_path(mo.type, obj_data.map_number)
            world.npcs.append(WorldNPC(
                type=mo.type,
                name=name,
                position_x=mo.position_x,
                position_y=mo.position_y,
                position_z=mo.position_z,
                angle=mo.angle_y,
                model_path=npc_model,
            ))
        elif cat == WorldObjectCategory.Monster:
            mon_scale = _MONSTER_SCALES.get(mo.type, mo.scale)
            mon_model = resolve_model_path(mo.type, obj_data.map_number)
            world.monsters.append(WorldMonster(
                type=mo.type,
                name=name,
                position_x=mo.position_x,
                position_y=mo.position_y,
                position_z=mo.position_z,
                angle=mo.angle_y,
                model_path=mon_model,
                scale=mon_scale,
            ))

    # Find player spawn (first object that looks like a spawn point)
    for obj in world.objects:
        # Spawn is typically type 0 or a very low-numbered object
        # placed near the centre of the map.  Use the first non-None
        # object with a reasonable position.
        if obj.type == 0:
            world.spawn_x = obj.position_x
            world.spawn_y = obj.position_y
            world.spawn_z = obj.position_z
            break

    return world
