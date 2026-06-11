"""Base class for Pipecat Tool components.

Concrete subclasses live under ``lfx/components/pipecat_tools/`` and return a
``(FunctionSchema, async handler)`` tuple consumable by any Pipecat LLM/S2S
service via ``llm.register_function(schema.name, handler)``.

The handler receives a ``FunctionCallParams`` object from Pipecat. To return a
result it must call ``await params.result_callback(result_dict)``.
"""

from abc import abstractmethod
from typing import TYPE_CHECKING

from lfx.custom.custom_component.component import Component
from lfx.field_typing.voice_types import PipecatTool, PipecatToolHandler
from lfx.template.field.base import Output

if TYPE_CHECKING:
    from pipecat.adapters.schemas.function_schema import FunctionSchema


class PipecatToolComponent(Component):
    """Base for voice tool components.

    Subclasses implement two methods:
      - ``build_function_schema()`` returns a ``FunctionSchema``
      - ``build_handler()`` returns an async callable taking ``FunctionCallParams``

    The default ``build_tool()`` output method packs them into a ``PipecatTool``
    tuple.
    """

    trace_type = "pipecat_tool"
    category = "pipecat"

    outputs = [
        Output(
            display_name="Tool",
            name="tool",
            method="build_tool",
            types=["PipecatTool"],
        ),
    ]

    @abstractmethod
    def build_function_schema(self) -> "FunctionSchema":
        """Return the Pipecat FunctionSchema describing this tool."""

    @abstractmethod
    def build_handler(self) -> PipecatToolHandler:
        """Return the async handler invoked when the LLM calls this tool.

        The handler signature is ``async def handler(params: FunctionCallParams) -> None``
        and must call ``await params.result_callback(result)`` to return a value.
        """

    def build_tool(self) -> PipecatTool:
        return (self.build_function_schema(), self.build_handler())
