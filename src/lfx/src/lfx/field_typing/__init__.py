"""Field typing module for lfx package."""

from typing import Text

try:
    from langchain_core.tools import Tool
except ImportError:

    class Tool:
        pass


from lfx.field_typing.range_spec import RangeSpec

__all__ = ["RangeSpec", "Text", "Tool"]
