"""Call any API in the APIVerve catalog by id."""

from __future__ import annotations

import json
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from lfx_bundles.apiverve.base import API_KEY_INFO, DEFAULT_TIMEOUT_SECONDS, DOCUMENTATION_URL, run, secret_value


class ApiverveRunApiComponent(Component):
    """Run one APIVerve API and return its response data."""

    display_name = "APIVerve Run API"
    description = (
        "Call any of about 380 APIVerve APIs by id: validate emails and phone numbers, look up IPs, "
        "DNS and SSL certificates, get exchange rates, decode VINs, and more."
    )
    documentation = DOCUMENTATION_URL
    icon = "APIVerve"
    name = "ApiverveRunApi"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info=API_KEY_INFO,
            required=True,
            password=True,
        ),
        MessageTextInput(
            name="api_id",
            display_name="API",
            info=(
                "The APIVerve API id, for example emailvalidator, iplookup or vindecoder. "
                "Use APIVerve Find APIs to look one up."
            ),
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="api_parameters",
            display_name="Parameters",
            info='The API parameters as a JSON object, for example {"email": "jane@example.com"}.',
            value="{}",
            tool_mode=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for APIVerve to respond.",
            value=int(DEFAULT_TIMEOUT_SECONDS),
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Result", name="result", type_=Data, method="run_api")]

    def run_api(self) -> Data:
        """Call the API and return the ``data`` object of its response."""
        result = run(
            secret_value(self.api_key),
            str(self.api_id or ""),
            self._parse_parameters(self.api_parameters),
            timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
        )
        data = Data(data=result if isinstance(result, dict) else {"result": result})
        self.status = data
        return data

    @staticmethod
    def _parse_parameters(value: str | dict[str, Any] | None) -> dict[str, Any]:
        if value in (None, ""):
            return {}
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            msg = f"Parameters must be valid JSON: {exc.msg}"
            raise ValueError(msg) from exc
        if not isinstance(parsed, dict):
            msg = "Parameters must be a JSON object."
            raise TypeError(msg)
        return parsed
