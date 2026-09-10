"""Complete schema-aware tool output for Langflow's Agent input."""

from collections.abc import Callable
from copy import deepcopy
from typing import Any, ClassVar

from langchain_core.tools import StructuredTool
from lfx.io import IntInput, Output, SecretStrInput

from lfx_fxmacrodata._public_client import Operation, list_operations
from lfx_fxmacrodata.client import DOCUMENTATION, query
from lfx_fxmacrodata.component import CredentialSafeComponent


def _invoke(operation: Operation, api_key: Any, timeout: float) -> Callable[..., dict]:
    def invoke(**arguments: Any) -> dict:
        return query(operation.name, arguments, api_key, timeout)

    invoke.__name__ = "fxmd_" + operation.name
    invoke.__doc__ = operation.description
    return invoke


class FXMacroDataTools(CredentialSafeComponent):
    display_name = "FXMacroData Tools"
    description = "FXMacroData tools for agents: macro, releases, FX, positioning, commodities and research."
    documentation = DOCUMENTATION
    icon = "Wrench"
    name = "FXMacroDataTools"
    inputs: ClassVar[list] = [
        SecretStrInput(name="api_key", display_name="FXMacroData API Key", required=False, advanced=True),
        IntInput(name="timeout", display_name="Request timeout (seconds)", value=30, advanced=True),
    ]
    outputs: ClassVar[list] = [Output(name="tools", display_name="Tools", method="build_tools")]

    def build_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="fxmd_" + operation.name,
                description=operation.description,
                args_schema=deepcopy(operation.input_schema),
                func=_invoke(operation, self.api_key, self.timeout),
            )
            for operation in list_operations()
        ]
