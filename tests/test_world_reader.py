# MU Online Blender Tools - Tests for World Reader
#
# Run with:  python -m unittest tests.test_world_reader -v

"""
Tests for ``mu_blender_tools.readers.world_reader``.

Verifies object classification, semantic groupings, model path resolution,
and coordinate preservation.
"""

from __future__ import annotations

import sys
import unittest

sys.path.insert(0, ".")

from mu_blender_tools.readers.world_reader import (
    WorldObjectCategory,
    read_world,
    classify_object_type,
    resolve_object_name,
    resolve_model_path,
    WorldObject,
    WorldData,
    WorldLight,
    WorldWater,
    WorldEffect,
    WorldNPC,
    WorldMonster,
)
from mu_blender_tools.readers.terrain_reader import (
    OBJData,
    MapObject,
    TerrainAttributeData,
    TerrainMappingData,
    OZBData,
)


# ======================================================================
# Helpers
# ======================================================================

def _make_obj(objects: list[tuple[int, float, float, float,
                                   float, float, float, float]]) -> OBJData:
    """Create OBJData from a list of (type, px, py, pz, ax, ay, az, scale)."""
    return OBJData(
        version=0,
        map_number=1,
        objects=[
            MapObject(
                type=t, position_x=px, position_y=py, position_z=pz,
                angle_x=ax, angle_y=ay, angle_z=az, scale=sc,
            )
            for t, px, py, pz, ax, ay, az, sc in objects
        ],
    )


# ======================================================================
# Tests: Object classification
# ======================================================================

class TestClassifyObjectType(unittest.TestCase):
    """Test type-to-category mapping."""

    def test_regular_object(self) -> None:
        self.assertEqual(classify_object_type(0), WorldObjectCategory.Object)
        self.assertEqual(classify_object_type(10), WorldObjectCategory.Object)
        self.assertEqual(classify_object_type(100), WorldObjectCategory.Object)

    def test_light_type(self) -> None:
        self.assertEqual(classify_object_type(50), WorldObjectCategory.Light)
        self.assertEqual(classify_object_type(90), WorldObjectCategory.Light)
        self.assertEqual(classify_object_type(130), WorldObjectCategory.Light)

    def test_water_type(self) -> None:
        self.assertEqual(classify_object_type(105), WorldObjectCategory.Water)

    def test_npc_type(self) -> None:
        self.assertEqual(classify_object_type(248), WorldObjectCategory.NPC)
        self.assertEqual(classify_object_type(249), WorldObjectCategory.NPC)

    def test_monster_types_are_not_auto_classified(self) -> None:
        """Monster type numbers overlap with world objects, so OBJ-based
        classification cannot reliably identify them."""
        self.assertEqual(classify_object_type(0), WorldObjectCategory.Object)
        self.assertEqual(classify_object_type(38), WorldObjectCategory.Object)
        # Type 50 is in LIGHT_TYPES, so it is classified as Light, not Object.
        self.assertEqual(classify_object_type(50), WorldObjectCategory.Light)

    def test_high_number_defaults_to_object(self) -> None:
        self.assertEqual(classify_object_type(200), WorldObjectCategory.Object)
        self.assertEqual(classify_object_type(500), WorldObjectCategory.Object)


# ======================================================================
# Tests: Name resolution
# ======================================================================

class TestResolveObjectName(unittest.TestCase):
    """Test type-to-name resolution."""

    def test_monster_name(self) -> None:
        self.assertEqual(resolve_object_name(38), "Balrog")
        self.assertEqual(resolve_object_name(0), "Spider")  # type 0 = Spider in monster table

    def test_npc_name(self) -> None:
        self.assertEqual(resolve_object_name(248), "Elf Lala")
        self.assertEqual(resolve_object_name(249), "Eo the Craftsman")

    def test_light_name(self) -> None:
        self.assertEqual(resolve_object_name(130), "Light")
        self.assertEqual(resolve_object_name(90), "StreetLight")

    def test_unknown_fallback(self) -> None:
        self.assertEqual(resolve_object_name(999), "Object999")


# ======================================================================
# Tests: Model path resolution
# ======================================================================

class TestResolveModelPath(unittest.TestCase):
    """Test type-to-model-path resolution."""

    def test_world_object_path(self) -> None:
        path = resolve_model_path(0, map_number=1)
        self.assertIn("Object1/Object01.bmd", path)

    def test_world_object_path_other_map(self) -> None:
        path = resolve_model_path(5, map_number=3)
        self.assertIn("Object3/Object06.bmd", path)

    def test_monster_path(self) -> None:
        # Type 38 is Balrog but its type is in the world-object range,
        # so resolve_model_path returns a world-object path by default.
        path = resolve_model_path(38, map_number=1)
        self.assertIn("Object1/Object39.bmd", path)

    def test_npc_path(self) -> None:
        path = resolve_model_path(248, map_number=1)
        self.assertIn("NPC/Npc248.bmd", path)


# ======================================================================
# Tests: read_world
# ======================================================================

