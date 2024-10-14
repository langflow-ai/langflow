from langflow.base.data.utils import TEXT_FILE_TYPES, parallel_load_data, parse_text_file_to_data, retrieve_file_paths
from langflow.custom import Component
from langflow.io import BoolInput, IntInput, MessageTextInput
from langflow.schema import Data
from langflow.template import Output


class DirectoryComponent(Component):
    display_name = "Directory"
    description = "Recursively load files from a directory."
    icon = "folder"
    name = "Directory"

    inputs = [
        MessageTextInput(
            name="path",
            display_name="Path",
            info="Path to the directory to load files from.",
        ),
        MessageTextInput(
            name="types",
            display_name="Types",
            info="File types to load. Leave empty to load all default supported types.",
            is_list=True,
        ),
        IntInput(
            name="depth",
            display_name="Depth",
            info="Depth to search for files.",
            value=0,
        ),
        IntInput(
            name="max_concurrency",
            display_name="Max Concurrency",
            advanced=True,
            info="Maximum concurrency for loading files.",
            value=2,
        ),
        BoolInput(
            name="load_hidden",
            display_name="Load Hidden",
            advanced=True,
            info="If true, hidden files will be loaded.",
        ),
        BoolInput(
            name="recursive",
            display_name="Recursive",
            advanced=True,
            info="If true, the search will be recursive.",
        ),
        BoolInput(
            name="silent_errors",
            display_name="Silent Errors",
            advanced=True,
            info="If true, errors will not raise an exception.",
        ),
        BoolInput(
            name="use_multithreading",
            display_name="Use Multithreading",
            advanced=True,
            info="If true, multithreading will be used.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="load_directory"),
    ]

    def load_directory(self) -> list[Data]:
        path = self.path
        types = (
            self.types if self.types and self.types != [""] else TEXT_FILE_TYPES
        )  # self.types is already a list due to is_list=True
        depth = self.depth
        max_concurrency = self.max_concurrency
        load_hidden = self.load_hidden
        recursive = self.recursive
        silent_errors = self.silent_errors
        use_multithreading = self.use_multithreading

        resolved_path = self.resolve_path(path)
        file_paths = retrieve_file_paths(
            resolved_path, load_hidden=load_hidden, recursive=recursive, depth=depth, types=types
        )

        if types:
            file_paths = [fp for fp in file_paths if any(fp.endswith(ext) for ext in types)]

        loaded_data = []

        if use_multithreading:
            loaded_data = parallel_load_data(file_paths, silent_errors=silent_errors, max_concurrency=max_concurrency)
        else:
            loaded_data = [parse_text_file_to_data(file_path, silent_errors=silent_errors) for file_path in file_paths]
        loaded_data = list(filter(None, loaded_data))
        self.status = loaded_data
        return loaded_data  # type: ignore[return-value]
