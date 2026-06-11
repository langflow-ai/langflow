"""Generic voice tool component.

Users supply:
  - tool_name (what the LLM sees)
  - description (what the LLM reads to decide when to call it)
  - parameters_json_schema (JSON object describing the arguments)
  - handler_code (Python source defining ``async def handle(args: dict) -> dict``)

The component compiles the handler code, wraps it into the Pipecat
``async def(params: FunctionCallParams)`` shape (which must call
``await params.result_callback(result)``), and packs both into a
``PipecatTool`` tuple via the inherited ``build_tool()`` method.

This is the direct parallel of LangChain's generic ``Tool`` — one base class
anyone can use without writing a new Python file per tool.
"""

import ast
import asyncio
import json
import textwrap
from typing import Any

from lfx.base.pipecat.tool import PipecatToolComponent
from lfx.field_typing.voice_types import PipecatToolHandler
from lfx.io import CodeInput, MultilineInput, StrInput

HANDLER_TEMPLATE_HINT = (
    "Define an async function named `handle` that takes a dict of arguments "
    "and returns a dict.\n\n"
    "Example:\n"
    "    async def handle(args: dict) -> dict:\n"
    "        location = args.get('location', '')\n"
    "        return {'location': location, 'temp': 21, 'unit': 'C'}\n"
)


def _compile_handler_source(source: str) -> Any:
    """Compile user-supplied source and return the top-level ``handle`` coroutine."""
    source = textwrap.dedent(source or "").strip()
    if not source:
        msg = "VoiceTool handler_code is empty."
        raise ValueError(msg)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        msg = f"VoiceTool handler_code has a syntax error: {exc}"
        raise ValueError(msg) from exc

    has_handle = any(
        isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "handle"
        for node in tree.body
    )
    if not has_handle:
        msg = "VoiceTool handler_code must define `async def handle(args: dict) -> dict`."
        raise ValueError(msg)

    namespace: dict[str, Any] = {}
    compiled = compile(tree, filename="<voice_tool_handler>", mode="exec")
    exec(compiled, namespace)  # noqa: S102 — handler authors are trusted (same level of trust as Langflow custom components).
    handle = namespace.get("handle")
    if not callable(handle):
        msg = "VoiceTool handler_code defined `handle` but it is not callable."
        raise ValueError(msg)
    return handle


class VoiceToolComponent(PipecatToolComponent):
    display_name = "Voice Tool"
    description = "Generic Pipecat tool defined by a JSON-schema + Python handler."
    icon = "Wrench"
    name = "VoiceTool"

    inputs = [
        StrInput(
            name="tool_name",
            display_name="Tool Name",
            required=True,
            info="Identifier the LLM uses to call this tool. Must be a valid identifier.",
        ),
        MultilineInput(
            name="tool_description",
            display_name="Description",
            required=True,
            info="What the tool does. The LLM reads this to decide when to call it.",
        ),
        CodeInput(
            name="parameters_json_schema",
            display_name="Parameters (JSON Schema)",
            value='{\n  "type": "object",\n  "properties": {},\n  "required": []\n}',
            info="OpenAI-style JSON schema describing the arguments object.",
        ),
        CodeInput(
            name="handler_code",
            display_name="Handler (Python)",
            value="async def handle(args: dict) -> dict:\n    return {'ok': True}\n",
            info=HANDLER_TEMPLATE_HINT,
        ),
    ]

    def build_function_schema(self) -> Any:
        from pipecat.adapters.schemas.function_schema import FunctionSchema

        raw = (self.parameters_json_schema or "").strip() or "{}"
        try:
            schema_dict = json.loads(raw)
        except json.JSONDecodeError as exc:
            msg = f"VoiceTool parameters_json_schema is not valid JSON: {exc}"
            raise ValueError(msg) from exc

        properties = schema_dict.get("properties", {})
        required = schema_dict.get("required", []) or []
        return FunctionSchema(
            name=self.tool_name,
            description=self.tool_description or "",
            properties=properties,
            required=required,
        )

    def build_handler(self) -> PipecatToolHandler:
        user_handle = _compile_handler_source(self.handler_code)

        async def _pipecat_handler(params: Any) -> None:  # pragma: no cover — runtime wiring
            args = dict(getattr(params, "arguments", {}) or {})
            result = user_handle(args)
            if asyncio.iscoroutine(result):
                result = await result
            if not isinstance(result, dict):
                result = {"result": result}
            await params.result_callback(result)

        return _pipecat_handler
