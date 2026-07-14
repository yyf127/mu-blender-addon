# MU Online Blender Tools - Serializer Interface
#
# A Serializer converts in-memory reader/builder data back into the
# original MU Online binary format (bytes).
#
# Examples:
#   BMDSerializer   → BMD dataclass → bytes (reverse of BMDReader)
#   ATTSerializer   → TerrainAttributeData → bytes
#   MAPSerializer   → TerrainMappingData → bytes
#   OZBSerializer   → OZBData → bytes
#   OBJSerializer   → OBJData → bytes

from __future__ import annotations

import abc
from typing import Generic, TypeVar

T = TypeVar("T")
"""The input data type this serializer accepts."""


class BaseSerializer(abc.ABC, Generic[T]):
    """Abstract interface for converting reader data back to bytes.

    A serializer is the reverse of a Reader: it takes the same
    dataclass and produces the equivalent binary representation.
    """

    @abc.abstractmethod
    def serialize(self, data: T) -> bytes:
        """Convert *data* to its binary format.

        Args:
            data: The in-memory data structure to serialize.

        Returns:
            Raw bytes suitable for writing to a file.
        """
        ...

    @property
    @abc.abstractmethod
    def file_extension(self) -> str:
        """Target file extension including the dot, e.g. ``.bmd``."""
        ...

    @property
    @abc.abstractmethod
    def format_name(self) -> str:
        """Human-readable format name, e.g. ``MU Online BMD Model``."""
        ...
