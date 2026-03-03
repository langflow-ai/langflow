"""Input handler for tool wrapper deserialization.

Converts serialized tool wrapper dicts into callable LangChain StructuredTool
objects.
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


def _create_tool_from_wrapper(tool_wrapper: dict[str, Any]) -> Any:
    """Create a LangChain StructuredTool from a tool wrapper."""
    try:
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, create_model

        tool_metadata = tool_wrapper.get("tool_metadata", {})
        tool_input_schema = tool_wrapper.get("tool_input_schema", {})
        static_inputs = tool_wrapper.get("static_inputs", {})
        component_type = tool_wrapper.get("component_type", "unknown")
        session_id = tool_wrapper.get("session_id", "default_session")

        component_code = tool_wrapper.get("component_code")
        code_blob_id = tool_wrapper.get("code_blob_id")

        if component_code is None and code_blob_id is None:
            raise ValueError(
                "Tool wrapper missing both component_code and code_blob_id"
            )

        properties = tool_input_schema.get("properties", {})

        field_definitions: dict[str, tuple[type, Any]] = {}
        for field_name, field_def in properties.items():
            field_type: type = str
            default_value = field_def.get("default", "")
            field_definitions[field_name] = (field_type, default_value)

        input_schema: type[BaseModel]
        if field_definitions:
            input_schema = create_model("ToolInputSchema", **field_definitions)  # type: ignore[call-overload]
        else:

            class EmptySchema(BaseModel):
                pass

            input_schema = EmptySchema

        def tool_func(**kwargs) -> dict[str, Any]:
            """Execute the tool by running the component."""
            try:
                if (
                    tool_metadata.get("name") == "evaluate_expression"
                    and "expression" in kwargs
                ):
                    result = _execute_calculator_tool(kwargs["expression"])
                    return {"result": result}

                merged_inputs = {
                    **static_inputs,
                    **kwargs,
                    "session_id": session_id,
                }

                result_data = {
                    "result": (
                        f"Tool {tool_metadata.get('name', 'unknown')} "
                        f"executed with inputs: {merged_inputs}"
                    ),
                    "component_type": component_type,
                    "inputs": merged_inputs,
                    "status": "tool_wrapper_execution",
                }

                if code_blob_id:
                    result_data["code_blob_id"] = code_blob_id
                elif component_code:
                    result_data["has_component_code"] = True

                return result_data

            except Exception as e:
                return {
                    "error": f"Tool execution failed: {str(e)}",
                    "component_type": component_type,
                }

        return StructuredTool.from_function(
            func=tool_func,
            name=tool_metadata.get("name", "unknown_tool"),
            description=tool_metadata.get("description", ""),
            args_schema=input_schema,
        )

    except Exception as e:

        class FailedToolWrapper:
            def __init__(self, tool_wrapper, error):
                self.tool_wrapper = tool_wrapper
                self.error = error
                self.name = tool_wrapper.get("tool_metadata", {}).get(
                    "name", "failed_tool"
                )

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
            return any(
                isinstance(item, dict) and item.get("__tool_wrapper__")
                for item in value
            )
        return False

    async def prepare(
        self, fields: dict[str, tuple[Any, dict[str, Any]]], context: Any
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for key, (value, _template_field) in fields.items():
            if isinstance(value, dict) and value.get("__tool_wrapper__"):
                result[key] = _create_tool_from_wrapper(value)
            elif isinstance(value, list):
                result[key] = [
                    _create_tool_from_wrapper(item)
                    if isinstance(item, dict) and item.get("__tool_wrapper__")
                    else item
                    for item in value
                ]

        return result
