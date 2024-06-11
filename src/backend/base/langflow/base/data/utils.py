import json
import xml.etree.ElementTree as ET
from concurrent import futures
from pathlib import Path
from typing import Callable, List, Optional, Text

import chardet
import yaml

from langflow.schema.schema import Record

# Types of files that can be read simply by file.read()
# and have 100% to be completely readable
TEXT_FILE_TYPES = [
    "txt",
    "md",
    "mdx",
    "csv",
    "json",
    "yaml",
    "yml",
    "xml",
    "html",
    "htm",
    "pdf",
    "docx",
    "py",
    "sh",
    "sql",
    "js",
    "ts",
    "tsx",
]


def is_hidden(path: Path) -> bool:
    return path.name.startswith(".")


def retrieve_file_paths(
    path: str,
    load_hidden: bool,
    recursive: bool,
    depth: int,
    types: List[str] = TEXT_FILE_TYPES,
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


# ! Removing unstructured dependency until
# ! 3.12 is supported
# def partition_file_to_record(file_path: str, silent_errors: bool) -> Optional[Record]:
#     # Use the partition function to load the file
#     from unstructured.partition.auto import partition  # type: ignore

#     try:
#         elements = partition(file_path)
#     except Exception as e:
#         if not silent_errors:
#             raise ValueError(f"Error loading file {file_path}: {e}") from e
#         return None

#     # Create a Record
#     text = "\n\n".join([Text(el) for el in elements])
#     metadata = elements.metadata if hasattr(elements, "metadata") else {}
#     metadata["file_path"] = file_path
#     record = Record(text=text, data=metadata)
#     return record


def read_text_file(file_path: str) -> str:
    with open(file_path, "rb") as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        encoding = result["encoding"]

        if encoding in ["Windows-1252", "Windows-1254", "MacRoman"]:
            encoding = "utf-8"

    with open(file_path, "r", encoding=encoding) as f:
        return f.read()


def read_docx_file(file_path: str) -> str:
    from docx import Document  # type: ignore

    doc = Document(file_path)
    return "\n\n".join([p.text for p in doc.paragraphs])


def parse_pdf_to_text(file_path: str) -> str:
    from pypdf import PdfReader  # type: ignore

    with open(file_path, "rb") as f:
        reader = PdfReader(f)
        return "\n\n".join([page.extract_text() for page in reader.pages])


def parse_text_file_to_record(file_path: str, silent_errors: bool) -> Optional[Record]:
    try:
        if file_path.endswith(".pdf"):
            text = parse_pdf_to_text(file_path)
        elif file_path.endswith(".docx"):
            text = read_docx_file(file_path)
        else:
            text = read_text_file(file_path)
        # if file is json, yaml, or xml, we can parse it
        if file_path.endswith(".json"):
            text = json.loads(text)
        elif file_path.endswith(".yaml") or file_path.endswith(".yml"):
            text = yaml.safe_load(text)
        elif file_path.endswith(".xml"):
            xml_element = ET.fromstring(text)
            text = ET.tostring(xml_element, encoding="unicode")
    except Exception as e:
        if not silent_errors:
            raise ValueError(f"Error loading file {file_path}: {e}") from e
        return None

    record = Record(data={"file_path": file_path, "text": text})
    return record


# ! Removing unstructured dependency until
# ! 3.12 is supported
# def get_elements(
#     file_paths: List[str],
#     silent_errors: bool,
#     max_concurrency: int,
#     use_multithreading: bool,
# ) -> List[Optional[Record]]:
#     if use_multithreading:
#         records = parallel_load_records(file_paths, silent_errors, max_concurrency)
#     else:
#         records = [partition_file_to_record(file_path, silent_errors) for file_path in file_paths]
#     records = list(filter(None, records))
#     return records


def parallel_load_records(
    file_paths: List[str],
    silent_errors: bool,
    max_concurrency: int,
    load_function: Callable = parse_text_file_to_record,
) -> List[Optional[Record]]:
    with futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        loaded_files = executor.map(
            lambda file_path: load_function(file_path, silent_errors),
            file_paths,
        )
    # loaded_files is an iterator, so we need to convert it to a list
    return list(loaded_files)
