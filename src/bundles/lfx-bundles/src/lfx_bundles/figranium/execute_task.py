"""Run a saved Figranium browser-automation task through the HTTP API."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from lfx_bundles.figranium.base import (
    API_KEY_INFO,
    BASE_URL_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    FigraniumAPIClient,
)


class FigraniumExecuteTaskComponent(Component):
    """Execute a saved Figranium task and return its result as ``Data``."""

    display_name = "Execute Figranium Task"
    description = "Run a saved Figranium browser automation task and return its result."
    documentation = DOCUMENTATION_URL
    icon = "Figranium"
    name = "FigraniumExecuteTask"

    inputs = [
        StrInput(
            name="base_url",
            display_name="Figranium URL",
            info=BASE_URL_INFO,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info=API_KEY_INFO,
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
            name="task_variables",
            display_name="Variables",
            info='Optional task variables as a JSON object, for example {"query": "Langflow"}.',
            value="{}",
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info=(
                "How long to wait for the task to finish. Figranium runs the task synchronously and "
                "returns the result in the same response, so raise this for long browser automations."
            ),
            value=int(DEFAULT_TIMEOUT_SECONDS),
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Result", name="result", type_=Data, method="execute_task")]

    def execute_task(self) -> Data:
        """POST the task's variables to Figranium and return the execution result."""
        task_id = str(self.task_id or "").strip()
        if not task_id:
            msg = "Figranium task ID is required."
            raise ValueError(msg)
        variables = self._parse_variables(self.task_variables)
        client = FigraniumAPIClient(self.base_url, self.api_key, timeout=self._timeout_seconds())
        result = client.post(f"/api/tasks/{quote(task_id, safe='')}/api", json={"variables": variables})
        data = Data(data=self._as_dict(result))
        self.status = data
        return data

    def _timeout_seconds(self) -> float:
        raw = getattr(self, "timeout", None)
        if raw in (None, ""):
            return DEFAULT_TIMEOUT_SECONDS
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            msg = "Timeout must be a number of seconds."
            raise ValueError(msg) from exc

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
