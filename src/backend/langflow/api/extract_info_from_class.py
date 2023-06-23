import ast


class ClassCodeExtractor:
    def __init__(self, code):
        self.code = code
        self.data = {
            "imports": [],
            "class": {
                "inherited_classes": "",
                "name": "",
                "init": ""
            },
            "functions": []
        }

    def _handle_import(self, node):
        for alias in node.names:
            module_name = getattr(node, 'module', None)
            self.data['imports'].append(
                f"{module_name}.{alias.name}" if module_name else alias.name)

    def _handle_class(self, node):
        self.data['class'].update({
            'name': node.name,
            'inherited_classes': [ast.unparse(base) for base in node.bases]
        })

        for inner_node in node.body:
            if isinstance(inner_node, ast.FunctionDef):
                self._handle_function(inner_node)

    def _handle_function(self, node):
        function_name = node.name
        function_args_str = ast.unparse(node.args)
        function_args = function_args_str.split(
            ", ") if function_args_str else []

        return_type = ast.unparse(node.returns) if node.returns else "None"

        function_data = {
            "name": function_name,
            "arguments": function_args,
            "return_type": return_type
        }

        if function_name == "__init__":
            self.data['class']['init'] = function_args_str.split(
                ", ") if function_args_str else []
        else:
            self.data["functions"].append(function_data)

    def extract_class_info(self):
        module = ast.parse(self.code)

        for node in module.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._handle_import(node)
            elif isinstance(node, ast.ClassDef):
                self._handle_class(node)

        return self.data


def is_valid_class_template(code: dict) -> bool:
    class_name_ok = code["class"]["name"] == "PythonFunction"
    function_run_exists = len(
        [f for f in code["functions"] if f["name"] == "run"]) == 1

    return (class_name_ok and function_run_exists)
