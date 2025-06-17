import unicodedata
from collections.abc import Callable
from concurrent import futures
from pathlib import Path

import chardet
import orjson
import yaml
from defusedxml import ElementTree
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption
from docling_core.types.doc.base import ImageRefMode

from langflow.schema.data import Data

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


def convert_json_to_text(file_path: str, *, silent_errors: bool) -> Data | None:
    try:
        _text = read_text_file(file_path=file_path)

        loaded_json = orjson.loads(_text)
        if isinstance(loaded_json, dict):
            loaded_json = {k: normalize_text(v) if isinstance(v, str) else v for k, v in loaded_json.items()}
        elif isinstance(loaded_json, list):
            loaded_json = [normalize_text(item) if isinstance(item, str) else item for item in loaded_json]

        text = orjson.dumps(loaded_json).decode("utf-8")
        return Data(data={"file_path": file_path, "text": text})
    except Exception as exc:
        if not silent_errors:
            msg = f"Could not parse json file {file_path}: {exc}"
            raise ValueError(msg) from exc

    return None


def convert_yaml_to_text(file_path: str, *, silent_errors: bool) -> Data | None:
    try:
        _text = read_text_file(file_path=file_path)
        loaded_yaml = yaml.safe_load(_text)
        text = yaml.dump(loaded_yaml, default_flow_style=False)
        return Data(data={"file_path": file_path, "text": text})
    except Exception as exc:
        if not silent_errors:
            msg = f"Could not parse yaml file {file_path}: {exc}"
            raise ValueError(msg) from exc

    return None


def convert_xml_to_text(file_path: str, *, silent_errors: bool) -> Data | None:
    try:
        _text = read_text_file(file_path=file_path)

        xml_element = ElementTree.fromstring(_text)
        text = ElementTree.tostring(xml_element, encoding="unicode")
        return Data(data={"file_path": file_path, "text": text})
    except Exception as exc:
        if not silent_errors:
            msg = f"Could not parse xml file {file_path}: {exc}"
            raise ValueError(msg) from exc

    return None


def convert_pdf_to_text(
    file_path: str,
    *,
    silent_errors: bool = False,
    do_ocr: bool = False,
    ocr_lang: list[str] | None = None,
    do_table_structure: bool = False,
    do_picture_classification: bool = False,
) -> Data | None:
    try:
        # fall back to english, pick your language here: https://www.jaided.ai/easyocr/
        if ocr_lang is None:
            ocr_lang = ["en"]

        # OPTIMIZAION: could be better to "cache" the converters ...
        pipeline_options = PdfPipelineOptions()
        # pipeline_options.images_scale = 2
        pipeline_options.generate_page_images = False
        pipeline_options.do_picture_classification = do_picture_classification
        pipeline_options.do_ocr = do_ocr
        pipeline_options.do_table_structure = do_table_structure
        pipeline_options.table_structure_options.do_cell_matching = True
        pipeline_options.ocr_options.lang = ocr_lang
        # pipeline_options.accelerator_options = AcceleratorOptions(num_threads=1, device=AcceleratorDevice.AUTO)

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )

        result = converter.convert(source=Path(file_path))
        markdown_text = result.document.export_to_markdown(
            image_mode=ImageRefMode.PLACEHOLDER,
            image_placeholder="<!-- image -->",
        )

        return Data(data={"file_path": file_path, "text": markdown_text})

    except Exception as exc:
        if not silent_errors:
            msg = f"Could not parse pdf file {file_path}: {exc}"
            raise ValueError(msg) from exc

    return None


