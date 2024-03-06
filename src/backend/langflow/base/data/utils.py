from concurrent import futures
from pathlib import Path
from typing import List, Optional, Text

from langflow.schema.schema import Record


def is_hidden(path: Path) -> bool:
    return path.name.startswith(".")


def retrieve_file_paths(
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
        return not is_hidden(p) or load_hidden

    def walk_level(directory: Path, max_depth: int):
        directory = directory.resolve()
        prefix_length = len(directory.parts)
        for p in directory.rglob("*" if recursive else "[!.]*"):
            if len(p.parts) - prefix_length <= max_depth:
                yield p

    glob = "**/*" if recursive else "*"
    paths = walk_level(path_obj, depth) if depth else path_obj.glob(glob)
    file_paths = [Text(p) for p in paths if p.is_file() and match_types(p) and is_not_hidden(p)]

    return file_paths


def parse_file_to_record(file_path: str, silent_errors: bool) -> Optional[Record]:
    # Use the partition function to load the file
    from unstructured.partition.auto import partition  # type: ignore

    try:
        elements = partition(file_path)
    except Exception as e:
        if not silent_errors:
            raise ValueError(f"Error loading file {file_path}: {e}") from e
        return None

    # Create a Record
    text = "\n\n".join([Text(el) for el in elements])
    metadata = elements.metadata if hasattr(elements, "metadata") else {}
    metadata["file_path"] = file_path
    record = Record(text=text, data=metadata)
    return record


def get_elements(
    file_paths: List[str],
    silent_errors: bool,
    max_concurrency: int,
    use_multithreading: bool,
) -> List[Optional[Record]]:
    if use_multithreading:
        records = parallel_load_records(file_paths, silent_errors, max_concurrency)
    else:
        records = [parse_file_to_record(file_path, silent_errors) for file_path in file_paths]
    records = list(filter(None, records))
    return records


def parallel_load_records(file_paths: List[str], silent_errors: bool, max_concurrency: int) -> List[Optional[Record]]:
    with futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        loaded_files = executor.map(
            lambda file_path: parse_file_to_record(file_path, silent_errors),
            file_paths,
        )
    # loaded_files is an iterator, so we need to convert it to a list
    return list(loaded_files)
