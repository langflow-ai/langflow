"""Agents module - backwards compatibility alias for models_and_agents.

This module provides backwards compatibility by forwarding all imports
to models_and_agents where the actual agent components are located.
"""

from __future__ import annotations

from typing import Any

# Import __all__ from models_and_agents to match its exports
from lfx.components.models_and_agents import __all__ as _models_and_agents_all

__all__ = list(_models_and_agents_all)


def __getattr__(attr_name: str) -> Any:
    """Forward attribute access to models_and_agents."""
    from lfx.components import models_and_agents

    return getattr(models_and_agents, attr_name)


def __dir__() -> list[str]:
    """Return directory of models_and_agents."""
    from lfx.components import models_and_agents

    return dir(models_and_agents)
