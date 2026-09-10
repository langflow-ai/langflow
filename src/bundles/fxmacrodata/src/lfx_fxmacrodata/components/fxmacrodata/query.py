"""Tabular FXMacroData data for visual Langflow pipelines."""

from typing import ClassVar

from fxmacrodata_public import list_operations
from lfx.io import DictInput, DropdownInput, IntInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message

from lfx_fxmacrodata.client import DOCUMENTATION, query
from lfx_fxmacrodata.component import CredentialSafeComponent


class FXMacroDataQuery(CredentialSafeComponent):
    display_name = "FXMacroData Table"
    description = "Official macro, calendar and market data as a DataFrame with the original response."
    documentation = DOCUMENTATION
    icon = "Table"
    name = "FXMacroDataQuery"
    inputs: ClassVar[list] = [
        DropdownInput(
            name="operation",
            display_name="Operation",
            value="indicator_history",
            options=[operation.name for operation in list_operations()],
            real_time_refresh=True,
        ),
        DictInput(
            name="arguments",
            display_name="Parameters",
            value={"currency": "USD", "indicator": "inflation"},
            info="Use the exact parameter names from the Parameter schema output. USD examples need no API key.",
        ),
        SecretStrInput(name="api_key", display_name="FXMacroData API Key", required=False, advanced=True),
        IntInput(name="timeout", display_name="Request timeout (seconds)", value=30, advanced=True),
    ]
    outputs: ClassVar[list] = [
        Output(name="table", display_name="DataFrame", method="build_table"),
        Output(name="response", display_name="Original response", method="build_response"),
        Output(name="parameter_schema", display_name="Parameter schema", method="build_schema"),
        Output(name="provider", display_name="FXMacroData", method="build_provider"),
    ]

    def _pre_run_setup(self) -> None:
        self._response_cache = None

    def _result(self) -> dict:
        cache_key = (self.operation, repr(self.arguments), self.timeout)
        cached = getattr(self, "_response_cache", None)
        if cached is not None and cached[0] == cache_key:
            return cached[1]
        result = query(self.operation, self.arguments, self.api_key, self.timeout)
        if result["error"]:
            self.status = result["error"]
            raise ValueError(result["error"])
        self.status = f"{len(result['records'])} records"
        self._response_cache = (cache_key, result)
        return result

    def build_table(self) -> DataFrame:
        result = self._result()
        frame = DataFrame(result["records"])
        frame.attrs["fxmacrodata_response"] = result["data"]
        frame.attrs["source_url"] = result["source_url"]
        frame.attrs["provider_url"] = result["provider_url"]
        return frame

    def build_response(self) -> Data:
        return Data(data=self._result())

    def build_schema(self) -> Data:
        operation = next(item for item in list_operations() if item.name == self.operation)
        return Data(data=operation.input_schema)

    def build_provider(self) -> Message:
        from lfx_fxmacrodata.client import SITE_URL

        return Message(text=f"[Explore FXMacroData]({SITE_URL})")

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        if field_name == "operation":
            spec = next(item for item in list_operations() if item.name == field_value)
            defaults = {
                name: field["default"]
                for name, field in spec.input_schema.get("properties", {}).items()
                if "default" in field
            }
            if "currency" in spec.input_schema.get("properties", {}):
                defaults["currency"] = "USD"
            if field_value == "indicator_history":
                defaults["indicator"] = "inflation"
            build_config["arguments"]["value"] = defaults
            build_config["arguments"]["info"] = spec.description
        return build_config
