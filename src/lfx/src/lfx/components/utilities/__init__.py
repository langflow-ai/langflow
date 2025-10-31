from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.utilities.calculator_core import CalculatorComponent
    from lfx.components.utilities.current_date import CurrentDateComponent
    from lfx.components.utilities.id_generator import IDGeneratorComponent
    from lfx.components.utilities.python_repl_core import PythonREPLComponent
    from lfx.components.utilities.sql_executor import SQLComponent

_dynamic_imports = {
    "CalculatorComponent": "calculator_core",
    "CurrentDateComponent": "current_date",
    "IDGeneratorComponent": "id_generator",
    "PythonREPLComponent": "python_repl_core",
    "SQLComponent": "sql_executor",
}

__all__ = [
    "CalculatorComponent",
    "CurrentDateComponent",
    "IDGeneratorComponent",
    "PythonREPLComponent",
    "SQLComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import utility components on attribute access."""
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
