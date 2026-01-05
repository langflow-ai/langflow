"""Backwards compatibility module for lfx.logging.

This module provides backwards compatibility for code that imports from lfx.logging.
All functionality has been moved to lfx.log.
"""

# Re-export everything from lfx.log for backwards compatibility
from lfx.log.logger import configure, logger

# Maintain the same __all__ exports
__all__ = ["configure", "logger"]
