import ast
import inspect
import traceback

from typing import Dict, Any, List, Type, Union
from fastapi import HTTPException
from langflow.interface.custom.schema import CallableCodeDetails, ClassCodeDetails


class CodeSyntaxError(HTTPException):
    pass


class CodeParser:
    """
    A parser for Python source code, extracting code details.
    """

    def __init__(self, code: Union[str, Type]) -> None:
        """
        Initializes the parser with the provided code.
        """
        if isinstance(code, type):
            if not inspect.isclass(code):
                raise ValueError("The provided code must be a class.")
            # If the code is a class, get its source code
            code = inspect.getsource(code)
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

    def parse_node(self, node: Union[ast.stmt, ast.AST]) -> None:
        """
        Parses an AST node and updates the data
        dictionary with the relevant information.
        """
        if handler := self.handlers.get(type(node)):  # type: ignore
            handler(node)  # type: ignore

    def parse_imports(self, node: Union[ast.Import, ast.ImportFrom]) -> None:
        """
        Extracts "imports" from the code.
        """
        if isinstance(node, ast.Import):
            for alias in node.names:
                self.data["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                self.data["imports"].append((node.module, alias.name))

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
        func = CallableCodeDetails(
            name=node.name,
            doc=ast.get_docstring(node),
            args=[],
            body=[],
            return_type=ast.unparse(node.returns) if node.returns else None,
        )

        func.args = self.parse_function_args(node)
        func.body = self.parse_function_body(node)

        return func.dict()

    def parse_function_args(self, node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """
        Parses the arguments of a function or method node.
        """
        args = []

        args += self.parse_positional_args(node)
        args += self.parse_varargs(node)
        args += self.parse_keyword_args(node)
        args += self.parse_kwargs(node)

        return args

    def parse_positional_args(self, node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """
        Parses the positional arguments of a function or method node.
        """
        num_args = len(node.args.args)
        num_defaults = len(node.args.defaults)
        num_missing_defaults = num_args - num_defaults
        missing_defaults = [None] * num_missing_defaults
        default_values = [
            ast.unparse(default).strip("'") if default else None
            for default in node.args.defaults
        ]
        # Now check all default values to see if there
        # are any "None" values in the middle
        default_values = [
            None if value == "None" else value for value in default_values
        ]

        defaults = missing_defaults + default_values

        args = [
            self.parse_arg(arg, default)
            for arg, default in zip(node.args.args, defaults)
        ]
        return args

    def parse_varargs(self, node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """
        Parses the *args argument of a function or method node.
        """
        args = []

        if node.args.vararg:
            args.append(self.parse_arg(node.args.vararg, None))

        return args

    def parse_keyword_args(self, node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """
        Parses the keyword-only arguments of a function or method node.
        """
        kw_defaults = [None] * (
            len(node.args.kwonlyargs) - len(node.args.kw_defaults)
        ) + [
            ast.unparse(default) if default else None
            for default in node.args.kw_defaults
        ]

        args = [
            self.parse_arg(arg, default)
            for arg, default in zip(node.args.kwonlyargs, kw_defaults)
        ]
        return args

    def parse_kwargs(self, node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """
        Parses the **kwargs argument of a function or method node.
        """
        args = []

        if node.args.kwarg:
            args.append(self.parse_arg(node.args.kwarg, None))

        return args

    def parse_function_body(self, node: ast.FunctionDef) -> List[str]:
        """
        Parses the body of a function or method node.
        """
        return [ast.unparse(line) for line in node.body]

    def parse_assign(self, stmt):
        """
        Parses an Assign statement and returns a dictionary
        with the target's name and value.
        """
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                return {"name": target.id, "value": ast.unparse(stmt.value)}

    def parse_ann_assign(self, stmt):
        """
        Parses an AnnAssign statement and returns a dictionary
        with the target's name, value, and annotation.
        """
        if isinstance(stmt.target, ast.Name):
            return {
                "name": stmt.target.id,
                "value": ast.unparse(stmt.value) if stmt.value else None,
                "annotation": ast.unparse(stmt.annotation),
            }

    def parse_function_def(self, stmt):
        """
        Parses a FunctionDef statement and returns the parsed
        method and a boolean indicating if it's an __init__ method.
        """
        method = self.parse_callable_details(stmt)
        return (method, True) if stmt.name == "__init__" else (method, False)

    def parse_classes(self, node: ast.ClassDef) -> None:
        """
        Extracts "classes" from the code, including inheritance and init methods.
        """

        class_details = ClassCodeDetails(
            name=node.name,
            doc=ast.get_docstring(node),
            bases=[ast.unparse(base) for base in node.bases],
            attributes=[],
            methods=[],
            init=None,
        )

        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                if attr := self.parse_assign(stmt):
                    class_details.attributes.append(attr)
            elif isinstance(stmt, ast.AnnAssign):
                if attr := self.parse_ann_assign(stmt):
                    class_details.attributes.append(attr)
            elif isinstance(stmt, ast.FunctionDef):
                method, is_init = self.parse_function_def(stmt)
                if is_init:
                    class_details.init = method
                else:
                    class_details.methods.append(method)

        self.data["classes"].append(class_details.dict())

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
