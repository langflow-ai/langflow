import ast
import asyncio
import time
import zlib
from pathlib import Path

import anyio
from aiofile import async_open
from loguru import logger

from langflow.custom.custom_component.component import Component

MAX_DEPTH = 2


class CustomComponentPathValueError(ValueError):
    pass


class StringCompressor:
    def __init__(self, input_string) -> None:
        """Initialize StringCompressor with a string to compress."""
        self.input_string = input_string

    def compress_string(self):
        """Compress the initial string and return the compressed data."""
        # Convert string to bytes
        byte_data = self.input_string.encode("utf-8")
        # Compress the bytes
        self.compressed_data = zlib.compress(byte_data)

        return self.compressed_data

    def decompress_string(self):
        """Decompress the compressed data and return the original string."""
        # Decompress the bytes
        decompressed_data = zlib.decompress(self.compressed_data)
        # Convert bytes back to string
        return decompressed_data.decode("utf-8")


class DirectoryReader:
    # Ensure the base path to read the files that contain
    # the custom components from this directory.
    base_path = ""

    def __init__(self, directory_path, *, compress_code_field=False) -> None:
        """Initialize DirectoryReader with a directory path and a flag indicating whether to compress the code."""
        self.directory_path = directory_path
        self.compress_code_field = compress_code_field

    def get_safe_path(self):
        """Check if the path is valid and return it, or None if it's not."""
        return self.directory_path if self.is_valid_path() else None

    def is_valid_path(self) -> bool:
        """Check if the directory path is valid by comparing it to the base path."""
        fullpath = Path(self.directory_path).resolve()
        return not self.base_path or fullpath.is_relative_to(self.base_path)

    def is_empty_file(self, file_content):
        """Check if the file content is empty."""
        return len(file_content.strip()) == 0

    def filter_loaded_components(self, data: dict, *, with_errors: bool) -> dict:
        from langflow.custom.utils import build_component

        items = []
        for menu in data["menu"]:
            components = []
            for component in menu["components"]:
                try:
                    if component["error"] if with_errors else not component["error"]:
                        component_tuple = (*build_component(component), component)
                        components.append(component_tuple)
                except Exception:  # noqa: BLE001
                    logger.debug(f"Error while loading component {component['name']} from {component['file']}")
                    continue
            items.append({"name": menu["name"], "path": menu["path"], "components": components})
        filtered = [menu for menu in items if menu["components"]]
        logger.debug(f"Filtered components {'with errors' if with_errors else ''}: {len(filtered)}")
        return {"menu": filtered}

    def validate_code(self, file_content) -> bool:
        """Validate the Python code by trying to parse it with ast.parse."""
        try:
            ast.parse(file_content)
        except SyntaxError:
            return False
        return True

    def validate_build(self, file_content):
        """Check if the file content contains a function named 'build'."""
        return "def build" in file_content

    def read_file_content(self, file_path):
        """Read and return the content of a file."""
        file_path_ = Path(file_path)
        if not file_path_.is_file():
            return None
        try:
            with file_path_.open(encoding="utf-8") as file:
                # UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 3069:
                # character maps to <undefined>
                return file.read()
        except UnicodeDecodeError:
            # This is happening in Windows, so we need to open the file in binary mode
            # The file is always just a python file, so we can safely read it as utf-8
            with file_path_.open("rb") as f:
                return f.read().decode("utf-8")

    async def aread_file_content(self, file_path):
        """Read and return the content of a file."""
        file_path_ = anyio.Path(file_path)
        if not await file_path_.is_file():
            return None
        try:
            async with async_open(str(file_path_), encoding="utf-8") as file:
                # UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 3069:
                # character maps to <undefined>
                return await file.read()
        except UnicodeDecodeError:
            # This is happening in Windows, so we need to open the file in binary mode
            # The file is always just a python file, so we can safely read it as utf-8
            async with async_open(str(file_path_), "rb") as f:
                return (await f.read()).decode("utf-8")

    def get_files(self):
        """Walk through the directory path and return a list of all .py files."""
        if not (safe_path := self.get_safe_path()):
            msg = f"The path needs to start with '{self.base_path}'."
            raise CustomComponentPathValueError(msg)

        file_list = []
        safe_path_obj = Path(safe_path)
        for file_path in safe_path_obj.rglob("*.py"):
            # Check if the file is in the folder `deactivated` and if so, skip it
            if "deactivated" in file_path.parent.name:
                continue

            # Calculate the depth of the file relative to the safe path
            relative_depth = len(file_path.relative_to(safe_path_obj).parts)

            # Only include files that are one or two levels deep
            if relative_depth <= MAX_DEPTH and file_path.is_file() and not file_path.name.startswith("__"):
                file_list.append(str(file_path))
        return file_list

    def find_menu(self, response, menu_name):
        """Find and return a menu by its name in the response."""
        return next(
            (menu for menu in response["menu"] if menu["name"] == menu_name),
            None,
        )

    def _is_type_hint_imported(self, type_hint_name: str, code: str) -> bool:
        """Check if a specific type hint is imported from the typing module in the given code."""
        module = ast.parse(code)

        return any(
            isinstance(node, ast.ImportFrom)
            and node.module == "typing"
            and any(alias.name == type_hint_name for alias in node.names)
            for node in ast.walk(module)
        )

    def _is_type_hint_used_in_args(self, type_hint_name: str, code: str) -> bool:
        """Check if a specific type hint is used in the function definitions within the given code."""
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
        """Helper function to check if a type hint exists in an annotation."""
        return (
            annotation is not None
            and isinstance(annotation, ast.Subscript)
            and isinstance(annotation.value, ast.Name)
            and annotation.value.id == type_hint_name
        )

    def is_type_hint_used_but_not_imported(self, type_hint_name: str, code: str) -> bool:
        """Check if a type hint is used but not imported in the given code."""
        try:
            return self._is_type_hint_used_in_args(type_hint_name, code) and not self._is_type_hint_imported(
                type_hint_name, code
            )
        except SyntaxError:
            # Returns True if there's something wrong with the code
            # TODO : Find a better way to handle this
            return True

    def process_file(self, file_path):
        """Process a file by validating its content and returning the result and content/error message."""
        try:
            file_content = self.read_file_content(file_path)
        except Exception:  # noqa: BLE001
            logger.exception(f"Error while reading file {file_path}")
            return False, f"Could not read {file_path}"

        if file_content is None:
            return False, f"Could not read {file_path}"
        if self.is_empty_file(file_content):
            return False, "Empty file"
        if not self.validate_code(file_content):
            return False, "Syntax error"
        if self._is_type_hint_used_in_args("Optional", file_content) and not self._is_type_hint_imported(
            "Optional", file_content
        ):
            return (
                False,
                "Type hint 'Optional' is used but not imported in the code.",
            )
        if self.compress_code_field:
            file_content = str(StringCompressor(file_content).compress_string())
        return True, file_content

    def build_component_menu_list(self, file_paths):
        """Build a list of menus with their components from the .py files in the directory."""
        response = {"menu": []}
        logger.debug("-------------------- Building component menu list --------------------")

        for file_path in file_paths:
            file_path_ = Path(file_path)
            menu_name = file_path_.parent.name
            filename = file_path_.name
            validation_result, result_content = self.process_file(file_path)
            if not validation_result:
                logger.error(f"Error while processing file {file_path}")

            menu_result = self.find_menu(response, menu_name) or {
                "name": menu_name,
                "path": str(file_path_.parent),
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

            if validation_result:
                try:
                    output_types = self.get_output_types_from_code(result_content)
                except Exception:  # noqa: BLE001
                    logger.opt(exception=True).debug("Error while getting output types from code")
                    output_types = [component_name_camelcase]
            else:
                output_types = [component_name_camelcase]

            component_info = {
                "name": component_name_camelcase,
                "output_types": output_types,
                "file": filename,
                "code": result_content if validation_result else "",
                "error": "" if validation_result else result_content,
            }
            menu_result["components"].append(component_info)

            if menu_result not in response["menu"]:
                response["menu"].append(menu_result)
        logger.debug("-------------------- Component menu list built --------------------")
        return response

    async def process_file_async(self, file_path):
        try:
            file_content = await self.aread_file_content(file_path)
        except Exception:  # noqa: BLE001
            logger.exception(f"Error while reading file {file_path}")
            return False, f"Could not read {file_path}"

        if file_content is None:
            return False, f"Could not read {file_path}"
        if self.is_empty_file(file_content):
            return False, "Empty file"
        if not self.validate_code(file_content):
            return False, "Syntax error"
        if self._is_type_hint_used_in_args("Optional", file_content) and not self._is_type_hint_imported(
            "Optional", file_content
        ):
            return (
                False,
                "Type hint 'Optional' is used but not imported in the code.",
            )
        if self.compress_code_field:
            file_content = str(StringCompressor(file_content).compress_string())
        return True, file_content

    async def abuild_component_menu_list(self, file_paths):
        start_time = time.perf_counter()
        response = {"menu": []}
        logger.debug("Starting async component menu list build...")

        tasks = [self.process_file_async(file_path) for file_path in file_paths]
        results = await asyncio.gather(*tasks)

        for file_path, (validation_result, result_content) in zip(file_paths, results, strict=True):
            file_path_ = Path(file_path)
            menu_name = file_path_.parent.name
            filename = file_path_.name

            if not validation_result:
                logger.error(f"Failed to process file {file_path}")

            menu_result = self.find_menu(response, menu_name) or {
                "name": menu_name,
                "path": str(file_path_.parent),
                "components": [],
            }
            component_name = filename.split(".")[0]

            if "_" in component_name:
                component_name_camelcase = " ".join(word.title() for word in component_name.split("_"))
            else:
                component_name_camelcase = component_name

            if validation_result:
                try:
                    output_types = await asyncio.to_thread(self.get_output_types_from_code, result_content)
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to extract output types from code")
                    output_types = [component_name_camelcase]
            else:
                output_types = [component_name_camelcase]

            component_info = {
                "name": component_name_camelcase,
                "output_types": output_types,
                "file": filename,
                "code": result_content if validation_result else "",
                "error": "" if validation_result else result_content,
            }
            menu_result["components"].append(component_info)

            if menu_result not in response["menu"]:
                response["menu"].append(menu_result)

        end_time = time.perf_counter()
        duration = end_time - start_time
        logger.debug(f"Successfully built component menu list in {duration:.2f} seconds")
        return response

    @staticmethod
    def get_output_types_from_code(code: str) -> list:
        """Get the output types from the code."""
        custom_component = Component(_code=code)
        types_list = custom_component._get_function_entrypoint_return_type

        # Get the name of types classes
        return [type_.__name__ for type_ in types_list if hasattr(type_, "__name__")]
