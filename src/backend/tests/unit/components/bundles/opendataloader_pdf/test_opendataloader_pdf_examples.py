"""OpenDataLoader PDF beginner guide tests.

This file provides step-by-step example-style tests that demonstrate
how to use the OpenDataLoader PDF component. Written so that developers
new to the component can read the code and understand its behavior.

Each test follows this structure:
  Step 1: Create the component
  Step 2: Configure settings
  Step 3: Call the method
  Step 4: Verify results
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from lfx.components.opendataloader_pdf.opendataloader_pdf import OpenDataLoaderPDFComponent
from lfx.schema import Data

# ---------------------------------------------------------------------------
# Helper functions: simplify repetitive setup across tests.
# ---------------------------------------------------------------------------


def create_mock_converter(write_callback):
    """Create a mock of the opendataloader_pdf module.

    Args:
        write_callback: A function that creates the output file when convert is called.
            Signature: callback(output_dir: str, input_path: str)

    Returns:
        A mock module containing a convert() function.

    Example usage::

        def my_callback(output_dir, input_path):
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            (Path(output_dir) / "result.txt").write_text("Extracted text", encoding="utf-8")

        mock_module = create_mock_converter(my_callback)
    """
    mock_module = MagicMock()

    def mock_convert(**kwargs):
        write_callback(kwargs["output_dir"], kwargs["input_path"])

    mock_module.convert = mock_convert
    return mock_module


def make_base_file(pdf_path: Path) -> OpenDataLoaderPDFComponent.BaseFile:
    """Create a real BaseFile object (using actual object instead of Mock).

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        A BaseFile object that can be passed to process_files().
    """
    data = Data(data={"file_path": str(pdf_path)})
    return OpenDataLoaderPDFComponent.BaseFile(data=data, path=pdf_path)


# Default settings used across all tests
DEFAULT_SETTINGS = {
    "path": [],
    "file_path_str": "",
    "format": "text",
    "quiet": True,
    "content_safety": "enabled",
    "content_safety_filters": "all",
    "image_output": "external",
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


# ---------------------------------------------------------------------------
# Example tests
# ---------------------------------------------------------------------------


class TestOpenDataLoaderPDFExamples:
    """OpenDataLoader PDF usage examples for beginners.

    Each test can be run independently and demonstrates
    one core feature of the component.
    """

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_example_convert_single_pdf_to_text(self, _mock_java, tmp_path):
        """Example 1: Convert a single PDF file to text.

        The most basic usage.
        Input a PDF file and text is extracted.
        """
        # Step 1: Prepare a test PDF file
        pdf_file = tmp_path / "report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        # Step 2: Set up mock to create output files
        output_dir = tmp_path / "output"

        def write_text_output(out_dir, _input_path):
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            (Path(out_dir) / "report.txt").write_text("This is the text extracted from the PDF.", encoding="utf-8")

        mock_module = create_mock_converter(write_text_output)

        # Step 3: Create and configure the component
        component = OpenDataLoaderPDFComponent()
        component.set_attributes({**DEFAULT_SETTINGS, "format": "text"})
        component.log = Mock()

        # Step 4: Run PDF conversion
        base_file = make_base_file(pdf_file)
        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_module}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files([base_file])

        # Step 5: Verify results
        assert len(result) == 1, "1 input -> 1 result"
        extracted_text = result[0].data[0].data["text"]
        assert "extracted from the PDF" in extracted_text

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_example_convert_pdf_to_markdown(self, _mock_java, tmp_path):
        """Example 2: Convert a PDF to markdown format.

        Setting format="markdown" preserves structure like headings and tables.
        """
        # Prepare a PDF file
        pdf_file = tmp_path / "document.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        output_dir = tmp_path / "output"

        def write_markdown_output(out_dir, _input_path):
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            (Path(out_dir) / "document.md").write_text(
                "# Document Title\n\nBody content.\n\n| Col1 | Col2 |\n|------|------|\n| A | B |",
                encoding="utf-8",
            )

        mock_module = create_mock_converter(write_markdown_output)

        # Set format to "markdown"
        component = OpenDataLoaderPDFComponent()
        component.set_attributes({**DEFAULT_SETTINGS, "format": "markdown"})
        component.log = Mock()

        base_file = make_base_file(pdf_file)
        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_module}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files([base_file])

        # Verify markdown heading is included
        text = result[0].data[0].data["text"]
        assert "# Document Title" in text
        assert "| Col1 | Col2 |" in text

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_example_multi_file_batch_processing(self, _mock_java, tmp_path):
        """Example 3: Process multiple PDFs at once.

        Passing multiple BaseFile objects to process_files()
        processes all files sequentially.
        """
        # Prepare 2 PDF files
        pdf1 = tmp_path / "chapter1.pdf"
        pdf2 = tmp_path / "chapter2.pdf"
        pdf1.write_bytes(b"%PDF-1.4 chapter 1")
        pdf2.write_bytes(b"%PDF-1.4 chapter 2")

        # Each file gets a unique output directory to avoid filename collisions
        output_dirs = [str(tmp_path / f"output_{i}") for i in range(2)]
        mkdtemp_calls = iter(output_dirs)

        def write_output_per_file(out_dir, input_path):
            """Create a separate output file for each input file."""
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            filename = Path(input_path).stem + ".txt"
            content = f"Content from {Path(input_path).stem}"
            (Path(out_dir) / filename).write_text(content, encoding="utf-8")

        mock_module = create_mock_converter(write_output_per_file)

        component = OpenDataLoaderPDFComponent()
        component.set_attributes({**DEFAULT_SETTINGS, "format": "text"})
        component.log = Mock()

        base_files = [make_base_file(pdf1), make_base_file(pdf2)]
        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_module}),
            patch("tempfile.mkdtemp", side_effect=lambda: next(mkdtemp_calls)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files(base_files)

        # Verify both files were processed
        assert len(result) == 2, "2 inputs -> 2 results"

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_example_custom_output_directory(self, _mock_java, tmp_path):
        """Example 4: Specify a custom output directory.

        Setting output_dir saves converted files to the specified path
        and they are not automatically deleted.
        """
        pdf_file = tmp_path / "data.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 data")

        # Specify the desired output path
        custom_output = tmp_path / "my_results"

        def write_output(out_dir, _input_path):
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            (Path(out_dir) / "data.txt").write_text("Converted result", encoding="utf-8")

        mock_module = create_mock_converter(write_output)

        component = OpenDataLoaderPDFComponent()
        component.set_attributes(
            {
                **DEFAULT_SETTINGS,
                "format": "text",
                "output_dir": str(custom_output),  # Specify output path
            }
        )
        component.log = Mock()

        base_file = make_base_file(pdf_file)
        with patch.dict(sys.modules, {"opendataloader_pdf": mock_module}):
            result = component.process_files([base_file])

        # Verify output files exist in the specified directory
        assert custom_output.exists()
        assert len(result) == 1

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_example_silent_errors_skip_bad_file(self, _mock_java, tmp_path):
        """Example 5: Continue processing even when errors occur.

        Setting silent_errors=True skips files that fail to convert
        and continues processing the remaining files.
        """
        pdf_file = tmp_path / "broken.pdf"
        pdf_file.write_bytes(b"this is not a real PDF")

        def convert_raises_error(_out_dir, _input_path):
            msg = "PDF parsing failed"
            raise RuntimeError(msg)

        mock_module = create_mock_converter(convert_raises_error)

        component = OpenDataLoaderPDFComponent()
        component.set_attributes(
            {
                **DEFAULT_SETTINGS,
                "silent_errors": True,  # Suppress errors mode
            }
        )
        component.log = Mock()

        base_file = make_base_file(pdf_file)
        with patch.dict(sys.modules, {"opendataloader_pdf": mock_module}):
            # No exception is raised because silent_errors=True
            result = component.process_files([base_file])

        assert len(result) == 1, "Result list is returned even when errors occur"

    def test_example_content_safety_configuration(self):
        """Example 6: Configure AI safety filters.

        content_safety="enabled" (default): All safety filters are active.
        content_safety="disabled": Disables the specified filters.
        """
        component = OpenDataLoaderPDFComponent()

        # Default: all filters enabled
        component.set_attributes(
            {
                **DEFAULT_SETTINGS,
                "content_safety": "enabled",
            }
        )
        assert component._get_content_safety_off() is None, "enabled -> no filters disabled (returns None)"

        # Disable all filters
        component.set_attributes(
            {
                **DEFAULT_SETTINGS,
                "content_safety": "disabled",
                "content_safety_filters": "all",
            }
        )
        assert component._get_content_safety_off() == ["all"], "'all' disables all filters"

        # Disable specific filters only
        component.set_attributes(
            {
                **DEFAULT_SETTINGS,
                "content_safety": "disabled",
                "content_safety_filters": "hidden-text, tiny",
            }
        )
        result = component._get_content_safety_off()
        assert result == ["hidden-text", "tiny"], "Comma-separated filter names are converted to a list"

    def test_example_tool_description_with_filenames(self):
        """Example 7: Verify file names are included in tool description for Agent mode.

        When an Agent uses this component as a tool,
        uploaded PDF file names are included in the tool description
        so the Agent knows which files are available for processing.
        """
        component = OpenDataLoaderPDFComponent()

        # No files: returns base description only
        component.set_attributes({**DEFAULT_SETTINGS, "path": []})
        desc_no_files = component.get_tool_description()
        assert "OpenDataLoader PDF" in desc_no_files
        assert "Available PDF files" not in desc_no_files

        # With files: file names are included in description
        component.set_attributes(
            {
                **DEFAULT_SETTINGS,
                "path": ["flow123/report.pdf", "flow123/invoice.pdf"],
            }
        )
        desc_with_files = component.get_tool_description()
        assert "report.pdf" in desc_with_files
        assert "invoice.pdf" in desc_with_files
