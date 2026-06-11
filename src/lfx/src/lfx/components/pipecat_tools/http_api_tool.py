"""HTTP API tool component.

Lets a voice agent call any HTTP(S) endpoint. The LLM provides the request
``body`` (and optionally ``query``) as JSON-compatible dicts; the component
forwards them with the configured method / URL / headers and returns the
response status + parsed body to the LLM.
"""

import json
from typing import Any

from lfx.base.pipecat.tool import PipecatToolComponent
from lfx.field_typing.voice_types import PipecatToolHandler
from lfx.io import DropdownInput, IntInput, MultilineInput, StrInput

DEFAULT_TIMEOUT_SECS = 15


class HTTPAPIToolComponent(PipecatToolComponent):
    display_name = "HTTP API Tool"
    description = "Voice tool that issues an HTTP request and returns the response to the LLM."
    icon = "Globe"
    name = "HTTPAPITool"

    inputs = [
        StrInput(
            name="tool_name",
            display_name="Tool Name",
            required=True,
            value="call_http_api",
        ),
        MultilineInput(
            name="tool_description",
            display_name="Description",
            required=True,
            value="Make an HTTP request to a configured backend and return the response.",
        ),
        StrInput(
            name="url",
            display_name="URL",
            required=True,
            info="Target endpoint. Supports {placeholders} substituted from `args.path_params`.",
        ),
        DropdownInput(
            name="method",
            display_name="HTTP Method",
            options=["GET", "POST", "PUT", "PATCH", "DELETE"],
            value="POST",
        ),
        MultilineInput(
            name="headers_json",
            display_name="Headers (JSON)",
            value="{}",
            info="Optional static headers dict. Authorization etc.",
            advanced=True,
        ),
        IntInput(
            name="timeout_secs",
            display_name="Timeout (seconds)",
            value=DEFAULT_TIMEOUT_SECS,
            advanced=True,
        ),
    ]

    def build_function_schema(self) -> Any:
        from pipecat.adapters.schemas.function_schema import FunctionSchema

        return FunctionSchema(
            name=self.tool_name,
            description=self.tool_description,
            properties={
                "body": {
                    "type": "object",
                    "description": "JSON body to send with the request.",
                    "additionalProperties": True,
                },
                "query": {
                    "type": "object",
                    "description": "Query-string params.",
                    "additionalProperties": True,
                },
                "path_params": {
                    "type": "object",
                    "description": "Values for {placeholders} in the URL template.",
                    "additionalProperties": {"type": "string"},
                },
            },
            required=[],
        )

    def build_handler(self) -> PipecatToolHandler:
        url_template = self.url
        method = (self.method or "POST").upper()
        timeout = float(self.timeout_secs or DEFAULT_TIMEOUT_SECS)
        try:
            headers = json.loads((self.headers_json or "{}").strip() or "{}")
        except json.JSONDecodeError as exc:
            msg = f"HTTPAPITool headers_json is invalid JSON: {exc}"
            raise ValueError(msg) from exc

        async def _handler(params: Any) -> None:  # pragma: no cover — runtime wiring
            import httpx

            args = dict(getattr(params, "arguments", {}) or {})
            body = args.get("body") or None
            query = args.get("query") or None
            path_params = args.get("path_params") or {}
            try:
                url = url_template.format(**path_params)
            except KeyError as exc:
                await params.result_callback({"error": f"missing path param: {exc}"})
                return

            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        params=query,
                        json=body if body is not None else None,
                    )
                content_type = response.headers.get("content-type", "")
                payload: Any
                if "application/json" in content_type:
                    payload = response.json()
                else:
                    payload = response.text
                await params.result_callback({
                    "status": response.status_code,
                    "ok": response.is_success,
                    "data": payload,
                })
            except Exception as exc:
                await params.result_callback({"error": f"{type(exc).__name__}: {exc}"})

        return _handler
