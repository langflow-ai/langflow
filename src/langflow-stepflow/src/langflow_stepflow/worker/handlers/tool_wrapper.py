"""Input handler for tool wrapper deserialization.

Converts serialized tool wrapper dicts into callable LangChain StructuredTool
objects whose invocation executes the wrapped Langflow component.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

from .base import InputHandler


def _execute_calculator_tool(expression: str) -> str:
    """Execute calculator tool by evaluating the mathematical expression."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_expr(tree.body)
        formatted_result = f"{float(result):.6f}".rstrip("0").rstrip(".")
        return formatted_result
    except Exception as e:
        return f"Calculator error: {str(e)}"


def _eval_expr(node: ast.AST) -> float:
    """Evaluate an AST node recursively (from CalculatorComponent)."""
    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }

    if isinstance(node, ast.Constant):
        if isinstance(node.value, int | float):
            return float(node.value)
        raise TypeError(f"Unsupported constant type: {type(node.value).__name__}")

    if isinstance(node, ast.Num):  # For backwards compatibility
        if isinstance(node.n, int | float):
            return float(node.n)
        raise TypeError(f"Unsupported number type: {type(node.n).__name__}")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in OPERATORS:
            raise TypeError(f"Unsupported binary operator: {op_type.__name__}")

        left = _eval_expr(node.left)
        right = _eval_expr(node.right)
        result = OPERATORS[op_type](left, right)
        return float(result)

    raise TypeError(f"Unsupported operation or expression type: {type(node).__name__}")


def _build_blob_data(component_code: dict[str, Any], component_type: str) -> dict[str, Any]:
    """Reshape a raw component definition into the executor's enhanced blob shape.

    ``component_tool`` stores the raw component node (``node["data"]["node"]``) as
    the tool blob: the Python source lives under ``template.code.value`` and the
    declared outputs under ``outputs``. ``CustomCodeExecutor._compile_component``
    instead expects ``code`` and the ``template`` (sans code) at the top level, so
    reshape here, mirroring ``NodeProcessor._prepare_udf_blob``. The tool runs the
    component's first declared output.
    """
    template = component_code.get("template", {})
    code = template.get("code", {}).get("value", "")
    outputs = component_code.get("outputs", [])
    selected_output = outputs[0].get("name") if outputs else None
    prepared_template = {name: cfg for name, cfg in template.items() if name != "code"}
    return {
        "code": code,
        "template": prepared_template,
        "component_type": component_type,
        "outputs": outputs,
        "selected_output": selected_output,
        "base_classes": component_code.get("base_classes", []),
        "display_name": component_code.get("display_name", component_type),
        "description": component_code.get("description", ""),
        "documentation": component_code.get("documentation", ""),
        "metadata": component_code.get("metadata", {}),
        "field_order": component_code.get("field_order", []),
        "icon": component_code.get("icon", ""),
    }


def _build_input_schema(tool_input_schema: dict[str, Any]) -> Any:
    """Build the StructuredTool args schema from the tool's input schema."""
    from pydantic import BaseModel, create_model

    properties = tool_input_schema.get("properties", {})
    field_definitions: dict[str, tuple[type, Any]] = {}
    for field_name, field_def in properties.items():
        field_definitions[field_name] = (str, field_def.get("default", ""))

    if field_definitions:
        return create_model("ToolInputSchema", **field_definitions)  # type: ignore[call-overload]

    class EmptySchema(BaseModel):
        pass

    return EmptySchema


