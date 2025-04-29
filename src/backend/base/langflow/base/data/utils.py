import unicodedata
from collections.abc import Callable
from concurrent import futures
from pathlib import Path

import chardet
import orjson
import yaml
from defusedxml import ElementTree

from langflow.schema import Data

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

IMG_FILE_TYPES = ["jpg", "jpeg", "png", "bmp", "image"]


def normalize_text(text):
    return unicodedata.normalize("NFKD", text)


def is_hidden(path: Path) -> bool:
    return path.name.startswith(".")


def format_directory_path(path: str) -> str:
    """Format a directory path to ensure it's properly escaped and valid.

    Args:
    path (str): The input path string.

    Returns:
    str: A properly formatted path string.
    """
    return path.replace("\n", "\\n")


# Ignoring FBT001 because the DirectoryComponent in 1.0.19
# calls this function without keyword arguments
def retrieve_file_paths(
    path: str,
    load_hidden: bool,  # noqa: FBT001
    recursive: bool,  # noqa: FBT001
    depth: int,
    types: list[str] = TEXT_FILE_TYPES,
) -> list[str]:
    path = format_directory_path(path)
    path_obj = Path(path)
    if not path_obj.exists() or not path_obj.is_dir():
        msg = f"Path {path} must exist and be a directory."
        raise ValueError(msg)

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
    return [str(p) for p in paths if p.is_file() and match_types(p) and is_not_hidden(p)]


def partition_file_to_data(file_path: str, *, silent_errors: bool) -> Data | None:
    # Use the partition function to load the file
    from unstructured.partition.auto import partition

    try:
        elements = partition(file_path)
    except Exception as e:
        if not silent_errors:
            msg = f"Error loading file {file_path}: {e}"
            raise ValueError(msg) from e
        return None

    # Create a Data
    text = "\n\n".join([str(el) for el in elements])
    metadata = elements.metadata if hasattr(elements, "metadata") else {}
    metadata["file_path"] = file_path
    return Data(text=text, data=metadata)


def read_text_file(file_path: str) -> str:
    file_path_ = Path(file_path)
    raw_data = file_path_.read_bytes()
    result = chardet.detect(raw_data)
    encoding = result["encoding"]

    if encoding in {"Windows-1252", "Windows-1254", "MacRoman"}:
        encoding = "utf-8"

    return file_path_.read_text(encoding=encoding)


def read_docx_file(file_path: str) -> str:
    from docx import Document

    doc = Document(file_path)
    return "\n\n".join([p.text for p in doc.paragraphs])


def extract_fields(data):
    extracted = []
    for item in data:
        try:
            # Extract page_content (assuming it's an attribute of the Document object)
            page_content = getattr(item, "page_content", "")

            # Extract metadata (assuming metadata is an attribute)
            metadata = getattr(item, "metadata", {})

            # Access dl_meta and doc_items (assuming they are nested attributes or dictionaries)
            dl_meta = metadata.get("dl_meta", {}) if isinstance(metadata, dict) else getattr(metadata, "dl_meta", {})
            doc_items = dl_meta.get("doc_items", []) if isinstance(dl_meta, dict) else getattr(dl_meta, "doc_items", [])

            # Extract content_layer and label from doc_items
            for doc_item in doc_items:
                # If doc_item is a dictionary
                if isinstance(doc_item, dict):
                    content_layer = doc_item.get("content_layer", "")
                    label = doc_item.get("label", "")
                else:
                    # If doc_item is an object, use getattr
                    content_layer = getattr(doc_item, "content_layer", "")
                    label = getattr(doc_item, "label", "")

                extracted.append({
                    "page_content": page_content,
                    "content_layer": content_layer,
                    "label": label
                })
        except AttributeError as _:
            continue

    return extracted


def parse_pdf_to_text(file_path: str) -> Data:
    from langchain_docling import DoclingLoader

    # Get the source of the PDF file
    loader = DoclingLoader(file_path=file_path)
    docs = loader.load()

    # Grab the extract fields from the documents
    metadata = extract_fields(docs)

    return Data(
            data={
                "metadata": {"metadata": metadata},
                "file_path": file_path,
                "text": "\n\n".join([record.get("page_content", "") for record in metadata]),
            }
        )


def handle_json_data(text):
    # if file is json, yaml, or xml, we can parse it
    text = orjson.loads(text)
    if isinstance(text, dict):
        text = {k: normalize_text(v) if isinstance(v, str) else v for k, v in text.items()}
    elif isinstance(text, list):
        text = [normalize_text(item) if isinstance(item, str) else item for item in text]
    return orjson.dumps(text).decode("utf-8")


def parse_text_file_to_data(file_path: str, *, silent_errors: bool) -> Data | None:
    try:
        # Special PDF handling with docling
        if file_path.endswith(".pdf"):
            return parse_pdf_to_text(file_path)

        # Check if the file is a docx file
        text = read_docx_file(file_path) if file_path.endswith(".docx") else read_text_file(file_path)

        # if file is json, yaml, or xml, we can parse it
        if file_path.endswith(".json"):
            text = handle_json_data(text)
        elif file_path.endswith((".yaml", ".yml")):
            text = yaml.safe_load(text)
        elif file_path.endswith(".xml"):
            xml_element = ElementTree.fromstring(text)
            text = ElementTree.tostring(xml_element, encoding="unicode")
    except Exception as e:
        if not silent_errors:
            msg = f"Error loading file {file_path}: {e}"
            raise ValueError(msg) from e
        return None

    return Data(data={"file_path": file_path, "text": text})


# ! Removing unstructured dependency until
# ! 3.12 is supported
# def get_elements(
#     file_paths: List[str],
#     silent_errors: bool,
#     max_concurrency: int,
#     use_multithreading: bool,
# ) -> List[Optional[Data]]:
#     if use_multithreading:
#         data = parallel_load_data(file_paths, silent_errors, max_concurrency)
#     else:
#         data = [partition_file_to_data(file_path, silent_errors) for file_path in file_paths]
#     data = list(filter(None, data))
#     return data


def parallel_load_data(
    file_paths: list[str],
    *,
    silent_errors: bool,
    max_concurrency: int,
    load_function: Callable = parse_text_file_to_data,
) -> list[Data | None]:
    with futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        loaded_files = executor.map(
            lambda file_path: load_function(file_path, silent_errors=silent_errors),
            file_paths,
        )
    # loaded_files is an iterator, so we need to convert it to a list
    return list(loaded_files)