class TestReadWorld(unittest.TestCase):
    """Test the main world reader function."""

    def test_empty_world(self) -> None:
        obj = _make_obj([])
        world = read_world(obj)
        self.assertEqual(world.map_number, 1)
        self.assertEqual(len(world.objects), 0)

    def test_classification_routing(self) -> None:
        obj = _make_obj([
            (0, 100, 200, 0, 0, 0, 0, 1.0),      # Object (tree)
            (90, 500, 600, 0, 0, 0, 0, 1.0),     # Light (StreetLight)
            (105, 300, 400, 0, 0, 0, 0, 2.0),    # Water (Waterspout)
            (248, 200, 300, 0, 0, 0, 0, 1.0),    # NPC (Elf Lala)
            (38, 400, 500, 0, 0, 0, 0, 1.5),     # Object (Balrog — monster type < 150)
        ])
        world = read_world(obj)
        self.assertEqual(len(world.objects), 5)
        self.assertEqual(len(world.lights), 1)
        self.assertEqual(len(world.water), 1)
        self.assertEqual(len(world.npcs), 1)
        self.assertEqual(len(world.monsters), 0)  # monsters < 150 are not auto-classified
        self.assertEqual(len(world.effects), 0)

    def test_light_properties(self) -> None:
        obj = _make_obj([
            (130, 100, 200, 50, 0, 0, 0, 1.0),
        ])
        world = read_world(obj)
        light = world.lights[0]
        self.assertAlmostEqual(light.position_x, 100)
        self.assertAlmostEqual(light.position_y, 200)
        self.assertAlmostEqual(light.position_z, 50)

    def test_npc_properties(self) -> None:
        obj = _make_obj([
            (249, 300, 400, 30, 0, 90, 0, 1.0),  # Eo the Craftsman
        ])
        world = read_world(obj)
        npc = world.npcs[0]
        self.assertEqual(npc.name, "Eo the Craftsman")
        self.assertAlmostEqual(npc.angle, 90)

    def test_monster_properties(self) -> None:
        """Monster types < 150 are not auto-classified; they remain Objects."""
        obj = _make_obj([
            (38, 500, 600, 20, 0, 45, 0, 1.2),  # Balrog (type 38 < 150)
        ])
        world = read_world(obj)
        self.assertEqual(len(world.monsters), 0)
        self.assertEqual(len(world.objects), 1)
        self.assertEqual(world.objects[0].name, "Balrog")  # name still resolves

    def test_water_properties(self) -> None:
        obj = _make_obj([
            (105, 700, 800, 10, 0, 0, 0, 3.0),
        ])
        world = read_world(obj)
        water = world.water[0]
        self.assertAlmostEqual(water.scale, 3.0)

    def test_object_preserves_raw_data(self) -> None:
        obj = _make_obj([
            (7, 111, 222, 333, 10, 20, 30, 2.5),
        ])
        world = read_world(obj)
        wo = world.objects[0]
        self.assertEqual(wo.type, 7)
        self.assertAlmostEqual(wo.position_x, 111)
        self.assertAlmostEqual(wo.angle_y, 20)
        self.assertAlmostEqual(wo.scale, 2.5)

    def test_with_terrain_data(self) -> None:
        obj = _make_obj([(0, 0, 0, 0, 0, 0, 0, 1.0)])
        att = TerrainAttributeData(version=0, index=0, width=255, height=255)
        mp = TerrainMappingData(version=1, map_number=1)
        h = OZBData(width=256, height=256, data=b"\x80" * (256 * 256 * 4))
        world = read_world(obj, att_data=att, map_data=mp, height_data=h)
        self.assertIsNotNone(world.terrain_att)
        self.assertIsNotNone(world.terrain_map)
        self.assertIsNotNone(world.terrain_height)


# ======================================================================
# Tests: Spawn point
# ======================================================================

class TestSpawnPoint(unittest.TestCase):
    """Test player spawn detection."""

    def test_spawn_detected(self) -> None:
        obj = _make_obj([
            (0, 1000, 2000, 0, 0, 0, 0, 1.0),
            (1, 500, 600, 0, 0, 0, 0, 1.0),
        ])
        world = read_world(obj)
        self.assertAlmostEqual(world.spawn_x, 1000)
        self.assertAlmostEqual(world.spawn_y, 2000)


# ======================================================================
# Tests: Edge cases
# ======================================================================

class TestWorldEdgeCases(unittest.TestCase):
    """Test edge cases for world reading."""

    def test_large_coordinates(self) -> None:
        """Large float coordinates should be preserved."""
        obj = _make_obj([
            (0, 999999.0, -999999.0, 0, 0, 0, 0, 100.0),
        ])
        world = read_world(obj)
        self.assertAlmostEqual(world.objects[0].position_x, 999999.0)
        self.assertAlmostEqual(world.objects[0].scale, 100.0)

    def test_negative_type_handled(self) -> None:
        """Negative type numbers should not crash (though unusual)."""
        obj = _make_obj([
            (-1, 0, 0, 0, 0, 0, 0, 1.0),
        ])
        world = read_world(obj)
        self.assertEqual(world.objects[0].category, WorldObjectCategory.Object)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
