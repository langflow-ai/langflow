import contextlib
import json
import re
import shutil
import subprocess
import tempfile
import threading
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

from lfx.base.data import BaseFileComponent
from lfx.inputs import (
    BoolInput,
    DropdownInput,
    IntInput,
    MultilineInput,
    SecretStrInput,
    StrInput,
)
from lfx.io import FileInput, Output
from lfx.schema import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message

# Sentinel pattern for page-level splitting in text/markdown/html formats.
# The %page-number% placeholder is replaced by opendataloader-pdf with the actual page number.
_PAGE_SENTINEL_TEMPLATE = "\n---ODL_PAGE_BREAK_%page-number%---\n"
_PAGE_SENTINEL_PATTERN = re.compile(r"---ODL_PAGE_BREAK_(\d+)---")

# Mapping from output format to the corresponding page separator parameter name.
_FORMAT_TO_SEPARATOR_KEY = {
    "text": "text_page_separator",
    "markdown": "markdown_page_separator",
    "markdown-with-html": "markdown_page_separator",
    "markdown-with-images": "markdown_page_separator",
    "html": "html_page_separator",
}


class OpenDataLoaderPDFComponent(BaseFileComponent):
    """OpenDataLoader PDF component for processing PDF files.

    Uses OpenDataLoader PDF to convert PDFs into structured formats
    (JSON, Markdown, HTML, Text) for RAG and LLM pipelines.

    Outputs:
        - Files (DataFrame): One row per PDF file — for data analysis.
        - Pages (DataFrame): One row per page with ``page_number`` metadata — for RAG with citations.
        - Text (Message): Concatenated text of all files — for simple chatbot prompts.
        - Toolset (auto): Agent tools ``read_pdf`` and ``read_pdf_page``.
    """

    display_name = "OpenDataLoader PDF"
    # description is now a dynamic property - see get_tool_description()
    _base_description = (
        "Convert PDFs into LLM-ready formats using OpenDataLoader PDF. "
        "Fast, local, rule-based extraction with correct reading order and table detection. "
        "Requires Java 11 or later."
    )
    documentation = "https://opendataloader.org/"
    trace_type = "tool"
    icon = "OpenDataLoaderPDF"
    name = "OpenDataLoaderPDF"
    add_tool_output = True

    VALID_EXTENSIONS = ["pdf"]

    _base_inputs = deepcopy(BaseFileComponent.get_base_inputs())
    for _inp in _base_inputs:
        if isinstance(_inp, FileInput) and _inp.name == "path":
            _inp.tool_mode = False
            _inp.required = False
            break
    del _inp  # Prevent loop variable from leaking into class namespace

    inputs = [
        *_base_inputs,
        StrInput(
            name="file_path_str",
            display_name="File Path",
            info="Used internally for tool mode activation.",
            show=False,
            advanced=True,
            tool_mode=True,  # Required for Toolset toggle, but _get_tools() ignores this parameter
            required=False,
        ),
        DropdownInput(
            name="format",
            display_name="Output Format",
            info="The output format for the converted PDF content.",
            options=[
                "json",
                "text",
                "markdown",
                "markdown-with-html",
                "markdown-with-images",
                "html",
                "pdf",
            ],
            value="json",
        ),
        BoolInput(
            name="quiet",
            display_name="Quiet Mode",
            info="Suppress CLI logging output when enabled.",
            value=True,
            advanced=True,
        ),
        DropdownInput(
            name="content_safety",
            display_name="Content Safety",
            info=(
                "AI safety filters to protect against prompt injection. "
                "Enabled by default to filter hidden text, off-page content, and tiny text."
            ),
            options=["enabled", "disabled"],
            value="enabled",
            advanced=True,
        ),
        MultilineInput(
            name="content_safety_filters",
            display_name="Disabled Safety Filters",
            info=(
                "Comma-separated list of safety filters to disable when Content Safety is 'disabled'. "
                "Options: all, hidden-text, off-page, tiny, hidden-ocg"
            ),
            value="all",
            advanced=True,
        ),
        DropdownInput(
            name="image_output",
            display_name="Image Output",
            info=(
                "How to handle images in the PDF. "
                "'off' excludes images, 'embedded' includes Base64 in output, "
                "'external' saves images as separate files."
            ),
            options=["external", "embedded", "off"],
            value="external",
            advanced=True,
        ),
        DropdownInput(
            name="image_format",
            display_name="Image Format",
            info="Output format for extracted images.",
            options=["png", "jpeg"],
            value="png",
            advanced=True,
        ),
        BoolInput(
            name="use_struct_tree",
            display_name="Use Tagged PDF Structure",
            info=(
                "Use native PDF structure tags when available. "
                "Improves accuracy for accessible PDFs with semantic markup."
            ),
            value=True,
            advanced=True,
        ),
        SecretStrInput(
            name="password",
            display_name="PDF Password",
            info="Password for encrypted PDF files.",
            value="",
            advanced=True,
        ),
        StrInput(
            name="pages",
            display_name="Pages",
            info="Pages to extract (e.g., '1,3,5-7'). Leave empty for all pages.",
            value="",
            advanced=True,
        ),
        StrInput(
            name="replace_invalid_chars",
            display_name="Replace Invalid Characters",
            info="Replacement character for invalid or unrecognized characters in extracted text. Default is a space.",
            value=" ",
            advanced=True,
        ),
        BoolInput(
            name="keep_line_breaks",
            display_name="Keep Line Breaks",
            info="Preserve original line breaks in extracted text.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="include_header_footer",
            display_name="Include Header/Footer",
            info="Include page headers and footers in output.",
            value=False,
            advanced=True,
        ),
        DropdownInput(
            name="table_method",
            display_name="Table Detection Method",
            info="Method for detecting tables. 'cluster' may improve accuracy for borderless tables.",
            options=["default", "cluster"],
            value="default",
            advanced=True,
        ),
        DropdownInput(
            name="reading_order",
            display_name="Reading Order",
            info="Algorithm for determining reading order. 'xycut' handles multi-column layouts.",
            options=["xycut", "off"],
            value="xycut",
            advanced=True,
        ),
        StrInput(
            name="text_page_separator",
            display_name="Text Page Separator",
            info="Separator between pages in text output. Use %page-number% for page numbers.",
            value="",
            advanced=True,
        ),
        StrInput(
            name="markdown_page_separator",
            display_name="Markdown Page Separator",
            info="Separator between pages in Markdown output. Use %page-number% for page numbers.",
            value="",
            advanced=True,
        ),
        StrInput(
            name="html_page_separator",
            display_name="HTML Page Separator",
            info="Separator between pages in HTML output. Use %page-number% for page numbers.",
            value="",
            advanced=True,
        ),
        DropdownInput(
            name="hybrid",
            display_name="Hybrid Mode",
            info="Use AI backend for complex pages. 'docling-fast' routes challenging pages to AI processing.",
            options=["off", "docling-fast"],
            value="off",
            advanced=True,
        ),
        DropdownInput(
            name="hybrid_mode",
            display_name="Hybrid Triage Mode",
            info="How to decide which pages go to AI backend. 'auto' uses dynamic triage, 'full' sends all pages.",
            options=["auto", "full"],
            value="auto",
            advanced=True,
        ),
        StrInput(
            name="hybrid_url",
            display_name="Hybrid Backend URL",
            info="Custom URL for hybrid backend server. Leave empty to use the library default (http://localhost:5002).",
            value="",
            advanced=True,
        ),
        IntInput(
            name="hybrid_timeout",
            display_name="Hybrid Timeout (ms)",
            info="Timeout for hybrid backend requests in milliseconds.",
            value=30000,
            advanced=True,
        ),
        BoolInput(
            name="hybrid_fallback",
            display_name="Hybrid Fallback",
            info=(
                "Fall back to local processing if hybrid backend fails. "
                "When enabled, connection failures are handled silently and processing continues locally."
            ),
            value=True,
            advanced=True,
        ),
        StrInput(
            name="image_dir",
            display_name="Image Directory",
            info=(
                "Directory to save extracted images when Image Output is 'external'. "
                "Leave empty to save images alongside the output files."
            ),
            value="",
            advanced=True,
        ),
        StrInput(
            name="output_dir",
            display_name="Output Directory",
            info=(
                "Directory to save converted files. Leave empty to use a temporary directory (files are not persisted)."
            ),
            value="",
            advanced=True,
        ),
    ]

    outputs = [
        *BaseFileComponent.get_base_outputs(),
        Output(display_name="Pages", name="page_data", method="load_files_by_page"),
        Output(display_name="Text", name="text", method="load_files_message"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Instance-level cache so that multiple outputs (Files, Pages, Text, Tool)
        # do not trigger redundant PDF conversions.
        self._cached_data: list[Data] | None = None
        self._cached_page_data: list[Data] | None = None
        self._cache_lock = threading.RLock()

    # ------------------------------ Caching -----------------------------------------

    def _get_cached_data(self) -> list[Data]:
        """Return cached conversion results, running ``load_files_base()`` on first call.

        Multiple outputs (Files, Pages, Text, Tool) share the same converted data
        to avoid redundant PDF processing.  A lock ensures thread-safety when
        multiple outputs are resolved concurrently.
        """
        with self._cache_lock:
            if self._cached_data is None:
                self._cached_data = self.load_files_base()
            return self._cached_data

    def _get_cached_page_data(self) -> list[Data]:
        """Return cached page-level data, parsing on first call.

        Avoids redundant ``_parse_pages_from_data`` calls when multiple
        consumers (Pages output, ``read_pdf_page`` tool) need page data.
        """
        with self._cache_lock:
            if self._cached_page_data is None:
                self._cached_page_data = self._parse_pages_from_data(self._get_cached_data())
            return self._cached_page_data

    # ------------------------------ Page-level parsing ----------------------------

    def _parse_pages_from_data(self, data_list: list[Data]) -> list[Data]:
        """Split file-level Data objects into page-level Data objects.

        For JSON format: parses the ``kids`` array and groups elements by ``page number``.
        For text/markdown/html: splits on the injected sentinel ``---ODL_PAGE_BREAK_N---``.
        For pdf (binary): returns an empty list (page-level splitting not supported).

        Returns:
            list[Data]: One Data object per page with ``page_number``, ``total_pages``,
            ``source``, ``file_path``, and ``format`` fields.
        """
        page_data_list: list[Data] = []

        for data in data_list:
            content = data.data.get("text", "")
            source = data.data.get("source", "")
            file_path = data.data.get("file_path", "")
            fmt = data.data.get("format", self.format)

            if fmt == "json":
                page_data_list.extend(self._parse_pages_from_json(content, source=source, file_path=file_path, fmt=fmt))
            elif fmt == "pdf":
                # Binary output — cannot split by page
                continue
            else:
                page_data_list.extend(
                    self._parse_pages_from_sentinel(content, source=source, file_path=file_path, fmt=fmt)
                )

        return page_data_list

    def _parse_pages_from_json(self, content: str, *, source: str, file_path: str, fmt: str) -> list[Data]:
        """Extract per-page Data from opendataloader-pdf JSON output.

        The actual JSON structure uses a flat ``kids`` array where each element
        carries a ``page number`` field (space-separated key, 1-indexed).
        """
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return []

        total_pages = parsed.get("number of pages", 1)

        # Group element texts by page number
        pages_map: dict[int, list[str]] = defaultdict(list)
        for element in parsed.get("kids", []):
            page_num = element.get("page number", 1)
            text = element.get("content", "")
            if text:
                pages_map[page_num].append(text)

        result: list[Data] = []
        for page_num in sorted(pages_map.keys()):
            page_text = "\n".join(pages_map[page_num])
            result.append(
                Data(
                    data={
                        "text": page_text,
                        "page_number": page_num,
                        "total_pages": total_pages,
                        "source": source,
                        "file_path": file_path,
                        "format": fmt,
                    }
                )
            )
        return result

    def _parse_pages_from_sentinel(self, content: str, *, source: str, file_path: str, fmt: str) -> list[Data]:
        """Split text content on ``---ODL_PAGE_BREAK_N---`` sentinels.

        The sentinel is injected into the opendataloader-pdf page separator parameter
        during ``process_files()`` so that we can recover page boundaries later.

        The opendataloader-pdf library places the sentinel **before** each page's
        content, and ``%page-number%`` is the page number of the content that follows.
        So ``---ODL_PAGE_BREAK_1---`` means "page 1 starts here".
        """
        parts = _PAGE_SENTINEL_PATTERN.split(content)
        if len(parts) <= 1:
            # No sentinel found — treat entire content as page 1
            if content.strip():
                return [
                    Data(
                        data={
                            "text": content.strip(),
                            "page_number": 1,
                            "total_pages": 1,
                            "source": source,
                            "file_path": file_path,
                            "format": fmt,
                        }
                    )
                ]
            return []

        # re.split with a capturing group returns [text0, sep1, text1, sep2, text2, ...]
        # Even indices are text chunks, odd indices are captured page numbers.
        result: list[Data] = []
        page_texts: dict[int, list[str]] = defaultdict(list)

        # Collect all sentinel page numbers (including pages with empty text)
        # to determine total_pages accurately.
        all_sentinel_pages: list[int] = [int(parts[i]) for i in range(1, len(parts), 2)]

        preamble: str | None = None
        for i in range(0, len(parts), 2):
            text_chunk = parts[i].strip()
            if i == 0:
                # Text before the first sentinel — typically empty.
                # If non-empty, hold it as preamble to merge with the first page.
                if text_chunk:
                    preamble = text_chunk
            else:
                # The page number is in parts[i-1] (the captured group before this text).
                # The sentinel is placed BEFORE the page content and %page-number%
                # is the page number of the content that follows.
                page_num = int(parts[i - 1])
                if text_chunk:
                    page_texts[page_num].append(text_chunk)

        # Merge preamble into the first page (typically page 1) to avoid
        # creating duplicate entries for the same page number.
        if preamble:
            first_page = min(all_sentinel_pages, default=1)
            page_texts[first_page].insert(0, preamble)

        # Determine total pages from all sentinels (not just non-empty pages)
        # so that empty trailing pages are still counted.
        total_pages = max(all_sentinel_pages, default=1)

        for page_num in sorted(page_texts.keys()):
            combined = "\n".join(page_texts[page_num])
            result.append(
                Data(
                    data={
                        "text": combined,
                        "page_number": page_num,
                        "total_pages": total_pages,
                        "source": source,
                        "file_path": file_path,
                        "format": fmt,
                    }
                )
            )
        return result

    # ------------------------------ Pages output ----------------------------------

    def load_files_by_page(self) -> DataFrame:
        """Load files and return a DataFrame with one row per page.

        Each row contains: ``text``, ``page_number``, ``total_pages``, ``source``,
        ``file_path``, ``format``. Connect this output to **Split Text** for RAG
        pipelines with page-level citation support.
        """
        page_data = self._get_cached_page_data()
        if not page_data:
            return DataFrame()

        rows = [dict(d.data) for d in page_data]
        df = DataFrame(rows)
        self.status = df
        return df

    # ------------------------------ Message.files support ----------------------------

    def _file_path_as_list(self) -> list[Data]:
        """Override to extract file paths from Message.files when available.

        When an agent sends a Message with attached files, the file paths are
        in ``message.files`` rather than ``message.text``.  This override checks
        for that attribute first so dynamic PDF uploads work in chat / agent mode.
        """
        file_path = self.file_path
        if not file_path:
            return []

        def _extract_from_message(msg: Message) -> list[Data]:
            files = getattr(msg, "files", None) or []
            if files:
                return [Data(data={self.SERVER_FILE_PATH_FIELDNAME: f}) for f in files]
            # Fall back to message.text (backward-compatible)
            return [Data(data={self.SERVER_FILE_PATH_FIELDNAME: msg.text})]

        if isinstance(file_path, Message):
            return _extract_from_message(file_path)
        if isinstance(file_path, list):
            results: list[Data] = []
            for obj in file_path:
                if isinstance(obj, Message):
                    results.extend(_extract_from_message(obj))
                elif isinstance(obj, Data):
                    results.append(obj)
            return results
        if isinstance(file_path, Data):
            return [file_path]

        return super()._file_path_as_list()

    # ------------------------------ Cached output overrides ------------------------

    def load_files(self) -> DataFrame:
        """Load files and return as DataFrame, using the shared cache."""
        data_list = self._get_cached_data()
        if not data_list:
            return DataFrame()

        all_rows = []
        for data in data_list:
            row = dict(data.data) if data.data else {}
            all_rows.append(row)

        df = DataFrame(all_rows)
        self.status = df
        return df

    def load_files_message(self) -> Message:
        """Load files and return as Message, using the shared cache.

        Internal page sentinels (``---ODL_PAGE_BREAK_N---``) are stripped so that
        the Message text is clean for chatbot / LLM consumption.  Use the **Pages**
        output instead if you need per-page metadata.
        """
        data_list = self._get_cached_data()
        if not data_list:
            return Message()

        # Extract metadata from the first data item (matches base class behavior)
        metadata = self._extract_file_metadata(data_list[0])

        sep: str = getattr(self, "separator", "\n\n") or "\n\n"
        parts: list[str] = []
        for d in data_list:
            text = self._extract_text(d)
            if text:
                # Strip internal page sentinels that were injected for page-level
                # parsing.  These markers are an implementation detail and should
                # not leak into the user-facing Message output.
                text = _PAGE_SENTINEL_PATTERN.sub("", text).strip()
                if text:
                    parts.append(text)

        return Message(text=sep.join(parts), **metadata)

    # ------------------------------ Tool description with file names --------------

    def get_tool_description(self) -> str:
        """Return a dynamic description that includes the names of uploaded files.

        This helps the Agent understand which PDF files are available to process.
        """
        base_description = self._base_description

        file_paths = getattr(self, "path", None)
        if not file_paths:
            return base_description

        if not isinstance(file_paths, list):
            file_paths = [file_paths]

        file_names = [Path(str(fp)).name for fp in file_paths if fp]

        if file_names:
            files_str = ", ".join(file_names)
            return (
                f"{base_description} Available PDF files: {files_str}. Call this tool to extract text from these PDFs."
            )

        return base_description

    @property
    def description(self) -> str:
        """Dynamic description property that includes uploaded file names."""
        return self.get_tool_description()

    @description.setter
    def description(self, _value: str) -> None:
        """Accept but ignore external writes to keep the property dynamic."""

    async def _get_tools(self) -> list:
        """Create agent tools for PDF reading.

        Two tools are exposed:
        1. ``read_pdf`` — extract full text from all uploaded PDFs (no parameters).
        2. ``read_pdf_page`` — extract text from a specific page (takes ``page_number``).
        """
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, Field

        description = self.get_tool_description()

        # ---- Tool 1: read_pdf (full text, no parameters) ----

        class EmptySchema(BaseModel):
            """No parameters required - uses pre-uploaded files."""

        async def read_pdf_tool() -> str:
            """Extract all text from uploaded PDF files."""
            try:
                data_list = self._get_cached_data()
                if not data_list:
                    return "No text extracted from the PDF files."
                parts = [d.data.get("text", "") for d in data_list]
                return "\n\n".join(p for p in parts if p) or "No text extracted."
            except (FileNotFoundError, ValueError, OSError, RuntimeError, ImportError) as e:
                return f"Error processing PDF files: {e}"

        tool_read_pdf = StructuredTool(
            name="read_pdf",
            description=f"{description} Returns the full text of all pages.",
            coroutine=read_pdf_tool,
            args_schema=EmptySchema,
            handle_tool_error=True,
            tags=["read_pdf"],
            metadata={
                "display_name": "OpenDataLoader PDF - Read All",
                "display_description": description,
            },
        )

        # ---- Tool 2: read_pdf_page (specific page) ----

        class PageSchema(BaseModel):
            """Parameters for reading a specific page from a PDF."""

            page_number: int = Field(description="Page number to extract (1-based)")

        async def read_pdf_page_tool(page_number: int) -> str:
            """Extract text from a specific page of the uploaded PDF files."""
            try:
                page_data = self._get_cached_page_data()
                matching = [p for p in page_data if p.data.get("page_number") == page_number]
                if matching:
                    return matching[0].get_text()
                if page_data:
                    available = sorted({p.data.get("page_number", 0) for p in page_data})
                    return f"Page {page_number} not found. Available pages: {available}"
                return f"Page {page_number} not found. No pages could be extracted."  # noqa: TRY300
            except (FileNotFoundError, ValueError, OSError, RuntimeError, ImportError) as e:
                return f"Error reading page {page_number}: {e}"

        tool_read_page = StructuredTool(
            name="read_pdf_page",
            description=(
                f"{description} Extract text from a specific page by number. "
                "Useful for detailed analysis or citation of particular pages."
            ),
            coroutine=read_pdf_page_tool,
            args_schema=PageSchema,
            handle_tool_error=True,
            tags=["read_pdf_page"],
            metadata={
                "display_name": "OpenDataLoader PDF - Read Page",
                "display_description": "Extract text from a specific page",
            },
        )

        return [tool_read_pdf, tool_read_page]

    # ------------------------------ Internal helpers --------------------------------

    _MIN_JAVA_VERSION = 11

    def _check_java_installed(self) -> bool:
        """Check if Java 11 or later is installed and available."""
        try:
            result = subprocess.run(
                ["java", "-version"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            # Java version info is typically in stderr
            version_output = result.stderr or result.stdout
            if result.returncode != 0 or not version_output:
                return False

            # Parse the major version number from output like:
            #   openjdk version "17.0.2" ...   or   java version "1.8.0_351" ...
            match = re.search(r'version "(\d+)(?:\.(\d+))?', version_output)
            if not match:
                return False

            major = int(match.group(1))
            # Java 8 and earlier used "1.x" versioning (e.g. "1.8" = Java 8)
            if major == 1:
                major = int(match.group(2)) if match.group(2) else major
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return False
        else:
            return major >= self._MIN_JAVA_VERSION

    _VALID_SAFETY_FILTERS = {"all", "hidden-text", "off-page", "tiny", "hidden-ocg"}

    def _get_content_safety_off(self) -> list[str] | None:
        """Get the list of content safety filters to disable."""
        if self.content_safety == "enabled":
            return None

        filters = self.content_safety_filters.strip()
        if not filters:
            return ["all"]

        result = [f.strip() for f in filters.split(",") if f.strip()]
        invalid = [f for f in result if f not in self._VALID_SAFETY_FILTERS]
        if invalid:
            self.log(
                f"Warning: unknown content safety filter(s): {invalid}. "
                f"Valid options: {sorted(self._VALID_SAFETY_FILTERS)}"
            )
        return result

    def _count_total_pages(self, content: str, *, parsed_json: dict | None = None, fmt: str | None = None) -> int:
        """Infer total page count from converted content.

        For JSON: reads ``"number of pages"`` from *parsed_json* if supplied,
        otherwise falls back to parsing *content*.  Callers that already hold a
        parsed dict should pass it via *parsed_json* to avoid a redundant
        ``json.loads`` call on large documents.

        For text/markdown/html: counts sentinel occurrences (one per page).

        Args:
            content: The converted file content string.
            parsed_json: Pre-parsed JSON dict to avoid redundant ``json.loads``.
            fmt: Output format to use for branching.  Falls back to ``self.format``
                 when not provided, for backward compatibility.
        """
        effective_fmt = fmt or self.format
        if effective_fmt == "json":
            if parsed_json is not None:
                try:
                    return int(parsed_json.get("number of pages", 1))
                except (TypeError, ValueError):
                    return 1
            try:
                parsed = json.loads(content)
                return int(parsed.get("number of pages", 1))
            except (json.JSONDecodeError, TypeError, ValueError):
                return 1

        if effective_fmt == "pdf":
            # Binary (base64) output — page-level splitting is not supported,
            # so we cannot infer the page count from content alone.
            return 1

        # For sentinel-split formats: use the maximum page number from sentinels.
        # This is consistent with JSON format (which reports actual PDF page count)
        # and with _parse_pages_from_sentinel() which uses max(page_numbers).
        matches = _PAGE_SENTINEL_PATTERN.findall(content)
        return max((int(m) for m in matches), default=1) if matches else 1

    def _compute_word_count(self, content: str, *, parsed_json: dict | None = None, fmt: str | None = None) -> int:
        """Count words in the actual document text, regardless of output format.

        For JSON: extracts ``content`` fields from the ``kids`` array.
        For PDF (base64): returns 0 (binary data has no meaningful word count).
        For text/markdown/html: strips sentinel markers before counting.

        Args:
            content: The converted file content string.
            parsed_json: Pre-parsed JSON dict to avoid redundant ``json.loads``.
            fmt: Output format to use for branching.  Falls back to ``self.format``
                 when not provided, for backward compatibility.
        """
        effective_fmt = fmt or self.format
        if effective_fmt == "pdf":
            return 0

        if effective_fmt == "json":
            parsed = parsed_json
            if parsed is None:
                try:
                    parsed = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    return 0
            texts = [el.get("content", "") for el in parsed.get("kids", []) if el.get("content")]
            return len(" ".join(texts).split())

        # text/markdown/html: strip sentinels before counting
        clean = _PAGE_SENTINEL_PATTERN.sub(" ", content)
        return len(clean.split())

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        """Process PDF files using OpenDataLoader PDF."""
        # Check for opendataloader_pdf package
        try:
            import opendataloader_pdf
        except ImportError as e:
            msg = (
                "opendataloader-pdf is not installed. "
                "Install with `pip install -U opendataloader-pdf` or "
                "`uv pip install opendataloader-pdf`."
            )
            raise ImportError(msg) from e

        # Check for Java
        if not self._check_java_installed():
            msg = (
                "Java 11 or later is required but not found. "
                "Please install Java from https://adoptium.net/ or your system's package manager. "
                "After installation, ensure 'java' is available in your system PATH."
            )
            raise RuntimeError(msg)

        file_paths = [file.path for file in file_list if file.path]

        if not file_paths:
            self.log("No files to process.")
            return file_list

        # Determine file extension based on format
        format_to_ext = {
            "json": "json",
            "text": "txt",
            "html": "html",
            "markdown": "md",
            "markdown-with-html": "md",
            "markdown-with-images": "md",
            "pdf": "pdf",
        }
        ext = format_to_ext.get(self.format, "txt")

        processed_data: list[Data | None] = []
        temp_dirs: list[str] = []

        use_custom_output_dir = bool(self.output_dir and self.output_dir.strip())

        try:
            for file_path in file_paths:
                try:
                    # Use user-specified directory or create a temporary one
                    if use_custom_output_dir:
                        output_dir = self.output_dir.strip()
                        Path(output_dir).mkdir(parents=True, exist_ok=True)
                    else:
                        output_dir = tempfile.mkdtemp()
                        temp_dirs.append(output_dir)

                    # Build convert parameters
                    convert_params = {
                        "input_path": str(file_path),
                        "output_dir": output_dir,
                        "format": [self.format],
                        "quiet": self.quiet,
                        "image_output": self.image_output,
                        "image_format": self.image_format,
                        "use_struct_tree": self.use_struct_tree,
                        "replace_invalid_chars": self.replace_invalid_chars,
                        "keep_line_breaks": self.keep_line_breaks,
                        "include_header_footer": self.include_header_footer,
                        "table_method": self.table_method,
                        "reading_order": self.reading_order,
                    }

                    # Only pass content_safety_off when filters are actually disabled
                    content_safety_off = self._get_content_safety_off()
                    if content_safety_off is not None:
                        convert_params["content_safety_off"] = content_safety_off

                    # Only pass image_dir when explicitly set
                    if self.image_dir and self.image_dir.strip():
                        convert_params["image_dir"] = self.image_dir.strip()

                    # Add optional string parameters (only if not empty)
                    if self.password:
                        convert_params["password"] = self.password
                    if self.pages:
                        convert_params["pages"] = self.pages
                    if self.text_page_separator:
                        convert_params["text_page_separator"] = self.text_page_separator
                    if self.markdown_page_separator:
                        convert_params["markdown_page_separator"] = self.markdown_page_separator
                    if self.html_page_separator:
                        convert_params["html_page_separator"] = self.html_page_separator

                    # Inject page sentinel for text/markdown/html formats when the user
                    # has not already set a page separator.  This enables the Pages
                    # output to split content by page with page_number metadata.
                    # Note: JSON and PDF formats are intentionally absent from
                    # _FORMAT_TO_SEPARATOR_KEY — JSON uses the "kids" array for page
                    # parsing, and PDF is binary output with no page separator support.
                    separator_key = _FORMAT_TO_SEPARATOR_KEY.get(self.format)
                    if separator_key and not convert_params.get(separator_key):
                        convert_params[separator_key] = _PAGE_SENTINEL_TEMPLATE

                    if self.hybrid != "off":
                        convert_params["hybrid"] = self.hybrid
                        convert_params["hybrid_mode"] = self.hybrid_mode
                        convert_params["hybrid_fallback"] = self.hybrid_fallback
                        hybrid_target = self.hybrid_url or "http://localhost:5002 (default)"
                        self.log(
                            f"Hybrid mode enabled: backend={self.hybrid}, "
                            f"triage={self.hybrid_mode}, url={hybrid_target}, "
                            f"fallback={'enabled' if self.hybrid_fallback else 'disabled'}"
                        )
                        if self.hybrid_url:
                            convert_params["hybrid_url"] = self.hybrid_url
                        if self.hybrid_timeout:
                            # opendataloader-pdf CLI expects timeout as a string value
                            convert_params["hybrid_timeout"] = str(self.hybrid_timeout)

                    # Convert PDF using opendataloader_pdf
                    opendataloader_pdf.convert(**convert_params)

                    # Find and read the output file.
                    # Prefer the exact expected filename (input stem + format ext)
                    # to avoid picking a stale file from a previous iteration when
                    # the user specified a custom output_dir for multiple files.
                    output_path = Path(output_dir)
                    expected_output = output_path / f"{file_path.stem}.{ext}"
                    if expected_output.exists():
                        output_files = [expected_output]
                    else:
                        # Sort by modification time (newest first) to avoid picking
                        # a stale file when the output directory is shared.
                        output_files = sorted(
                            output_path.glob(f"*.{ext}"), key=lambda p: p.stat().st_mtime, reverse=True
                        )

                    if output_files:
                        if self.format == "pdf":
                            import base64

                            with output_files[0].open("rb") as f:
                                content = base64.b64encode(f.read()).decode("ascii")
                        else:
                            with output_files[0].open(encoding="utf-8") as f:
                                content = f.read()

                        # For JSON format, parse once and reuse the dict for
                        # _count_total_pages to avoid a redundant json.loads.
                        pre_parsed: dict | None = None
                        if self.format == "json":
                            with contextlib.suppress(json.JSONDecodeError, TypeError):
                                pre_parsed = json.loads(content)

                        total_pages = self._count_total_pages(content, parsed_json=pre_parsed)

                        # Compute word count from actual document text, not raw format output.
                        # JSON content contains syntax tokens; PDF content is base64-encoded.
                        word_count = self._compute_word_count(content, parsed_json=pre_parsed)

                        processed_data.append(
                            Data(
                                data={
                                    "text": content,
                                    "file_path": str(file_path),
                                    "format": self.format,
                                    "source": file_path.name,
                                    "total_pages": total_pages,
                                    "word_count": word_count,
                                }
                            )
                        )
                    else:
                        self.log(f"No output file generated for {file_path}")
                        processed_data.append(None)

                except (
                    subprocess.SubprocessError,
                    OSError,
                    ValueError,
                    RuntimeError,
                    json.JSONDecodeError,
                    TypeError,
                ) as e:
                    self.log(f"Error processing {file_path}: {e}")
                    if not self.silent_errors:
                        raise
                    processed_data.append(None)

        finally:
            # Clean up temporary directories
            for temp_dir in temp_dirs:
                try:
                    shutil.rmtree(temp_dir)
                except OSError as e:
                    self.log(f"Error cleaning up temp directory: {e}")

        return self.rollup_data(file_list, processed_data)
