from typing import Any, Dict, List, Optional

from langflow.base.data.utils import parallel_load_records, parse_text_file_to_record, retrieve_file_paths
from langflow.custom import CustomComponent
from langflow.schema import Record


class DirectoryComponent(CustomComponent):
    display_name = "Directory"
    description = "Recursively load files from a directory."
    icon = "folder"

    def build_config(self) -> Dict[str, Any]:
        return {
            "path": {"display_name": "Path"},
            "types": {
                "display_name": "Types",
                "info": "File types to load. Leave empty to load all types.",
            },
            "depth": {"display_name": "Depth", "info": "Depth to search for files."},
            "max_concurrency": {"display_name": "Max Concurrency", "advanced": True},
            "load_hidden": {
                "display_name": "Load Hidden",
                "advanced": True,
                "info": "If true, hidden files will be loaded.",
            },
            "recursive": {
                "display_name": "Recursive",
                "advanced": True,
                "info": "If true, the search will be recursive.",
            },
            "silent_errors": {
                "display_name": "Silent Errors",
                "advanced": True,
                "info": "If true, errors will not raise an exception.",
            },
            "use_multithreading": {
                "display_name": "Use Multithreading",
                "advanced": True,
            },
        }

    def build(
        self,
        path: str,
        depth: int = 0,
        max_concurrency: int = 2,
        load_hidden: bool = False,
        recursive: bool = True,
        silent_errors: bool = False,
        use_multithreading: bool = True,
    ) -> List[Optional[Record]]:
        resolved_path = self.resolve_path(path)
        file_paths = retrieve_file_paths(resolved_path, load_hidden, recursive, depth)
        loaded_records = []

        if use_multithreading:
            loaded_records = parallel_load_records(file_paths, silent_errors, max_concurrency)
        else:
            loaded_records = [parse_text_file_to_record(file_path, silent_errors) for file_path in file_paths]
        loaded_records = list(filter(None, loaded_records))
        self.status = loaded_records
        return loaded_records
