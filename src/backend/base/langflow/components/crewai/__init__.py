from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.components._importing import import_mod

if TYPE_CHECKING:
    from .crewai import CrewAIAgentComponent
    from .hierarchical_crew import HierarchicalCrewComponent
    from .hierarchical_task import HierarchicalTaskComponent
    from .sequential_crew import SequentialCrewComponent
    from .sequential_task import SequentialTaskComponent
    from .sequential_task_agent import SequentialTaskAgentComponent

_dynamic_imports = {
    "CrewAIAgentComponent": "crewai",
    "HierarchicalCrewComponent": "hierarchical_crew",
    "HierarchicalTaskComponent": "hierarchical_task",
    "SequentialCrewComponent": "sequential_crew",
    "SequentialTaskAgentComponent": "sequential_task_agent",
    "SequentialTaskComponent": "sequential_task",
}

__all__ = [
    "CrewAIAgentComponent",
    "HierarchicalCrewComponent",
    "HierarchicalTaskComponent",
    "SequentialCrewComponent",
    "SequentialTaskAgentComponent",
    "SequentialTaskComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import crewai components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
