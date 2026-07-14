# MU Online Blender Tools - Tests for Export Framework
#
# Run with:  python -m unittest tests.test_export_framework -v

"""
Tests for ``mu_blender_tools.export`` package.

Verifies that all abstract interfaces are properly defined and that
the concrete stubs have the correct structure.
"""

from __future__ import annotations

import sys
import unittest

sys.path.insert(0, ".")


# ======================================================================
# Test: Base interfaces
# ======================================================================

class TestBaseSerializer(unittest.TestCase):
    """Test BaseSerializer abstract interface."""

    def test_cannot_instantiate_abstract(self) -> None:
        from mu_blender_tools.export.base_serializer import BaseSerializer
        with self.assertRaises(TypeError):
            BaseSerializer()  # type: ignore[abstract]

    def test_has_required_methods(self) -> None:
        from mu_blender_tools.export.base_serializer import BaseSerializer
        self.assertTrue(hasattr(BaseSerializer, "serialize"))
        self.assertTrue(hasattr(BaseSerializer, "file_extension"))
        self.assertTrue(hasattr(BaseSerializer, "format_name"))


class TestBaseWriter(unittest.TestCase):
    """Test BaseWriter abstract interface."""

    def test_cannot_instantiate_abstract(self) -> None:
        from mu_blender_tools.export.base_writer import BaseWriter
        with self.assertRaises(TypeError):
            BaseWriter()  # type: ignore[abstract]

    def test_has_required_methods(self) -> None:
        from mu_blender_tools.export.base_writer import BaseWriter
        self.assertTrue(hasattr(BaseWriter, "write"))
        self.assertTrue(hasattr(BaseWriter, "supports_encryption"))
        self.assertTrue(hasattr(BaseWriter, "description"))


class TestBaseExporter(unittest.TestCase):
    """Test BaseExporter abstract interface."""

    def test_cannot_instantiate_abstract(self) -> None:
        from mu_blender_tools.export.base_exporter import BaseExporter
        with self.assertRaises(TypeError):
            BaseExporter()  # type: ignore[abstract]

    def test_has_required_methods(self) -> None:
        from mu_blender_tools.export.base_exporter import BaseExporter
        self.assertTrue(hasattr(BaseExporter, "export"))
        self.assertTrue(hasattr(BaseExporter, "validate"))
        self.assertTrue(hasattr(BaseExporter, "export_name"))
        self.assertTrue(hasattr(BaseExporter, "file_extensions"))


# ======================================================================
# Test: BMD exporter
# ======================================================================

class TestBMDExporter(unittest.TestCase):
    """Test BMD exporter stub."""

    def setUp(self) -> None:
        from mu_blender_tools.export.bmd_exporter import BMDExporter, BMDSerializer
        self.serializer = BMDSerializer()
        self.exporter = BMDExporter()

    def test_serializer_properties(self) -> None:
        self.assertEqual(self.serializer.file_extension, ".bmd")
        self.assertIn("BMD", self.serializer.format_name)

    def test_serialize_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            self.serializer.serialize(None)

    def test_exporter_properties(self) -> None:
        self.assertIn(".bmd", self.exporter.file_extensions)
        self.assertIn("BMD", self.exporter.export_name)

    def test_export_requires_writer(self) -> None:
        with self.assertRaises(ValueError, msg="Writer not set"):
            self.exporter.export(None, "/tmp/test.bmd")


# ======================================================================
# Test: Terrain exporter
# ======================================================================

class TestTerrainExporter(unittest.TestCase):
    """Test Terrain exporter stub."""

    def setUp(self) -> None:
        from mu_blender_tools.export.terrain_exporter import (
            TerrainExporter,
            ATTSerializer,
            MAPSerializer,
            OZBSerializer,
            OBJSerializer,
        )
        self.exporter = TerrainExporter()
        self.serializers = {
            "att": ATTSerializer(),
            "map": MAPSerializer(),
            "ozb": OZBSerializer(),
            "obj": OBJSerializer(),
        }

    def test_file_extensions(self) -> None:
        exts = self.exporter.file_extensions
        for ext in [".att", ".map", ".ozb", ".obj"]:
            self.assertIn(ext, exts)

    def test_export_requires_writer(self) -> None:
        with self.assertRaises(ValueError, msg="Writer not set"):
            self.exporter.export(None, "/tmp/test.att")


# ======================================================================
# Test: World exporter
# ======================================================================

class TestWorldExporter(unittest.TestCase):
    """Test World exporter stub."""

    def setUp(self) -> None:
        from mu_blender_tools.export.world_exporter import WorldExporter
        self.exporter = WorldExporter()

    def test_exporter_properties(self) -> None:
        self.assertIn("World", self.exporter.export_name)

    def test_export_requires_writer(self) -> None:
        with self.assertRaises(ValueError, msg="Writer not set"):
            self.exporter.export(None, "/tmp/")


# ======================================================================
# Test: Scene exporter
# ======================================================================

class TestSceneExporter(unittest.TestCase):
    """Test Scene exporter stub."""

    def setUp(self) -> None:
        from mu_blender_tools.export.scene_exporter import SceneExporter
        self.exporter = SceneExporter()

    def test_exporter_properties(self) -> None:
        self.assertIn("Scene", self.exporter.export_name)
        self.assertIn(".bmd", self.exporter.file_extensions)

    def test_export_requires_writer(self) -> None:
        with self.assertRaises(ValueError, msg="Writer not set"):
            self.exporter.export(None, "/tmp/")


# ======================================================================
# Test: Package exports
# ======================================================================

class TestPackageExports(unittest.TestCase):
    """Test that the export package exports the expected names."""

    def test_package_importable(self) -> None:
        import mu_blender_tools.export  # noqa: F811

    def test_serializer_abstract_method_signature(self) -> None:
        from mu_blender_tools.export.base_serializer import BaseSerializer
        import inspect
        sig = inspect.signature(BaseSerializer.serialize)
        params = list(sig.parameters.keys())
        self.assertIn("data", params)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
