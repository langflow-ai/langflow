import ast
from typing import Any

from typing_extensions import override


class RequiredInputsVisitor(ast.NodeVisitor):
    def __init__(self, inputs: dict[str, Any]):
        self.inputs: dict[str, Any] = inputs
        self.required_inputs: set[str] = set()

    @override
    def visit_Attribute(self, node) -> None:
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr in self.inputs
            and self.inputs[node.attr].required
        ):
            self.required_inputs.add(node.attr)
        self.generic_visit(node)
