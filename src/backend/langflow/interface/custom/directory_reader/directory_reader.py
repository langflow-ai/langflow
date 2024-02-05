import ast
import os
import zlib

from loguru import logger


class CustomComponentPathValueError(ValueError):
    pass


class StringCompressor:
    def __init__(self, input_string):
        """Initialize StringCompressor with a string to compress."""
        self.input_string = input_string

    def compress_string(self):
        """
        Compress the initial string and return the compressed data.
        """
        # Convert string to bytes
        byte_data = self.input_string.encode("utf-8")
        # Compress the bytes
        self.compressed_data = zlib.compress(byte_data)

        return self.compressed_data

    def decompress_string(self):
        """
        Decompress the compressed data and return the original string.
        """
        # Decompress the bytes
        decompressed_data = zlib.decompress(self.compressed_data)
        # Convert bytes back to string
        return decompressed_data.decode("utf-8")


class DirectoryReader:
    # Ensure the base path to read the files that contain
    # the custom components from this directory.
    base_path = ""

    def __init__(self, directory_path, compress_code_field=False):
        """
        Initialize DirectoryReader with a directory path
        and a flag indicating whether to compress the code.
        """
        self.directory_path = directory_path
        self.compress_code_field = compress_code_field

    def get_safe_path(self):
        """Check if the path is valid and return it, or None if it's not."""
        return self.directory_path if self.is_valid_path() else None

    def is_valid_path(self) -> bool:
        """Check if the directory path is valid by comparing it to the base path."""
        fullpath = os.path.normpath(os.path.join(self.directory_path))
        return fullpath.startswith(self.base_path)

    def is_empty_file(self, file_content):
        """
        Check if the file content is empty.
        """
        return len(file_content.strip()) == 0

    def filter_loaded_components(self, data: dict, with_errors: bool) -> dict:
        from langflow.interface.custom.utils import build_component

        items = [
            {
                "name": menu["name"],
                "path": menu["path"],
                "components": [
                    (*build_component(component), component)
                    for component in menu["components"]
                    if (component["error"] if with_errors else not component["error"])
                ],
            }
            for menu in data["menu"]
        ]
        filtered = [menu for menu in items if menu["components"]]
        logger.debug(f'Filtered components {"with errors" if with_errors else ""}: {len(filtered)}')
        return {"menu": filtered}

    def validate_code(self, file_content):
        """
        Validate the Python code by trying to parse it with ast.parse.
        """
        try:
            ast.parse(file_content)
            return True
        except SyntaxError:
            return False

    def validate_build(self, file_content):
        """
        Check if the file content contains a function named 'build'.
        """
        return "def build" in file_content

    def read_file_content(self, file_path):
        """
        Read and return the content of a file.
        """
        if not os.path.isfile(file_path):
            return None
        with open(file_path, "r") as file:
            return file.read()

    def get_files(self):
        """
        Walk through the directory path and return a list of all .py files.
        """
        if not (safe_path := self.get_safe_path()):
            raise CustomComponentPathValueError(f"The path needs to start with '{self.base_path}'.")

        file_list = []
        for root, _, files in os.walk(safe_path):
            file_list.extend(
                os.path.join(root, filename)
                for filename in files
                if filename.endswith(".py") and not filename.startswith("__")
            )
        return file_list

    def find_menu(self, response, menu_name):
        """
        Find and return a menu by its name in the response.
        """
        return next(
            (menu for menu in response["menu"] if menu["name"] == menu_name),
            None,
        )

    def _is_type_hint_imported(self, type_hint_name: str, code: str) -> bool:
        """
        Check if a specific type hint is imported
        from the typing module in the given code.
        """
        module = ast.parse(code)

        return any(
            isinstance(node, ast.ImportFrom)
            and node.module == "typing"
            and any(alias.name == type_hint_name for alias in node.names)
            for node in ast.walk(module)
        )

    def _is_type_hint_used_in_args(self, type_hint_name: str, code: str) -> bool:
        """
        Check if a specific type hint is used in the
        function definitions within the given code.
        """
        try:
            module = ast.parse(code)

            for node in ast.walk(module):
                if isinstance(node, ast.FunctionDef):
                    for arg in node.args.args:
                        if self._is_type_hint_in_arg_annotation(arg.annotation, type_hint_name):
                            return True
        except SyntaxError:
            # Returns False if the code is not valid Python
            return False
        return False

    def _is_type_hint_in_arg_annotation(self, annotation, type_hint_name: str) -> bool:
        """
        Helper function to check if a type hint exists in an annotation.
        """
        return (
            annotation is not None
            and isinstance(annotation, ast.Subscript)
            and isinstance(annotation.value, ast.Name)
            and annotation.value.id == type_hint_name
        )

    def is_type_hint_used_but_not_imported(self, type_hint_name: str, code: str) -> bool:
        """
        Check if a type hint is used but not imported in the given code.
        """
        try:
            return self._is_type_hint_used_in_args(type_hint_name, code) and not self._is_type_hint_imported(
                type_hint_name, code
            )
        except SyntaxError:
            # Returns True if there's something wrong with the code
            # TODO : Find a better way to handle this
            return True

    def process_file(self, file_path):
        """
        Process a file by validating its content and
        returning the result and content/error message.
        """
        file_content = self.read_file_content(file_path)

        if file_content is None:
            return False, f"Could not read {file_path}"
        elif self.is_empty_file(file_content):
            return False, "Empty file"
        elif not self.validate_code(file_content):
            return False, "Syntax error"
        elif not self.validate_build(file_content):
            return False, "Missing build function"
        elif self._is_type_hint_used_in_args("Optional", file_content) and not self._is_type_hint_imported(
            "Optional", file_content
        ):
            return (
                False,
                "Type hint 'Optional' is used but not imported in the code.",
            )
        else:
            if self.compress_code_field:
                file_content = str(StringCompressor(file_content).compress_string())
            return True, file_content

    def build_component_menu_list(self, file_paths):
        """
        Build a list of menus with their components
        from the .py files in the directory.
        """
        response = {"menu": []}
        logger.debug("-------------------- Building component menu list --------------------")

        for file_path in file_paths:
            menu_name = os.path.basename(os.path.dirname(file_path))
            logger.debug(f"Menu name: {menu_name}")
            filename = os.path.basename(file_path)
            validation_result, result_content = self.process_file(file_path)
            logger.debug(f"Validation result: {validation_result}")

            menu_result = self.find_menu(response, menu_name) or {
                "name": menu_name,
                "path": os.path.dirname(file_path),
                "components": [],
            }
            component_name = filename.split(".")[0]
            # This is the name of the file which will be displayed in the UI
            # We need to change it from snake_case to CamelCase

            # first check if it's already CamelCase
            if "_" in component_name:
                component_name_camelcase = " ".join(word.title() for word in component_name.split("_"))
            else:
                component_name_camelcase = component_name

            component_info = {
                "name": "CustomComponent",
                "output_types": [component_name_camelcase],
                "file": filename,
                "code": result_content if validation_result else "",
                "error": "" if validation_result else result_content,
            }
            menu_result["components"].append(component_info)

            logger.debug(f"Component info: {component_info}")
            if menu_result not in response["menu"]:
                response["menu"].append(menu_result)
        logger.debug("-------------------- Component menu list built --------------------")
        return response
