# Re-export everything from lfx.field_typing.constants for backward compatibility.
# Uses PEP 562 __getattr__ so that importing this module does NOT trigger the
# full langchain import chain at module load time.  The previous bulk
# ``from lfx.field_typing.constants import (AgentExecutor, ...)`` triggered
# lfx's own PEP 562 __getattr__ for every symbol in that list, importing 30+
# langchain modules eagerly and defeating the lazy-loading optimisation on the
# lfx side.  This mirrors the approach used there.
#
# Cost analysis of each eager import below (langchain modules pulled):
#   Callable, Text                               → 0
#   lfx Code, NestedDict, Object                 → 0
#   lfx.schema.data Data                         → 0
#   lfx.schema.dataframe DataFrame               → 15  ← lazy
#   langflow.schema.message Message              → 80  ← lazy
from __future__ import annotations

from collections.abc import Callable  # noqa: F401  re-export
from typing import Any, Text  # noqa: F401  Text is a re-export

# Non-langchain symbols that are cheap and always safe to import eagerly:
from lfx.field_typing.constants import Code, NestedDict, Object  # noqa: F401  re-exports
from lfx.schema.data import Data  # noqa: F401  re-export


def __getattr__(name: str) -> Any:
    """Lazily resolve langchain types, aggregate dicts, and transitive-langchain types.

    DataFrame and Message are handled here (not eager) because their import
    chains transitively pull ~15 and ~80 langchain modules respectively.

    All other symbols are forwarded to lfx.field_typing.constants, which
    resolves them via its own PEP 562 __getattr__ only when actually needed.
    """
    if name == "Message":
        from langflow.schema.message import Message

        globals()["Message"] = Message
        return Message
    if name == "DataFrame":
        from lfx.schema.dataframe import DataFrame

        globals()["DataFrame"] = DataFrame
        return DataFrame
    if name == "CUSTOM_COMPONENT_SUPPORTED_TYPES":
        import lfx.field_typing.constants as _c
        from lfx.schema.dataframe import DataFrame as _DataFrame

        from langflow.schema.message import Message as _Message

        result = {**_c.CUSTOM_COMPONENT_SUPPORTED_TYPES, "Message": _Message, "DataFrame": _DataFrame}
        globals()["CUSTOM_COMPONENT_SUPPORTED_TYPES"] = result
        return result
    import lfx.field_typing.constants as _c

    try:
        return getattr(_c, name)
    except AttributeError:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg) from None
