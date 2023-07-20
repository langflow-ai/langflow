import os
import ast
import zlib


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
    base_path = "/custom_component_files"

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
            raise CustomComponentPathValueError(
                f"The path needs to start with '{self.base_path}'."
            )
        file_list = []
        for root, _, files in os.walk(safe_path):
            file_list.extend(
                os.path.join(root, filename)
                for filename in files
                if filename.endswith(".py")
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

    def process_file(self, file_path):
        """
        Process a file by validating its content and
        returning the result and content/error message.
        """
        file_content = self.read_file_content(file_path)
        if file_content is None:
            return False, f"Could not read {file_path}"

        if self.is_empty_file(file_content):
            return False, "Empty file"
        elif not self.validate_code(file_content):
            return False, "Syntax error"
        elif not self.validate_build(file_content):
            return False, "Missing build function"
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

        for file_path in file_paths:
            menu_name = os.path.basename(os.path.dirname(file_path))
            filename = os.path.basename(file_path)
            validation_result, result_content = self.process_file(file_path)

            menu_result = self.find_menu(response, menu_name) or {
                "name": menu_name,
                "path": os.path.dirname(file_path),
                "components": [],
            }

            component_info = {
                "name": filename.split(".")[0],
                "file": filename,
                "code": result_content if validation_result else "",
                "error": "" if validation_result else result_content,
            }
            menu_result["components"].append(component_info)

            if menu_result not in response["menu"]:
                response["menu"].append(menu_result)

        return response
