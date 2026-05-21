"""Trigger components.

A trigger component fires the containing flow on some external signal
(time, queue, event). The ``CronTrigger`` is the time-based one.

Lazy import pattern matches every other category: ``_dynamic_imports``
maps the class name to its module file and the global ``__getattr__``
in ``lfx.components.__init__`` does the actual import on first
attribute access. This keeps server cold-start times low when most
trigger types are not used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .cron_trigger import CronTriggerComponent

_dynamic_imports: dict[str, str] = {
    "CronTriggerComponent": "cron_trigger",
}

__all__ = ["CronTriggerComponent"]


def __getattr__(attr_name: str) -> Any:
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
