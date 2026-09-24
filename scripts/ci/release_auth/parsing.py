"""Parse authentication defaults without importing the application."""

import ast


def parse_auto_login_default(source: bytes) -> ast.Constant:
    """Parse the literal AUTO_LOGIN default without executing application code.

    Raises:
        SyntaxError: The source is not valid Python.
        ValueError: The settings declaration is missing, ambiguous, or nonliteral.
    """
    tree = ast.parse(source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AuthSettings"]
    if len(classes) != 1:
        msg = "Expected exactly one AuthSettings class"
        raise ValueError(msg)
    fields = [
        node
        for node in classes[0].body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "AUTO_LOGIN"
    ]
    if len(fields) != 1:
        msg = "Expected exactly one AuthSettings.AUTO_LOGIN field"
        raise ValueError(msg)
    field = fields[0].value
    if not isinstance(field, ast.Call) or not isinstance(field.func, ast.Name) or field.func.id != "Field":
        msg = "Expected AuthSettings.AUTO_LOGIN to use Field(default=<bool>)"
        raise ValueError(msg)
    defaults = [keyword.value for keyword in field.keywords if keyword.arg == "default"]
    if len(defaults) != 1 or not isinstance(defaults[0], ast.Constant) or type(defaults[0].value) is not bool:
        msg = "Expected a literal boolean default for AuthSettings.AUTO_LOGIN"
        raise ValueError(msg)
    return defaults[0]
