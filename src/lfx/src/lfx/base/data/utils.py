import asyncio
import codecs
import contextlib
import logging
import re
import tempfile
import unicodedata
from collections.abc import Awaitable, Callable
from concurrent import futures
from contextvars import copy_context
from io import BytesIO
from pathlib import Path

import chardet
import orjson
import yaml
from defusedxml import ElementTree
from pypdf import PdfReader

from lfx.base.data.storage_utils import read_file_bytes
from lfx.schema.data import Data
from lfx.services.deps import get_settings_service
from lfx.utils.async_helpers import run_until_complete

logger = logging.getLogger(__name__)

# Max bytes to feed to chardet for encoding detection.
# Scanning the first 100 KB is sufficient for reliable detection
# and avoids O(n) overhead on large files (e.g. 800s for 1.5 GB).
_CHARDET_SAMPLE_BYTES = 102400

# Types of files that can be read simply by file.read()
# and have 100% to be completely readable
TEXT_FILE_TYPES = [
    "csv",
    "json",
    "pdf",
    "txt",
    "md",
    "mdx",
    "yaml",
    "yml",
    "xml",
    "html",
    "htm",
    "docx",
    "py",
    "sh",
    "sql",
    "js",
    "ts",
    "tsx",
]

IMG_FILE_TYPES = ["jpg", "jpeg", "png", "bmp", "image"]


def parse_structured_text(text: str, file_path: str) -> str | dict | list:
    """Parse structured text formats (JSON, YAML, XML) and normalize text.

    Args:
        text: The text content to parse
        file_path: The file path (used to determine format)

    Returns:
        Parsed content (dict/list for JSON, dict for YAML, str for XML)
    """
    if file_path.endswith(".json"):
        loaded_json = orjson.loads(text)
        if isinstance(loaded_json, dict):
            loaded_json = {k: normalize_text(v) if isinstance(v, str) else v for k, v in loaded_json.items()}
        elif isinstance(loaded_json, list):
            loaded_json = [normalize_text(item) if isinstance(item, str) else item for item in loaded_json]
        return orjson.dumps(loaded_json).decode("utf-8")

    if file_path.endswith((".yaml", ".yml")):
        return yaml.safe_load(text)

    if file_path.endswith(".xml"):
        xml_element = ElementTree.fromstring(text)
        return ElementTree.tostring(xml_element, encoding="unicode")

    return text


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
    path_obj = Path(path).resolve()
    if not path_obj.exists() or not path_obj.is_dir():
        msg = f"Path {path} must exist and be a directory."
        raise ValueError(msg)

    def match_types(p: Path) -> bool:
        return any(p.suffix == f".{t}" for t in types) if types else True

    def is_not_hidden(p: Path) -> bool:
        return not is_hidden(p) or load_hidden

    def is_within_directory(p: Path) -> bool:
        return p.resolve().is_relative_to(path_obj)

    def walk_level(directory: Path, max_depth: int):
        prefix_length = len(directory.parts)
        for p in directory.rglob("*" if recursive else "[!.]*"):
            if len(p.parts) - prefix_length <= max_depth:
                yield p

    glob = "**/*" if recursive else "*"
    paths = walk_level(path_obj, depth) if depth else path_obj.glob(glob)
    return [str(p) for p in paths if p.is_file() and match_types(p) and is_not_hidden(p) and is_within_directory(p)]


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


def _detect_encoding_with_fallbacks(raw_data: bytes) -> list[str]:
    """Detect encoding and build a fallback chain for decoding.

    Returns a list of encodings to try in order, ending with latin-1
    which always succeeds as it maps all 256 byte values.
    """
    result = chardet.detect(raw_data[:_CHARDET_SAMPLE_BYTES])
    detected_encoding = result.get("encoding") if result else None

    if detected_encoding in {"Windows-1252", "Windows-1254", "MacRoman"}:
        # chardet reports one of these for many files that are utf-8 in reality, so
        # try utf-8 first. Its guesses also miss GB18030 four-byte characters,
        # which cp1252 would silently mangle. Include three trailing bytes so
        # a four-byte pattern can straddle the detection sample boundary.
        encodings: list[str] = ["utf-8"]
        if re.search(rb"[\x81-\xfe][0-9][\x81-\xfe][0-9]", raw_data[: _CHARDET_SAMPLE_BYTES + 3]):
            encodings.append("gb18030")
        # Otherwise cp1252 must precede gb18030, which accepts some Windows
        # punctuation as CJK characters. Both readers validate each candidate.
        encodings.append("cp1252")
    else:
        encodings = [detected_encoding] if detected_encoding else []

    for fallback in ("utf-8", "gb18030", "cp1252"):
        if fallback not in encodings:
            encodings.append(fallback)
    encodings.append("latin-1")
    return encodings


def read_text_file(file_path: str, *, encoding: str | None = None) -> str:
    """Read a text file, detecting its encoding unless one is explicitly supplied.

    Args:
        file_path: Path to the file (local path only, not storage service path)
        encoding: Explicit text encoding. Invalid choices raise without falling back.

    Returns:
        str: The file content as text
    """
    return _read_text_file_with_encoding(file_path, encoding=encoding)[0]


