import ast
import traceback

from typing import Dict, Any, Union
from fastapi import HTTPException


class CodeSyntaxError(HTTPException):
    pass


class CodeParser:
    """
    A parser for Python source code, extracting code details.
    """

    def __init__(self, code: str) -> None:
        """
        Initializes the parser with the provided code.
        """
        self.code = code
        self.data: Dict[str, Any] = {
            "imports": [],
            "functions": [],
            "classes": [],
            "global_vars": [],
        }
        self.handlers = {
            ast.Import: self.parse_imports,
            ast.ImportFrom: self.parse_imports,
            ast.FunctionDef: self.parse_functions,
            ast.ClassDef: self.parse_classes,
            ast.Assign: self.parse_global_vars,
        }

    def __get_tree(self):
        """
        Parses the provided code to validate its syntax.
        It tries to parse the code into an abstract syntax tree (AST).
        """
        try:
            tree = ast.parse(self.code)
        except SyntaxError as err:
            raise CodeSyntaxError(
                status_code=400,
                detail={"error": err.msg, "traceback": traceback.format_exc()},
            ) from err

        return tree

    def parse_node(self, node: ast.AST) -> None:
        """
        Parses an AST node and updates the data
        dictionary with the relevant information.
        """
        if handler := self.handlers.get(type(node)):
            handler(node)

    def parse_imports(self, node: Union[ast.Import, ast.ImportFrom]) -> None:
        """
        Extracts "imports" from the code.
        """
        if isinstance(node, ast.Import):
            module = node.names[0].name
            self.data["imports"].append(module)
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            names = [alias.name for alias in node.names]
            self.data["imports"].append((module, names))

    def parse_functions(self, node: ast.FunctionDef) -> None:
        """
        Extracts "functions" from the code.
        """
        self.data["functions"].append(self.parse_callable_details(node))

    def parse_arg(self, arg, default):
        """
        Parses an argument and its default value.
        """
        arg_dict = {"name": arg.arg, "default": default}
        if arg.annotation:
            arg_dict["type"] = ast.unparse(arg.annotation)
        return arg_dict

    def parse_callable_details(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """
        Extracts details from a single function or method node.
        """
        func = {
            "name": node.name,
            "doc": ast.get_docstring(node),
            "args": [],
            "body": [],
            "return_type": ast.unparse(node.returns) if node.returns else None,
        }

        # Handle positional arguments with default values
        defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + [
            ast.unparse(default) for default in node.args.defaults
        ]

        for arg, default in zip(node.args.args, defaults):
            func["args"].append(self.parse_arg(arg, default))

        # Handle *args
        if node.args.vararg:
            func["args"].append(self.parse_arg(node.args.vararg, None))

        # Handle keyword-only arguments with default values
        kw_defaults = [None] * (
            len(node.args.kwonlyargs) - len(node.args.kw_defaults)
        ) + [
            ast.unparse(default) if default else None
            for default in node.args.kw_defaults
        ]

        for arg, default in zip(node.args.kwonlyargs, kw_defaults):
            func["args"].append(self.parse_arg(arg, default))

        # Handle **kwargs
        if node.args.kwarg:
            func["args"].append(self.parse_arg(node.args.kwarg, None))

        for line in node.body:
            func["body"].append(ast.unparse(line))
        return func

    def parse_classes(self, node: ast.ClassDef) -> None:
        """
        Extracts "classes" from the code, including
        inheritance and init methods.
        """
        class_dict = {
            "name": node.name,
            "doc": ast.get_docstring(node),
            "bases": [ast.unparse(base) for base in node.bases],
            "attributes": [],
            "methods": [],
        }

        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign):
                attr = {"name": stmt.target.id, "type": ast.unparse(stmt.annotation)}
                class_dict["attributes"].append(attr)
            elif isinstance(stmt, ast.Assign):
                attr = {"name": stmt.targets[0].id, "value": ast.unparse(stmt.value)}
                class_dict["attributes"].append(attr)
            elif isinstance(stmt, ast.FunctionDef):
                method = self.parse_callable_details(stmt)
                if stmt.name == "__init__":
                    class_dict["init"] = method
                else:
                    class_dict["methods"].append(method)

        self.data["classes"].append(class_dict)

    def parse_global_vars(self, node: ast.Assign) -> None:
        """
        Extracts global variables from the code.
        """
        global_var = {
            "targets": [
                t.id if hasattr(t, "id") else ast.dump(t) for t in node.targets
            ],
            "value": ast.unparse(node.value),
        }
        self.data["global_vars"].append(global_var)

    def parse_code(self) -> Dict[str, Any]:
        """
        Runs all parsing operations and returns the resulting data.
        """
        tree = self.__get_tree()

        for node in ast.walk(tree):
            self.parse_node(node)
        return self.data
