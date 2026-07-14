# MU Online Blender Tools - Unified Logging
#
# Centralised logging configuration for the entire addon.
# Every module should import ``_logger`` from here instead of calling
# ``logging.getLogger()`` directly.

from __future__ import annotations

import logging
from typing import Optional

# ── Root logger name ──────────────────────────────────────────────
# All modules share this prefix so that log messages can be filtered
# via ``logging.getLogger("mu_blender_tools")``.
ROOT_LOGGER_NAME: str = "mu_blender_tools"

# ── Logger cache ──────────────────────────────────────────────────
_loggers: dict[str, logging.Logger] = {}


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a MU Blender Tools logger.

    If *name* is ``None`` (default) returns the root addon logger.
    Otherwise returns ``"mu_blender_tools.<name>"``.

    Args:
        name: Optional sub-name (module or component name).

    Returns:
        A :class:`logging.Logger` instance.
    """
    key = f"{ROOT_LOGGER_NAME}.{name}" if name else ROOT_LOGGER_NAME
    if key not in _loggers:
        _loggers[key] = logging.getLogger(key)
    return _loggers[key]


# Convenience reference — import as::
#   from .._logging import logger
logger = get_logger()
