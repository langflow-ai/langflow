import ast
from typing import Any

from typing_extensions import override


class RequiredInputsVisitor(ast.NodeVisitor):
    def __init__(self, inputs: dict[str, Any], target_method=None):
        self.inputs: dict[str, Any] = inputs
        self.required_inputs: set[str] = set()
        self.target_method = target_method
        self.current_function = None

    @override
    def visit_Attribute(self, node) -> None:
        # Check if this is an attribute access on 'self' (self.input_name)
        if (
            (self.target_method is None or self.current_function == self.target_method)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr in self.inputs
        ):
            self.required_inputs.add(node.attr)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):  # noqa: N802
        # Track which function we're currently in
        old_function = self.current_function
        self.current_function = node.name

        # Only analyze the target method if specified
        if self.target_method is None or self.target_method == node.name:
            self.generic_visit(node)

        # Restore previous function context
        self.current_function = old_function

    def visit_Name(self, node):  # noqa: N802
        # Only collect names when we're in the target method (or no target specified)
        if (self.target_method is None or self.current_function == self.target_method) and isinstance(
            node.ctx, ast.Load
        ):
            for input_name in self.inputs:
                if node.id == input_name:
                    self.required_inputs.add(input_name)
