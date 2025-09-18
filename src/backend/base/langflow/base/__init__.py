"""Backwards compatibility module for langflow.base.

This module imports from lfx.base to maintain compatibility with existing code
that expects to import from langflow.base.
"""

# Import all base modules from lfx for backwards compatibility
from lfx.base import *  # noqa: F403