async def _create_tool_from_wrapper(tool_wrapper: dict[str, Any], context: Any = None) -> Any:
    """Create a LangChain StructuredTool from a tool wrapper.

    The returned tool executes the wrapped Langflow component on invocation. The
    component is compiled once here, where the Stepflow ``context`` is available to
    fetch its code blob, then executed without context on each call, matching the
    custom-code executor's pre-compile-then-execute design.
    """
    try:
        from langchain_core.tools import StructuredTool

        tool_metadata = tool_wrapper.get("tool_metadata", {})
        static_inputs = tool_wrapper.get("static_inputs", {})
        component_type = tool_wrapper.get("component_type", "unknown")
        session_id = tool_wrapper.get("session_id", "default_session")

        input_schema = _build_input_schema(tool_wrapper.get("tool_input_schema", {}))

        # Calculator fast-path: the CalculatorComponent's expression evaluator is
        # pure and self-contained, so run it directly without compiling a component.
        if tool_metadata.get("name") == "evaluate_expression":

            def calculator_func(**kwargs) -> dict[str, Any]:
                return {"result": _execute_calculator_tool(kwargs.get("expression", ""))}

            return StructuredTool.from_function(
                func=calculator_func,
                name=tool_metadata.get("name", "unknown_tool"),
                description=tool_metadata.get("description", ""),
                args_schema=input_schema,
            )

        component_code = tool_wrapper.get("component_code")
        code_blob_id = tool_wrapper.get("code_blob_id")
        if component_code is None and code_blob_id is None:
            raise ValueError("Tool wrapper missing both component_code and code_blob_id")

        # Resolve the raw component definition: component_tool stores it as a blob
        # and references it by id; an inline component_code dict is also accepted.
        if code_blob_id is not None:
            if context is None:
                raise ValueError("code_blob_id requires a Stepflow context to fetch the component blob")
            raw_component = await context.get_blob(code_blob_id)
        else:
            raw_component = component_code
        if not isinstance(raw_component, dict):
            raise TypeError(f"Component code must be a component definition dict, got {type(raw_component).__name__}")

        # Imported lazily: custom_code_executor imports this handler, so a top-level
        # import would be circular.
        from ..custom_code_executor import CustomCodeExecutor

        executor = CustomCodeExecutor()
        blob_data = _build_blob_data(raw_component, component_type)
        compiled_component = await executor._compile_component(blob_data, code_blob_id)

        async def tool_func(**kwargs) -> Any:
            """Execute the wrapped component with the tool's merged inputs."""
            try:
                runtime_inputs = {**static_inputs, **kwargs, "session_id": session_id}
                return await executor._execute_compiled_component(compiled_component, runtime_inputs)
            except Exception as e:  # noqa: BLE001 - surface a tool-shaped error to the agent
                return {"error": f"Tool execution failed: {str(e)}", "component_type": component_type}

        return StructuredTool.from_function(
            coroutine=tool_func,
            name=tool_metadata.get("name", "unknown_tool"),
            description=tool_metadata.get("description", ""),
            args_schema=input_schema,
        )

    except Exception as e:  # noqa: BLE001 - any wrapper-build failure degrades to a failed tool

        class FailedToolWrapper:
            def __init__(self, tool_wrapper, error):
                self.tool_wrapper = tool_wrapper
                self.error = error
                self.name = tool_wrapper.get("tool_metadata", {}).get("name", "failed_tool")

            def invoke(self, inputs):
                return {"error": f"Tool creation failed: {self.error}"}

        return FailedToolWrapper(tool_wrapper, str(e))


class ToolWrapperInputHandler(InputHandler):
    """Deserialize tool wrapper dicts into callable StructuredTool objects.

    Matches dicts with ``__tool_wrapper__`` key and converts them to
    LangChain StructuredTool instances.
    """

    def matches(self, *, template_field: dict[str, Any], value: Any) -> bool:
        if isinstance(value, dict) and value.get("__tool_wrapper__"):
            return True
        if isinstance(value, list):
            return any(isinstance(item, dict) and item.get("__tool_wrapper__") for item in value)
        return False

    async def prepare(self, fields: dict[str, tuple[Any, dict[str, Any]]], context: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for key, (value, _template_field) in fields.items():
            if isinstance(value, dict) and value.get("__tool_wrapper__"):
                result[key] = await _create_tool_from_wrapper(value, context)
            elif isinstance(value, list):
                resolved: list[Any] = []
                for item in value:
                    if isinstance(item, dict) and item.get("__tool_wrapper__"):
                        resolved.append(await _create_tool_from_wrapper(item, context))
                    else:
                        resolved.append(item)
                result[key] = resolved

        return result
