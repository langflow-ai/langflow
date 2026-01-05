"""AST transformer to block dangerous dunder method access."""

import ast
from typing import Any

from lfx.custom.import_isolation.config import SecurityViolationError

# Dangerous dunder methods that enable isolation escapes
# These allow access to __globals__, __subclasses__, etc. which can be used to escape
DANGEROUS_DUNDER_ATTRS: set[str] = {
    "__class__",  # Access to object's class
    "__bases__",  # Access to base classes
    "__subclasses__",  # Access to all subclasses (enables escape)
    "__mro__",  # Method resolution order (can access classes)
    "__globals__",  # Access to function/module globals (enables escape)
    "__builtins__",  # Access to builtins (we handle this separately, but block direct access)
    "__init__",  # Can access __init__.__globals__
    "__dict__",  # Can access object's dictionary
    "__getattribute__",  # Can bypass our restrictions
    "__getattr__",  # Can bypass our restrictions
}


class DunderAccessTransformer(ast.NodeTransformer):
    """AST transformer that blocks dangerous dunder method access.
    
    This prevents classic Python isolation escapes like:
    ().__class__.__bases__[0].__subclasses__()[XX].__init__.__globals__['os']
    
    The transformer rewrites dangerous attribute access (like obj.__class__) into
    calls to getattr() which we can intercept and block.
    """

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        # Check if this is accessing a dangerous dunder attribute
        if isinstance(node.attr, str) and node.attr in DANGEROUS_DUNDER_ATTRS:
            # Rewrite obj.__class__ to getattr(obj, '__class__') which we can intercept
            # This converts direct attribute access to a function call we can block
            return ast.Call(
                func=ast.Name(id="getattr", ctx=ast.Load()),
                args=[
                    self.visit(node.value),  # Visit the object being accessed
                    ast.Constant(value=node.attr),  # The attribute name
                ],
                keywords=[],
            )
        # Continue visiting child nodes
        return self.generic_visit(node)

