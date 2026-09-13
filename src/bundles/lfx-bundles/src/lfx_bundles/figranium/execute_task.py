from __future__ import annotations

import json
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from .base import FigraniumAPIClient, secret_value


class FigraniumExecuteTaskComponent(Component):
    display_name = "Execute Figranium Task"
    description = "Run a saved Figranium browser automation task through the HTTP API."
    documentation = "https://docs.figranium.dev"
    icon = "Workflow"
    name = "FigraniumExecuteTask"

    inputs = [
        StrInput(
            name="base_url",
            display_name="Figranium URL",
            info="Base URL of your Figranium instance, for example https://figranium.example.com.",
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Figranium API key sent as the x-api-key header.",
            required=True,
            password=True,
        ),
        StrInput(
            name="task_id",
            display_name="Task ID",
            info="ID of the saved Figranium task to execute.",
            required=True,
        ),
        MultilineInput(
            name="variables",
            display_name="Variables",
            info='Optional task variables as JSON, for example {"query":"Langflow"}.',
            value="{}",
        ),
    ]

    outputs = [Output(display_name="Result", name="result", type_=Data, method="execute_task")]

    def execute_task(self) -> Data:
        variables = self._parse_variables(self.variables)
        client = FigraniumAPIClient(self.base_url, secret_value(self.api_key))
        result = client.request("POST", f"/tasks/{self.task_id}/api", json={"variables": variables})
        data = Data(data=self._as_dict(result))
        self.status = data
        return data

    @staticmethod
    def _parse_variables(value: str | dict[str, Any] | None) -> dict[str, Any]:
        if value in (None, ""):
            return {}
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            msg = f"Variables must be valid JSON: {exc.msg}"
            raise ValueError(msg) from exc
        if not isinstance(parsed, dict):
            msg = "Variables must be a JSON object."
            raise TypeError(msg)
        return parsed

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {"result": value}
