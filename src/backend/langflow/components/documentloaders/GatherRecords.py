from concurrent import futures
from pathlib import Path
from typing import Any, Dict, List

from langflow import CustomComponent
from langflow.schema import Record


class GatherRecordsComponent(CustomComponent):
    display_name = "Gather Records"
    description = "Gather records from a directory."

    def build_config(self) -> Dict[str, Any]:
        return {
            "load_hidden": {
                "display_name": "Load Hidden Files",
                "value": False,
                "advanced": True,
            },
            "max_concurrency": {
                "display_name": "Max Concurrency",
                "value": 10,
                "advanced": True,
            },
            "path": {"display_name": "Local Directory"},
            "recursive": {"display_name": "Recursive", "value": True, "advanced": True},
            "use_multithreading": {
                "display_name": "Use Multithreading",
                "value": True,
                "advanced": True,
            },
        }

    def is_hidden(self, path: Path) -> bool:
        return path.name.startswith(".")

    def retrieve_file_paths(
        self,
        path: str,
        types: List[str],
        load_hidden: bool,
        recursive: bool,
        depth: int,
    ) -> List[str]:
        path_obj = Path(path)
        if not path_obj.exists() or not path_obj.is_dir():
            raise ValueError(f"Path {path} must exist and be a directory.")

        def match_types(p: Path) -> bool:
            return any(p.suffix == f".{t}" for t in types) if types else True

        def is_not_hidden(p: Path) -> bool:
            return not self.is_hidden(p) or load_hidden

        def walk_level(directory: Path, max_depth: int):
            directory = directory.resolve()
            prefix_length = len(directory.parts)
            for p in directory.rglob("*" if recursive else "[!.]*"):
                if len(p.parts) - prefix_length <= max_depth:
                    yield p

        glob = "**/*" if recursive else "*"
        paths = walk_level(path_obj, depth) if depth else path_obj.glob(glob)
        file_paths = [str(p) for p in paths if p.is_file() and match_types(p) and is_not_hidden(p)]

        return file_paths

    def parse_file_to_record(self, file_path: str, silent_errors: bool) -> Record:
        # Use the partition function to load the file
        from unstructured.partition.auto import partition

        try:
            elements = partition(file_path)
        except Exception as e:
            if not silent_errors:
                raise ValueError(f"Error loading file {file_path}: {e}") from e
            return None

        # Create a Record
        text = "\n\n".join([str(el) for el in elements])
        metadata = elements.metadata if hasattr(elements, "metadata") else {}
        metadata["file_path"] = file_path
        record = Record(text=text, data=metadata)
        return record

    def get_elements(
        self,
        file_paths: List[str],
        silent_errors: bool,
        max_concurrency: int,
        use_multithreading: bool,
    ) -> List[Record]:
        if use_multithreading:
            records = self.parallel_load_records(file_paths, silent_errors, max_concurrency)
        else:
            records = [self.parse_file_to_record(file_path, silent_errors) for file_path in file_paths]
        records = list(filter(None, records))
        return records

    def parallel_load_records(self, file_paths: List[str], silent_errors: bool, max_concurrency: int) -> List[Record]:
        with futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            loaded_files = executor.map(
                lambda file_path: self.parse_file_to_record(file_path, silent_errors),
                file_paths,
            )
        return loaded_files

    def build(
        self,
        path: str,
        types: List[str] = None,
        depth: int = 0,
        max_concurrency: int = 2,
        load_hidden: bool = False,
        recursive: bool = True,
        silent_errors: bool = False,
        use_multithreading: bool = True,
    ) -> List[Record]:
        resolved_path = self.resolve_path(path)
        file_paths = self.retrieve_file_paths(resolved_path, types, load_hidden, recursive, depth)
        loaded_records = []

        if use_multithreading:
            loaded_records = self.parallel_load_records(file_paths, silent_errors, max_concurrency)
        else:
            loaded_records = [self.parse_file_to_record(file_path, silent_errors) for file_path in file_paths]
        loaded_records = list(filter(None, loaded_records))
        self.status = loaded_records
        return loaded_records
