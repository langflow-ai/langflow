from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.helpers.calculator_core import CalculatorComponent
    from lfx.components.helpers.create_list import CreateListComponent
    from lfx.components.helpers.current_date import CurrentDateComponent
    from lfx.components.helpers.id_generator import IDGeneratorComponent
    from lfx.components.helpers.memory import MemoryComponent
    from lfx.components.helpers.output_parser import OutputParserComponent
    from lfx.components.helpers.store_message import MessageStoreComponent

_dynamic_imports = {
    "CalculatorComponent": "calculator_core",
    "CreateListComponent": "create_list",
    "CurrentDateComponent": "current_date",
    "IDGeneratorComponent": "id_generator",
    "MemoryComponent": "memory",
    "OutputParserComponent": "output_parser",
    "MessageStoreComponent": "store_message",
}

__all__ = [
    "CalculatorComponent",
    "CreateListComponent",
    "CurrentDateComponent",
    "IDGeneratorComponent",
    "MemoryComponent",
    "MessageStoreComponent",
    "OutputParserComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import helper components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)

    # CurrentDateComponent, CalculatorComponent, and IDGeneratorComponent were moved to utilities
    # Forward them to utilities for backwards compatibility
    if attr_name in ("CurrentDateComponent", "CalculatorComponent", "IDGeneratorComponent"):
        from lfx.components import utilities

        result = getattr(utilities, attr_name)
        globals()[attr_name] = result
        return result

    # MemoryComponent was moved to models_and_agents
    # Forward it to models_and_agents for backwards compatibility
    if attr_name == "MemoryComponent":
        from lfx.components import models_and_agents

        result = getattr(models_and_agents, attr_name)
        globals()[attr_name] = result
        return result

    # CreateListComponent, MessageStoreComponent, and OutputParserComponent were moved to processing
    # Forward them to processing for backwards compatibility
    if attr_name == "CreateListComponent":
        from lfx.components import processing

        result = getattr(processing, attr_name)
        globals()[attr_name] = result
        return result
    if attr_name == "MessageStoreComponent":
        from lfx.components import processing

        result = processing.MessageStoreComponent
        globals()[attr_name] = result
        return result
    if attr_name == "OutputParserComponent":
        from lfx.components import processing

        result = getattr(processing, attr_name)
        globals()[attr_name] = result
        return result

    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
