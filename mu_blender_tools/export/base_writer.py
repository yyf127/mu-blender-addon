# MU Online Blender Tools - Writer Interface
#
# A Writer takes serialized bytes and writes them to a file or stream.
# Implementations may support plain binary files, encrypted files
# (FileCryptor / ModulusCryptor), or streams.

from __future__ import annotations

import abc
import io
from typing import BinaryIO, Optional


class BaseWriter(abc.ABC):
    """Abstract interface for writing bytes to a storage target.

    The default implementation writes to a file on disk.
    Subclasses can add encryption, compression, or streaming.
    """

    @abc.abstractmethod
    def write(self, data: bytes, path: str) -> None:
        """Write *data* to the file at *path*.

        Args:
            data: The serialized bytes to write.
            path: Destination file path.

        Raises:
            OSError: On write failure.
        """
        ...

    def write_stream(self, data: bytes, stream: BinaryIO) -> None:
        """Write *data* to an open binary stream.

        The default implementation calls ``stream.write(data)``.
        Subclasses may override to add encryption on-the-fly.

        Args:
            data: The serialized bytes to write.
            stream: An open binary stream (e.g. ``io.BytesIO``).

        Raises:
            OSError: On write failure.
        """
        stream.write(data)

    @property
    @abc.abstractmethod
    def supports_encryption(self) -> bool:
        """Whether this writer applies game-format encryption."""
        ...

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Human-readable description, e.g. ``Plain binary writer``."""
        ...
