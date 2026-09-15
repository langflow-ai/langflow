"""Run a saved Figranium browser-automation task through the HTTP API."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from lfx.custom.custom_component.component import Component
from lfx.io import DictInput, DropdownInput, IntInput, Output, SecretStrInput, StrInput
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
        StrInput(name="base_url", display_name="Figranium URL", info=BASE_URL_INFO, required=True),
        SecretStrInput(name="api_key", display_name="API Key", info=API_KEY_INFO, required=True, password=True),
        DropdownInput(
            name="task_id",
            display_name="Task",
            info="Choose a saved Figranium task. Use the refresh button after changing the URL or API key.",
            options=[],
            required=True,
            refresh_button=True,
        ),
        DictInput(
            name="task_variables",
            display_name="Variables",
            info="Optional key-value dictionary passed to the task at runtime.",
            value={},
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

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):
        if field_name == "task_id":
            client = FigraniumAPIClient(self.base_url, self.api_key, timeout=self._timeout_seconds())
            response = client.get("/api/tasks/list")
            tasks = response.get("tasks", []) if isinstance(response, dict) else []
            build_config["task_id"]["options"] = [
                {"name": str(task.get("name") or task.get("id")), "value": str(task.get("id"))}
                for task in tasks
                if isinstance(task, dict) and task.get("id")
            ]
        return build_config

    def execute_task(self) -> Data:
        """POST the task's variables to Figranium and return the execution result."""
        task_id = str(self.task_id or "").strip()
        if not task_id:
            msg = "Figranium task is required."
            raise ValueError(msg)
        variables = self.task_variables or {}
        if not isinstance(variables, dict):
            msg = "Variables must be a dictionary."
            raise TypeError(msg)
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
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {"result": value}
