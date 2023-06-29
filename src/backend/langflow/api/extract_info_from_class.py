import ast


class ClassCodeExtractor:
    def __init__(self, code):
        self.code = code
        self.function_entrypoint_name = "build"
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

    def transform_list(self, input_list):
        output_list = []
        for item in input_list:
            # Split each item on ':' to separate variable name and type
            split_item = item.split(':')

            # If there is a type, strip any leading/trailing spaces from it
            if len(split_item) > 1:
                split_item[1] = split_item[1].strip()
            # If there isn't a type, append None
            else:
                split_item.append(None)
            output_list.append(split_item)

        return output_list

    def extract_class_info(self):
        module = ast.parse(self.code)

        for node in module.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._handle_import(node)
            elif isinstance(node, ast.ClassDef):
                self._handle_class(node)

        return self.data

    def get_entrypoint_function_args_and_return_type(self):
        data = self.extract_class_info()
        functions = data.get("functions", [])

        build_function = next(
            (f for f in functions if f["name"] ==
             self.function_entrypoint_name), None
        )

        if build_function:
            function_args = build_function.get("arguments", None)
            function_args = self.transform_list(function_args)

            return_type = build_function.get("return_type", None)
        else:
            function_args = None
            return_type = None

        return function_args, return_type


def is_valid_class_template(code: dict):
    extractor = ClassCodeExtractor(code)
    return_type_valid_list = ["ConversationChain", "Tool"]

    class_name = code.get("class", {}).get("name", None)
    if not class_name:  # this will also check for None, empty string, etc.
        return False

    functions = code.get("functions", [])
    # use a generator and next to find if a function matching the criteria exists
    build_function = next(
        (f for f in functions if f["name"] ==
         extractor.function_entrypoint_name), None
    )

    if not build_function:
        return False

    # Check if the return type of the build function is valid
    if build_function.get("return_type") not in return_type_valid_list:
        return False

    return True
