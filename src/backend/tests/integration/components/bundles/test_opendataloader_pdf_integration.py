"""OpenDataLoader PDF integration tests.

Validates PDF conversion using the real opendataloader_pdf library and Java.
Automatically skipped in environments where opendataloader-pdf or Java is not installed.

Usage:
    pytest src/backend/tests/integration/components/bundles/test_opendataloader_pdf_integration.py -v
"""

import base64
import json
import re
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from lfx.components.opendataloader_pdf.opendataloader_pdf import OpenDataLoaderPDFComponent
from lfx.schema import Data

# ---------------------------------------------------------------------------
# Environment check: both opendataloader-pdf package and Java are required.
# ---------------------------------------------------------------------------

try:
    import opendataloader_pdf  # noqa: F401

    HAS_OPENDATALOADER = True
except ImportError:
    HAS_OPENDATALOADER = False


def _java_available() -> bool:
    """Check if Java 11 or later is installed on the system."""
    if not shutil.which("java"):
        return False
    try:
        result = subprocess.run(
            ["java", "-version"],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
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
        return major >= 11


HAS_JAVA = _java_available()

SKIP_REASON = (
    "Requires opendataloader-pdf package and Java 11+. "
    "Install: pip install -U opendataloader-pdf  /  Java: https://adoptium.net/"
)

requires_opendataloader = pytest.mark.skipif(
    not (HAS_OPENDATALOADER and HAS_JAVA),
    reason=SKIP_REASON,
)

# ---------------------------------------------------------------------------
# Valid PDF bytes (contains text "Hello World", "This is a test PDF document.")
# Embedded as base64 encoding with correct xref offsets for a valid PDF.
# ---------------------------------------------------------------------------

_MINIMAL_PDF_BASE64 = (
    "JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2JqCjIgMCBvYmoK"
    "PDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2JqCjMgMCBvYmoKPDwgL1R5cGUg"
    "L1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIgNzkyXSAvQ29udGVudHMgNCAwIFIgL1Jlc291cm"
    "NlcyA8PCAvRm9udCA8PCAvRjEgNSAwIFIgPj4gPj4gPj4KZW5kb2JqCjQgMCBvYmoKPDwgL0xlbmd0aCA4NiA+Pgpz"
    "dHJlYW0KQlQgL0YxIDI0IFRmIDEwMCA3MDAgVGQgKEhlbGxvIFdvcmxkKSBUaiAwIC0zMCBUZCAoVGhpcyBpcyBhIH"
    "Rlc3QgUERGIGRvY3VtZW50LikgVGogRVQKZW5kc3RyZWFtCmVuZG9iago1IDAgb2JqCjw8IC9UeXBlIC9Gb250IC9T"
    "dWJ0eXBlIC9UeXBlMSAvQmFzZUZvbnQgL0hlbHZldGljYSA+PgplbmRvYmoKeHJlZgowIDYKMDAwMDAwMDAwMCA2NT"
    "UzNSBmIAowMDAwMDAwMDA5IDAwMDAwIG4gCjAwMDAwMDAwNTggMDAwMDAgbiAKMDAwMDAwMDExNSAwMDAwMCBuIAow"
    "MDAwMDAwMjQxIDAwMDAwIG4gCjAwMDAwMDAzNzcgMDAwMDAgbiAKdHJhaWxlcgo8PCAvU2l6ZSA2IC9Sb290IDEgMC"
    "BSID4+CnN0YXJ0eHJlZgo0NDcKJSVFT0YK"
)
MINIMAL_PDF_BYTES = base64.b64decode(_MINIMAL_PDF_BASE64)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def real_pdf(tmp_path):
    """Create a minimal valid PDF file containing "Hello World" text."""
    pdf_path = tmp_path / "hello.pdf"
    pdf_path.write_bytes(MINIMAL_PDF_BYTES)
    return pdf_path


@pytest.fixture
def default_kwargs():
    """Return default component settings."""
    return {
        "path": [],
        "file_path_str": "",
        "format": "text",
        "quiet": True,
        "content_safety": "enabled",
        "content_safety_filters": "all",
        "image_output": "off",
        "image_format": "png",
        "use_struct_tree": True,
        "password": "",
        "pages": "",
        "replace_invalid_chars": " ",
        "keep_line_breaks": False,
        "include_header_footer": False,
        "table_method": "default",
        "reading_order": "xycut",
        "text_page_separator": "",
        "markdown_page_separator": "",
        "html_page_separator": "",
        "hybrid": "off",
        "hybrid_mode": "auto",
        "hybrid_url": "",
        "hybrid_timeout": 30000,
        "hybrid_fallback": True,
        "silent_errors": False,
        "image_dir": "",
        "output_dir": "",
    }


def _make_base_file(pdf_path: Path):
    """Create a real BaseFile object (using actual object instead of Mock)."""
    data = Data(data={"file_path": str(pdf_path)})
    return OpenDataLoaderPDFComponent.BaseFile(data=data, path=pdf_path)


def _make_component(default_kwargs, **overrides):
    """Create a component instance with the given settings."""
    component = OpenDataLoaderPDFComponent()
    component.set_attributes({**default_kwargs, **overrides})
    component.log = Mock()
    return component


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@requires_opendataloader
class TestOpenDataLoaderPDFIntegration:
    """Integration tests using the real opendataloader-pdf library.

    These tests convert actual PDF files with the real library
    to validate end-to-end behavior.
    """

    def test_real_java_check_passes(self, default_kwargs):
        """Verify _check_java_installed() returns True when Java is available."""
        component = _make_component(default_kwargs)
        assert component._check_java_installed() is True

    def test_real_convert_text_format(self, real_pdf, default_kwargs):
        """Convert a real PDF to text format and verify text is extracted."""
        component = _make_component(default_kwargs, format="text")
        base_file = _make_base_file(real_pdf)

        result = component.process_files([base_file])

        assert len(result) == 1
        text = result[0].data[0].data.get("text", "")
        assert len(text) > 0, "Converted text should not be empty"
        assert "Hello" in text, "'Hello' text from the PDF should be extracted"

    def test_real_convert_markdown_format(self, real_pdf, default_kwargs):
        """Convert a real PDF to markdown format and verify non-empty result."""
        component = _make_component(default_kwargs, format="markdown")
        base_file = _make_base_file(real_pdf)

        result = component.process_files([base_file])

        assert len(result) == 1
        text = result[0].data[0].data.get("text", "")
        assert len(text) > 0, "Markdown conversion result should not be empty"

    def test_real_convert_json_format(self, real_pdf, default_kwargs):
        """Convert a real PDF to JSON format and verify valid JSON output."""
        component = _make_component(default_kwargs, format="json")
        base_file = _make_base_file(real_pdf)

        result = component.process_files([base_file])

        assert len(result) == 1
        text = result[0].data[0].data.get("text", "")
        # Should be parseable as JSON
        parsed = json.loads(text)
        assert isinstance(parsed, (dict, list)), "JSON result should be a dict or list"

    def test_real_convert_html_format(self, real_pdf, default_kwargs):
        """Convert a real PDF to HTML format and verify HTML tags are present."""
        component = _make_component(default_kwargs, format="html")
        base_file = _make_base_file(real_pdf)

        result = component.process_files([base_file])

        assert len(result) == 1
        text = result[0].data[0].data.get("text", "")
        assert "<" in text, "HTML result should contain opening tags"
        assert ">" in text, "HTML result should contain closing tags"

    def test_real_multi_file_processing(self, tmp_path, default_kwargs):
        """Verify that multiple PDF files can be processed at once."""
        # Create 2 PDF files
        pdf1 = tmp_path / "file1.pdf"
        pdf2 = tmp_path / "file2.pdf"
        pdf1.write_bytes(MINIMAL_PDF_BYTES)
        pdf2.write_bytes(MINIMAL_PDF_BYTES)

        component = _make_component(default_kwargs, format="text")
        base_files = [_make_base_file(pdf1), _make_base_file(pdf2)]

        result = component.process_files(base_files)

        assert len(result) == 2, "Processing 2 files should produce 2 results"
        for i, bf in enumerate(result):
            text = bf.data[0].data.get("text", "")
            assert len(text) > 0, f"File {i + 1} conversion result should not be empty"

    def test_real_output_dir_persists_files(self, real_pdf, default_kwargs, tmp_path):
        """Verify that converted files remain in the specified output directory."""
        output_dir = tmp_path / "my_output"

        component = _make_component(
            default_kwargs,
            format="text",
            output_dir=str(output_dir),
        )
        base_file = _make_base_file(real_pdf)

        component.process_files([base_file])

        # Output files should exist in the specified directory
        assert output_dir.exists(), "Output directory should be created"
        output_files = list(output_dir.glob("*.txt"))
        assert len(output_files) > 0, "Output directory should contain .txt files"

    def test_real_pages_selection(self, real_pdf, default_kwargs):
        """Verify that specific pages can be extracted using the pages parameter."""
        component = _make_component(default_kwargs, format="text", pages="1")
        base_file = _make_base_file(real_pdf)

        result = component.process_files([base_file])

        assert len(result) == 1
        text = result[0].data[0].data.get("text", "")
        assert len(text) > 0, "Page 1 extraction result should not be empty"

    # ------------------------------ Page-level & metadata tests -------------------

    def test_real_json_structure_has_kids_and_page_number(self, real_pdf, default_kwargs):
        """Verify that real JSON output contains kids array and page number fields."""
        component = _make_component(default_kwargs, format="json")
        base_file = _make_base_file(real_pdf)

        result = component.process_files([base_file])

        assert len(result) == 1
        text = result[0].data[0].data.get("text", "")
        parsed = json.loads(text)

        # Verify structure: kids array exists
        assert "kids" in parsed, "JSON output should contain a 'kids' array"
        assert isinstance(parsed["kids"], list)

        # number of pages exists
        assert "number of pages" in parsed, "JSON output should contain 'number of pages'"
        assert parsed["number of pages"] >= 1

        # Each element in kids array should have page number
        for element in parsed["kids"]:
            if element.get("content"):
                assert "page number" in element, f"Element should have 'page number': {element}"

    def test_real_metadata_total_pages_and_word_count(self, real_pdf, default_kwargs):
        """Verify that total_pages and word_count metadata are present after conversion."""
        component = _make_component(default_kwargs, format="text")
        base_file = _make_base_file(real_pdf)

        result = component.process_files([base_file])

        data = result[0].data[0]
        assert "total_pages" in data.data, "total_pages field should be present"
        assert data.data["total_pages"] >= 1
        assert "word_count" in data.data, "word_count field should be present"
        assert data.data["word_count"] > 0

    def test_real_parse_pages_from_json(self, real_pdf, default_kwargs):
        """Verify that per-page Data objects can be created from real JSON output."""
        component = _make_component(default_kwargs, format="json")
        base_file = _make_base_file(real_pdf)

        result = component.process_files([base_file])
        data_list = [d for bf in result for d in bf.data]

        pages = component._parse_pages_from_data(data_list)

        # Should have at least 1 page
        assert len(pages) >= 1, "Should have at least 1 page"
        for page in pages:
            assert "page_number" in page.data
            assert "total_pages" in page.data
            assert "source" in page.data
            assert page.data["page_number"] >= 1

    def test_real_text_with_sentinel_page_split(self, real_pdf, default_kwargs):
        """Verify that sentinel is injected in text format for page splitting."""
        # Leaving text_page_separator empty triggers automatic sentinel injection
        component = _make_component(default_kwargs, format="text", text_page_separator="")
        base_file = _make_base_file(real_pdf)

        result = component.process_files([base_file])
        data_list = [d for bf in result for d in bf.data]

        pages = component._parse_pages_from_data(data_list)

        # 1-page PDF should have at least 1 page
        assert len(pages) >= 1
        assert pages[0].data["page_number"] == 1

    def test_real_load_files_by_page_returns_dataframe(self, real_pdf, default_kwargs):
        """Verify load_files_by_page() returns a DataFrame with page-level rows end-to-end."""
        component = _make_component(default_kwargs, format="text", path=[str(real_pdf)])

        # Pre-populate cache by running the conversion
        base_file = _make_base_file(real_pdf)
        result = component.process_files([base_file])
        data_list = [d for bf in result for d in bf.data]
        component._cached_data = data_list

        df = component.load_files_by_page()

        assert len(df) >= 1, "Should have at least 1 page row"
        assert "page_number" in df.columns
        assert "total_pages" in df.columns
        assert "text" in df.columns
        assert "source" in df.columns
        # Verify page numbers are valid
        for _, row in df.iterrows():
            assert row["page_number"] >= 1
            assert row["total_pages"] >= 1
            assert len(row["text"]) > 0