def convert_img_to_text(
    file_path: str,
    *,
    silent_errors: bool = False,
    ocr_lang: list[str] | None = None,
    do_table_structure: bool = False,
    do_picture_classification: bool = False,
) -> Data | None:
    try:
        # fall back to english, pick your language here: https://www.jaided.ai/easyocr/
        if ocr_lang is None:
            ocr_lang = ["en"]

        # OPTIMIZAION: could be better to "cache" the converters ...
        pipeline_options = PdfPipelineOptions()
        # pipeline_options.images_scale = 2
        pipeline_options.generate_page_images = False
        pipeline_options.do_picture_classification = do_picture_classification
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = do_table_structure
        pipeline_options.table_structure_options.do_cell_matching = True
        pipeline_options.ocr_options.lang = ocr_lang
        # pipeline_options.accelerator_options = AcceleratorOptions(num_threads=1, device=AcceleratorDevice.AUTO)

        converter = DocumentConverter(
            format_options={
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
            }
        )

        result = converter.convert(source=Path(file_path))
        markdown_text = result.document.export_to_markdown(
            image_mode=ImageRefMode.PLACEHOLDER,
            image_placeholder="<!-- image -->",
        )

        return Data(data={"file_path": file_path, "text": markdown_text})

    except Exception as exc:
        if not silent_errors:
            msg = f"Could not parse image file {file_path}: {exc}"
            raise ValueError(msg) from exc

    return None


def convert_docx_to_text(file_path: str, *, silent_errors: bool) -> Data | None:
    try:
        converter = DocumentConverter(allowed_formats=[InputFormat.DOCX])

        result = converter.convert(source=Path(file_path))
        markdown_text = result.document.export_to_markdown()

        return Data(data={"file_path": file_path, "text": markdown_text})

    except Exception as exc:
        if not silent_errors:
            msg = f"Could not parse docx file {file_path}: {exc}"
            raise ValueError(msg) from exc

    return None


def convert_file_to_data(
    file_path: str, *, silent_errors: bool, do_ocr: bool = False, ocr_lang: list[str] | None = None
) -> Data | None:
    try:
        if file_path.endswith(".json"):
            return convert_json_to_text(file_path=file_path, silent_errors=silent_errors)

        if file_path.endswith((".yaml", ".yml")):
            return convert_yaml_to_text(file_path=file_path, silent_errors=silent_errors)

        if file_path.endswith(".xml"):
            return convert_xml_to_text(file_path=file_path, silent_errors=silent_errors)

        if file_path.endswith(".pdf"):
            return convert_pdf_to_text(
                file_path=file_path, silent_errors=silent_errors, do_ocr=do_ocr, ocr_lang=ocr_lang
            )

        if file_path.endswith(".docx"):
            return convert_docx_to_text(file_path=file_path, silent_errors=silent_errors)

        # Handle image files
        if do_ocr and (any(file_path.endswith(f".{ext}") for ext in IMG_FILE_TYPES)):
            return convert_img_to_text(file_path=file_path, silent_errors=silent_errors, ocr_lang=ocr_lang)

        # Handle plain text and other text-based files
        if any(file_path.endswith(f".{ext}") for ext in TEXT_FILE_TYPES):
            text = read_text_file(file_path)
            return Data(data={"file_path": file_path, "text": text})

    except Exception as exc:
        if not silent_errors:
            msg = f"Error loading file {file_path}: {exc}"
            raise ValueError(msg) from exc

    return None


def parallel_load_data(
    file_paths: list[str],
    *,
    silent_errors: bool,
    max_concurrency: int,
    load_function: Callable = convert_file_to_data,
    do_table_structure: bool = False,  # We try to keep conversion as light as possible
    do_picture_classification: bool = False,
    do_ocr: bool = False,
    ocr_lang: list[str] | None = None,
) -> list[Data | None]:
    with futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        loaded_files = executor.map(
            lambda file_path: load_function(
                file_path,
                silent_errors=silent_errors,
                do_ocr=do_ocr,
                ocr_lang=ocr_lang,
                do_table_structure=do_table_structure,
                do_picture_classification=do_picture_classification,
            ),
            file_paths,
        )
    # loaded_files is an iterator, so we need to convert it to a list
    return list(loaded_files)