def _read_text_file_with_encoding(file_path: str, *, encoding: str | None = None) -> tuple[str, str]:
    text, selected = _decode_text_bytes_with_encoding(Path(file_path).read_bytes(), file_path, encoding=encoding)
    # Preserve the universal newline handling of Path.read_text in the sync reader.
    return text.replace("\r\n", "\n").replace("\r", "\n"), selected


async def read_text_file_async(file_path: str, *, encoding: str | None = None) -> str:
    """Read a text file with automatic encoding detection (async, storage-aware).

    Args:
        file_path: Path to the file (S3 key format "flow_id/filename" or local path)
        encoding: Explicit text encoding. Invalid choices raise without falling back.

    Returns:
        str: The file content as text
    """
    return (await _read_text_file_with_encoding_async(file_path, encoding=encoding))[0]


async def _read_text_file_with_encoding_async(file_path: str, *, encoding: str | None = None) -> tuple[str, str]:
    # Use storage-aware read to get bytes; encoding detection is CPU-bound, so keep it off the loop.
    raw_data = await read_file_bytes(file_path)
    return await asyncio.to_thread(_decode_text_bytes_with_encoding, raw_data, file_path, encoding=encoding)


def _decode_text_bytes(raw_data: bytes, file_path: str, *, encoding: str | None = None) -> str:
    return _decode_text_bytes_with_encoding(raw_data, file_path, encoding=encoding)[0]


def _decode_text_bytes_with_encoding(
    raw_data: bytes, file_path: str, *, encoding: str | None = None
) -> tuple[str, str]:
    if encoding is not None:
        # A user-selected encoding is authoritative: never silently retry another codec.
        return raw_data.decode(encoding), codecs.lookup(encoding).name

    for enc in _detect_encoding_with_fallbacks(raw_data):
        try:
            text = raw_data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            logger.debug("Encoding '%s' failed for %s, trying next fallback", enc, file_path)
            continue

        selected = codecs.lookup(enc).name
        if selected != "ascii" and not selected.startswith("utf-"):
            logger.warning(
                "Auto-selected text encoding '%s' for %s. Detection can be ambiguous. "
                "Verify the text or specify an encoding explicitly.",
                selected,
                file_path,
            )
        return text, selected

    # Unreachable: latin-1 in the fallback chain always succeeds
    return raw_data.decode("latin-1"), "iso8859-1"


def read_docx_file(file_path: str) -> str:
    """Read a DOCX file and extract text.

    ote: python-docx requires a file path, so this only works with local files.
    For storage service files, use read_docx_file_async which downloads to temp.

    Args:
        file_path: Path to the DOCX file (local path only)

    Returns:
        str: Extracted text from the document
    """
    from docx import Document

    doc = Document(file_path)
    return "\n\n".join([p.text for p in doc.paragraphs])


async def read_docx_file_async(file_path: str) -> str:
    """Read a DOCX file and extract text (async, storage-aware).

    For S3 storage, downloads to temp file (python-docx requires file path).
    For local storage, reads directly.

    Args:
        file_path: Path to the DOCX file (S3 key format "flow_id/filename" or local path)

    Returns:
        str: Extracted text from the document
    """
    from .storage_utils import read_file_bytes

    settings = get_settings_service().settings

    if settings.storage_type == "local":
        # Local storage - read directly
        return await asyncio.to_thread(read_docx_file, file_path)

    # S3 storage - need temp file for python-docx (doesn't support BytesIO)
    content = await read_file_bytes(file_path)
    return await asyncio.to_thread(_read_docx_bytes_via_temp_file, content, file_path)


def _read_docx_bytes_via_temp_file(content: bytes, file_path: str) -> str:
    # Create temp file with .docx extension
    # Extract filename from path for suffix
    suffix = Path(file_path.split("/")[-1]).suffix
    with tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, delete=False) as tmp_file:
        tmp_file.write(content)
        temp_path = tmp_file.name

    try:
        return read_docx_file(temp_path)
    finally:
        with contextlib.suppress(Exception):
            Path(temp_path).unlink()


def extract_text_from_bytes(file_name: str, file_content: bytes) -> str:
    """Extract text from binary file content based on file extension.

    Supports PDF (via pypdf), DOCX (via python-docx), and plain text files.

    Raises:
        ValueError: If the file content is corrupted or cannot be parsed.
    """
    lower_name = file_name.lower()
    if lower_name.endswith(".pdf"):
        try:
            with BytesIO(file_content) as f, PdfReader(f) as reader:
                return "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            msg = f"Failed to parse PDF file '{file_name}': {e}"
            raise ValueError(msg) from e
    if lower_name.endswith(".docx"):
        try:
            from docx import Document

            doc = Document(BytesIO(file_content))
            return "\n\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            msg = f"Failed to parse DOCX file '{file_name}': {e}"
            raise ValueError(msg) from e
    return file_content.decode("utf-8", errors="ignore")


