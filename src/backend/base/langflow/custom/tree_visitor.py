import ast

from typing_extensions import override


class RequiredInputsVisitor(ast.NodeVisitor):
    def __init__(self, inputs):
        self.inputs = inputs
        self.required_inputs = set()

    @override
    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "self" and node.attr in self.inputs:
            self.required_inputs.add(node.attr)
        self.generic_visit(node)