def parse_pdf_to_text(file_path: str) -> str:
    with Path(file_path).open("rb") as f, PdfReader(f) as reader:
        return "\n\n".join([page.extract_text() for page in reader.pages])


async def parse_pdf_to_text_async(file_path: str) -> str:
    """Parse a PDF file to extract text (async, storage-aware).

    Uses storage-aware file reading to support both local and S3 storage.

    Args:
        file_path: Path to the PDF file (S3 key format "flow_id/filename" or local path)

    Returns:
        str: Extracted text from all pages
    """
    content = await read_file_bytes(file_path)
    return await asyncio.to_thread(_parse_pdf_bytes_to_text, content)


def _parse_pdf_bytes_to_text(content: bytes) -> str:
    with BytesIO(content) as f, PdfReader(f) as reader:
        return "\n\n".join([page.extract_text() for page in reader.pages])


def parse_text_file_to_data(file_path: str, *, silent_errors: bool, encoding: str | None = None) -> Data | None:
    """Parse a text file to Data (sync version).

    For S3 storage, this will use async operations to fetch the file.
    For local storage, reads directly from filesystem.
    """
    settings = get_settings_service().settings

    # If using S3 storage, we need to use async operations
    if settings.storage_type == "s3":
        # Run the async version safely (handles existing event loops)
        return run_until_complete(
            parse_text_file_to_data_async(file_path, silent_errors=silent_errors, encoding=encoding)
        )

    metadata = {}
    try:
        if file_path.endswith(".pdf"):
            text = parse_pdf_to_text(file_path)
        elif file_path.endswith(".docx"):
            text = read_docx_file(file_path)
        else:
            text, selected = _read_text_file_with_encoding(file_path, encoding=encoding)
            metadata["encoding"] = selected

        text = parse_structured_text(text, file_path)
    except Exception as e:
        if not silent_errors:
            msg = f"Error loading file {file_path}: {e}"
            raise ValueError(msg) from e
        return None

    return Data(data={"file_path": file_path, "text": text, **metadata})


async def parse_text_file_to_data_async(
    file_path: str, *, silent_errors: bool, encoding: str | None = None
) -> Data | None:
    """Parse a text file to Data (async version, supports storage service).

    This version properly handles storage service files:
    - For text/JSON/YAML/XML: reads bytes directly (no temp file)
    - For PDF: reads bytes directly via BytesIO (no temp file)
    - For DOCX: downloads to temp file (python-docx requires file path)
    """
    metadata = {}
    try:
        if file_path.endswith(".pdf"):
            text = await parse_pdf_to_text_async(file_path)
        elif file_path.endswith(".docx"):
            text = await read_docx_file_async(file_path)
        else:
            # Text files - read directly, no temp file needed
            text, selected = await _read_text_file_with_encoding_async(file_path, encoding=encoding)
            metadata["encoding"] = selected

        # Parse structured formats (JSON, YAML, XML)
        text = await asyncio.to_thread(parse_structured_text, text, file_path)

        return Data(data={"file_path": file_path, "text": text, **metadata})

    except Exception as e:
        if not silent_errors:
            msg = f"Error loading file {file_path}: {e}"
            raise ValueError(msg) from e
        return None


async def aparse_text_file_to_data(file_path: str, *, silent_errors: bool, encoding: str | None = None) -> Data | None:
    """Parse a text file to Data from a coroutine without blocking its event loop.

    Unlike ``parse_text_file_to_data``, this never goes through ``run_until_complete``: under
    S3 the object read is awaited on the caller's loop, while local reads and all parsing run
    in a worker thread.
    """
    settings = get_settings_service().settings
    if settings.storage_type == "s3":
        return await parse_text_file_to_data_async(file_path, silent_errors=silent_errors, encoding=encoding)
    return await asyncio.to_thread(parse_text_file_to_data, file_path, silent_errors=silent_errors, encoding=encoding)


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
    # Each thread gets its own context copy so ContextVars (e.g. component_context_var)
    # are available in thread pool workers across all Python versions.
    def _run_in_context(file_path: str) -> Data | None:
        ctx = copy_context()
        return ctx.run(load_function, file_path, silent_errors=silent_errors)

    with futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        loaded_files = executor.map(_run_in_context, file_paths)
    # loaded_files is an iterator, so we need to convert it to a list
    return list(loaded_files)


async def aparallel_load_data(
    file_paths: list[str],
    *,
    silent_errors: bool,
    max_concurrency: int,
    load_function: Callable[..., Awaitable[Data | None]] = aparse_text_file_to_data,
) -> list[Data | None]:
    """Async counterpart of ``parallel_load_data`` with at most ``max_concurrency`` loads in flight.

    Results keep the order of ``file_paths``. Like the executor-backed sync version, every load
    finishes before the first error (in input order) is raised, so no worker thread started by a
    load outlives this call.
    """
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def _load(file_path: str) -> Data | None:
        async with semaphore:
            return await load_function(file_path, silent_errors=silent_errors)

    results = await asyncio.gather(*(_load(file_path) for file_path in file_paths), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return list(results)
