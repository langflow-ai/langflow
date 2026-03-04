import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from lfx.components.opendataloader_pdf.opendataloader_pdf import (
    OpenDataLoaderPDFComponent,
)
from lfx.schema import Data

from tests.base import ComponentTestBaseWithoutClient


class TestOpenDataLoaderPDFComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return OpenDataLoaderPDFComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
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

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        # New component, no previous versions
        return []

    def test_basic_setup(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)
        assert component.format == default_kwargs["format"]
        assert component.quiet == default_kwargs["quiet"]
        assert component.content_safety == default_kwargs["content_safety"]

    def test_valid_extensions(self, component_class):
        """Test that only PDF extension is supported."""
        component = component_class()
        assert component.VALID_EXTENSIONS == ["pdf"]

    def test_content_safety_enabled(self, component_class, default_kwargs):
        """Test content safety filter when enabled."""
        component = component_class()
        component.set_attributes({**default_kwargs, "content_safety": "enabled"})
        result = component._get_content_safety_off()
        assert result is None

    def test_content_safety_disabled_default(self, component_class, default_kwargs):
        """Test content safety filter when disabled with default filters."""
        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "content_safety": "disabled",
                "content_safety_filters": "all",
            }
        )
        result = component._get_content_safety_off()
        assert result == ["all"]

    def test_content_safety_disabled_custom_filters(self, component_class, default_kwargs):
        """Test content safety filter with custom disabled filters."""
        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "content_safety": "disabled",
                "content_safety_filters": "hidden-text, off-page, tiny",
            }
        )
        result = component._get_content_safety_off()
        assert result == ["hidden-text", "off-page", "tiny"]

    def test_java_check_success(self, component_class, default_kwargs):
        """Test Java installation check when Java is available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr='openjdk version "11.0.1"')
            component = component_class()
            component.set_attributes(default_kwargs)
            assert component._check_java_installed() is True

    @patch("subprocess.run")
    def test_java_check_failure(self, mock_run, component_class, default_kwargs):
        """Test Java installation check when Java is not available."""
        mock_run.side_effect = FileNotFoundError("java not found")
        component = component_class()
        component.set_attributes(default_kwargs)
        assert component._check_java_installed() is False

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_process_files_success(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test successful PDF processing."""
        # Create a mock PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        # Create output directory
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Track convert call arguments
        convert_calls = []

        # Create mock opendataloader_pdf module
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            # Simulate creating output file
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "test.txt"
            out_file.write_text("Extracted text content")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "silent_errors": False})
        component.log = Mock()

        # Create BaseFile mock with a real merge_data implementation
        original_data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = original_data
        mock_base_file.delete_after_processing = False
        mock_base_file.merge_data = lambda new_data: [
            Data(data={**d.data, **nd.data})
            for d in original_data
            for nd in (new_data if isinstance(new_data, list) else [new_data])
        ]

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files([mock_base_file])

        assert len(result) == 1

        # Verify convert was called with correct core parameters
        assert len(convert_calls) == 1
        call_args = convert_calls[0]
        assert call_args["input_path"] == str(pdf_file)
        assert call_args["quiet"] is True
        assert "content_safety_off" not in call_args  # enabled = not passed to API
        assert call_args["format"] == ["text"]

        # Verify the extracted text content is present in the result data
        result_data = result[0].data[0]
        assert result_data.data["text"] == "Extracted text content"
        assert result_data.data["format"] == "text"
        assert result_data.data["source"] == "test.pdf"
        assert result_data.data["word_count"] == 3  # "Extracted text content"

    def test_import_error_handling(self, component_class, default_kwargs, tmp_path):
        """Test handling when opendataloader_pdf is not installed."""
        component = component_class()
        component.set_attributes(default_kwargs)
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        # Setting a module to None in sys.modules is enough to trigger ImportError
        with (
            patch.dict("sys.modules", {"opendataloader_pdf": None}),
            pytest.raises(ImportError) as exc_info,
        ):
            component.process_files([mock_base_file])

        assert "opendataloader-pdf is not installed" in str(exc_info.value)

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=False)
    def test_java_not_installed_error(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test error when Java is not installed."""
        mock_opendataloader = MagicMock()

        component = component_class()
        component.set_attributes(default_kwargs)
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            pytest.raises(RuntimeError) as exc_info,
        ):
            component.process_files([mock_base_file])

        assert "Java 11 or later is required" in str(exc_info.value)

    def test_format_options(self, component_class):
        """Test different output format options."""
        component = component_class()

        for fmt in [
            "text",
            "markdown",
            "markdown-with-html",
            "markdown-with-images",
            "html",
            "json",
            "pdf",
        ]:
            component.set_attributes({"format": fmt})
            assert component.format == fmt

    def test_display_name_and_description(self, component_class):
        """Test component metadata."""
        assert component_class.display_name == "OpenDataLoader PDF"
        # description is now a dynamic property, so check on an instance
        component = component_class()
        assert "OpenDataLoader PDF" in component._base_description
        assert component_class.icon == "OpenDataLoaderPDF"
        assert component_class.name == "OpenDataLoaderPDF"

    def test_empty_file_list(self, component_class, default_kwargs):
        """Test handling of empty file list."""
        mock_opendataloader = MagicMock()

        component = component_class()
        component.set_attributes(default_kwargs)
        component.log = Mock()

        # Mock the import and java check
        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch.object(component, "_check_java_installed", return_value=True),
        ):
            # Process with empty path list
            mock_base_file = Mock()
            mock_base_file.path = None
            mock_base_file.data = []

            result = component.process_files([mock_base_file])
            assert result == [mock_base_file]

    def test_image_output_options(self, component_class, default_kwargs):
        """Test different image output options."""
        component = component_class()

        for option in ["external", "embedded", "off"]:
            component.set_attributes({**default_kwargs, "image_output": option})
            assert component.image_output == option

    def test_image_format_options(self, component_class, default_kwargs):
        """Test different image format options."""
        component = component_class()

        for fmt in ["png", "jpeg"]:
            component.set_attributes({**default_kwargs, "image_format": fmt})
            assert component.image_format == fmt

    def test_use_struct_tree_option(self, component_class, default_kwargs):
        """Test tagged PDF structure option."""
        component = component_class()

        component.set_attributes({**default_kwargs, "use_struct_tree": True})
        assert component.use_struct_tree is True

        component.set_attributes({**default_kwargs, "use_struct_tree": False})
        assert component.use_struct_tree is False

    def test_password_option(self, component_class, default_kwargs):
        """Test password option for encrypted PDFs."""
        component = component_class()

        component.set_attributes({**default_kwargs, "password": "secret123"})
        assert component.password == "secret123"

    def test_pages_option(self, component_class, default_kwargs):
        """Test pages selection option."""
        component = component_class()

        component.set_attributes({**default_kwargs, "pages": "1,3,5-7"})
        assert component.pages == "1,3,5-7"

    def test_replace_invalid_chars_option(self, component_class, default_kwargs):
        """Test replace invalid characters option."""
        component = component_class()

        component.set_attributes({**default_kwargs, "replace_invalid_chars": "?"})
        assert component.replace_invalid_chars == "?"

        component.set_attributes({**default_kwargs, "replace_invalid_chars": " "})
        assert component.replace_invalid_chars == " "

    def test_keep_line_breaks_option(self, component_class, default_kwargs):
        """Test keep line breaks option."""
        component = component_class()

        component.set_attributes({**default_kwargs, "keep_line_breaks": True})
        assert component.keep_line_breaks is True

    def test_include_header_footer_option(self, component_class, default_kwargs):
        """Test include header/footer option."""
        component = component_class()

        component.set_attributes({**default_kwargs, "include_header_footer": True})
        assert component.include_header_footer is True

    def test_table_method_options(self, component_class, default_kwargs):
        """Test table detection method options."""
        component = component_class()

        for method in ["default", "cluster"]:
            component.set_attributes({**default_kwargs, "table_method": method})
            assert component.table_method == method

    def test_reading_order_options(self, component_class, default_kwargs):
        """Test reading order algorithm options."""
        component = component_class()

        for order in ["xycut", "off"]:
            component.set_attributes({**default_kwargs, "reading_order": order})
            assert component.reading_order == order

    def test_page_separator_options(self, component_class, default_kwargs):
        """Test page separator options."""
        component = component_class()

        component.set_attributes(
            {
                **default_kwargs,
                "text_page_separator": "--- Page %page-number% ---",
                "markdown_page_separator": "\n---\n",
                "html_page_separator": "<hr/>",
            }
        )
        assert component.text_page_separator == "--- Page %page-number% ---"
        assert component.markdown_page_separator == "\n---\n"
        assert component.html_page_separator == "<hr/>"

    def test_hybrid_mode_options(self, component_class, default_kwargs):
        """Test hybrid mode options."""
        component = component_class()

        for mode in ["off", "docling-fast"]:
            component.set_attributes({**default_kwargs, "hybrid": mode})
            assert component.hybrid == mode

    def test_hybrid_triage_mode_options(self, component_class, default_kwargs):
        """Test hybrid triage mode options."""
        component = component_class()

        for mode in ["auto", "full"]:
            component.set_attributes({**default_kwargs, "hybrid_mode": mode})
            assert component.hybrid_mode == mode

    def test_hybrid_url_option(self, component_class, default_kwargs):
        """Test hybrid backend URL option."""
        component = component_class()

        component.set_attributes({**default_kwargs, "hybrid_url": "http://localhost:5002"})
        assert component.hybrid_url == "http://localhost:5002"

    def test_hybrid_timeout_option(self, component_class, default_kwargs):
        """Test hybrid timeout option."""
        component = component_class()

        component.set_attributes({**default_kwargs, "hybrid_timeout": 60000})
        assert component.hybrid_timeout == 60000

    def test_hybrid_fallback_option(self, component_class, default_kwargs):
        """Test hybrid fallback option."""
        component = component_class()

        component.set_attributes({**default_kwargs, "hybrid_fallback": False})
        assert component.hybrid_fallback is False

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_process_files_with_all_options(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test PDF processing with all options enabled."""
        # Create a mock PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        # Create output directory
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Track convert call arguments
        convert_calls = []

        # Create mock opendataloader_pdf module
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            # Simulate creating output file
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "test.md"
            out_file.write_text("# Extracted markdown content")

        mock_opendataloader.convert = mock_convert

        # Set up component with various options
        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "format": "markdown",
                "password": "secret",
                "pages": "1-5",
                "image_output": "embedded",
                "image_format": "jpeg",
                "use_struct_tree": True,
                "keep_line_breaks": True,
                "include_header_footer": True,
                "table_method": "cluster",
                "reading_order": "xycut",
                "markdown_page_separator": "\n---\n",
                "hybrid": "docling-fast",
                "hybrid_mode": "auto",
                "hybrid_url": "http://localhost:5002",
                "hybrid_timeout": 60000,
                "hybrid_fallback": True,
            }
        )
        component.log = Mock()

        # Create BaseFile mock
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files([mock_base_file])

        # Verify convert was called with correct parameters
        assert len(convert_calls) == 1
        call_args = convert_calls[0]

        assert call_args["input_path"] == str(pdf_file)
        assert call_args["quiet"] is True
        assert "content_safety_off" not in call_args  # enabled = not passed to API
        assert call_args["format"] == ["markdown"]
        assert call_args["password"] == "secret"
        assert call_args["pages"] == "1-5"
        assert call_args["image_output"] == "embedded"
        assert call_args["image_format"] == "jpeg"
        assert call_args["use_struct_tree"] is True
        assert call_args["replace_invalid_chars"] == " "
        assert call_args["keep_line_breaks"] is True
        assert call_args["include_header_footer"] is True
        assert call_args["table_method"] == "cluster"
        assert call_args["reading_order"] == "xycut"
        assert call_args["markdown_page_separator"] == "\n---\n"
        assert call_args["hybrid"] == "docling-fast"
        assert call_args["hybrid_mode"] == "auto"
        assert call_args["hybrid_url"] == "http://localhost:5002"
        assert call_args["hybrid_timeout"] == "60000"
        assert call_args["hybrid_fallback"] is True

        assert len(result) == 1

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_process_files_hybrid_off_excludes_hybrid_params(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that hybrid parameters are excluded when hybrid is off."""
        # Create a mock PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        # Create output directory
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Track convert call arguments
        convert_calls = []

        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "test.txt"
            out_file.write_text("Extracted text")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "hybrid": "off"})
        component.log = Mock()

        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        # Verify hybrid-related params are not included when hybrid is off
        call_args = convert_calls[0]
        assert "hybrid" not in call_args
        assert "hybrid_mode" not in call_args
        assert "hybrid_url" not in call_args
        assert "hybrid_timeout" not in call_args
        assert "hybrid_fallback" not in call_args

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_process_files_hybrid_on_empty_url_excludes_url(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that hybrid_url is excluded when hybrid is on but url is empty."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("Extracted text")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "hybrid": "docling-fast",
                "hybrid_mode": "auto",
                "hybrid_url": "",  # empty URL
                "hybrid_timeout": 30000,
            }
        )
        component.log = Mock()

        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        call_args = convert_calls[0]
        # hybrid and hybrid_mode should be present
        assert call_args["hybrid"] == "docling-fast"
        assert call_args["hybrid_mode"] == "auto"
        # hybrid_url should NOT be present (empty string is falsy)
        assert "hybrid_url" not in call_args
        # hybrid_timeout should be present (non-None value)
        assert call_args["hybrid_timeout"] == "30000"
        # Verify hybrid configuration was logged with default URL
        log_messages = [str(call) for call in component.log.call_args_list]
        hybrid_logs = [m for m in log_messages if "Hybrid mode enabled" in m]
        assert len(hybrid_logs) == 1, f"Expected one hybrid config log, got: {log_messages}"
        assert "http://localhost:5002 (default)" in hybrid_logs[0]
        assert "fallback=enabled" in hybrid_logs[0]

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_process_files_hybrid_logs_custom_url(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test that hybrid mode logs the custom URL when provided."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("Extracted text")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "hybrid": "docling-fast",
                "hybrid_mode": "full",
                "hybrid_url": "http://my-server:8080",
                "hybrid_timeout": 60000,
                "hybrid_fallback": False,
            }
        )
        component.log = Mock()

        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        log_messages = [str(call) for call in component.log.call_args_list]
        hybrid_logs = [m for m in log_messages if "Hybrid mode enabled" in m]
        assert len(hybrid_logs) == 1, f"Expected one hybrid config log, got: {log_messages}"
        assert "http://my-server:8080" in hybrid_logs[0]
        assert "triage=full" in hybrid_logs[0]
        assert "fallback=disabled" in hybrid_logs[0]

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_process_files_pdf_format_base64(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test PDF format output returns base64-encoded content."""
        import base64

        # Create a mock PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        # Create output directory
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.pdf").write_bytes(b"%PDF-1.4 restructured")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "format": "pdf"})
        component.log = Mock()

        original_data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = original_data
        mock_base_file.delete_after_processing = False
        # Provide a real merge_data implementation so rollup_data works correctly
        mock_base_file.merge_data = lambda new_data: [
            Data(data={**d.data, **nd.data})
            for d in original_data
            for nd in (new_data if isinstance(new_data, list) else [new_data])
        ]

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files([mock_base_file])

        assert len(result) == 1
        # Verify the content is valid base64
        content = result[0].data[0].data["text"]
        decoded = base64.b64decode(content)
        assert decoded == b"%PDF-1.4 restructured"

    def test_description_includes_java_requirement(self, component_class):
        """Test that component description mentions Java requirement."""
        assert "Java 11" in component_class._base_description

    # ------------------------------ Tool mode tests ---------------------------------

    def test_add_tool_output_enabled(self, component_class):
        """Test that add_tool_output is True for agent tool support."""
        assert component_class.add_tool_output is True

    def test_path_input_tool_mode_false(self, component_class):
        """Test that path FileInput has tool_mode=False to prevent agents from specifying paths."""
        component = component_class()
        path_input = None
        for input_field in component.inputs:
            if input_field.name == "path":
                path_input = input_field
                break
        assert path_input is not None, "path input should exist"
        assert path_input.tool_mode is False

    def test_get_tool_description_with_files(self, component_class, default_kwargs):
        """Test that tool description includes uploaded file names."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": ["flow123/report.pdf"]})
        desc = component.get_tool_description()
        assert "report.pdf" in desc
        assert "OpenDataLoader PDF" in desc

    def test_get_tool_description_no_files(self, component_class, default_kwargs):
        """Test that tool description returns base description when no files are uploaded."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": []})
        desc = component.get_tool_description()
        assert "OpenDataLoader PDF" in desc
        assert "Available PDF files" not in desc

    def test_get_tool_description_multiple_files(self, component_class, default_kwargs):
        """Test that tool description includes all uploaded file names."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": ["flow123/a.pdf", "flow123/b.pdf"]})
        desc = component.get_tool_description()
        assert "a.pdf" in desc
        assert "b.pdf" in desc

    @pytest.mark.asyncio
    async def test_get_tools_returns_two_tools(self, component_class, default_kwargs):
        """Test that _get_tools() creates read_pdf (no params) and read_pdf_page (page_number)."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": ["flow123/test.pdf"]})
        tools = await component._get_tools()
        assert len(tools) == 2

        # Tool 1: read_pdf — zero parameters
        read_pdf = tools[0]
        assert read_pdf.name == "read_pdf"
        schema = read_pdf.args_schema.model_json_schema()
        assert len(schema.get("properties", {})) == 0

        # Tool 2: read_pdf_page — page_number parameter
        read_page = tools[1]
        assert read_page.name == "read_pdf_page"
        schema = read_page.args_schema.model_json_schema()
        assert "page_number" in schema.get("properties", {})

    @pytest.mark.asyncio
    async def test_get_tools_description_includes_filenames(self, component_class, default_kwargs):
        """Test that both tools' descriptions include uploaded file names."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": ["flow123/important_report.pdf"]})
        tools = await component._get_tools()
        assert len(tools) == 2
        assert "important_report.pdf" in tools[0].description
        assert "important_report.pdf" in tools[1].description

    @pytest.mark.asyncio
    async def test_get_tools_metadata(self, component_class, default_kwargs):
        """Test that tool metadata is correctly set."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": ["flow123/test.pdf"]})
        tools = await component._get_tools()
        assert tools[0].metadata["display_name"] == "OpenDataLoader PDF - Read All"
        assert tools[1].metadata["display_name"] == "OpenDataLoader PDF - Read Page"

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_output_dir_used_instead_of_temp(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test that a user-specified output_dir is passed to convert instead of a temp directory."""
        custom_output = tmp_path / "custom_output"
        convert_calls = []

        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("content")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "output_dir": str(custom_output),
            }
        )
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}):
            component.process_files([mock_base_file])

        # output_dir should be the user-specified directory, not a temp dir
        assert convert_calls[0]["output_dir"] == str(custom_output)

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_silent_errors_suppresses_convert_exception(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that silent_errors=True suppresses conversion exceptions."""
        mock_opendataloader = MagicMock()
        mock_opendataloader.convert.side_effect = RuntimeError("Conversion failed")

        component = component_class()
        component.set_attributes({**default_kwargs, "silent_errors": True})
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}):
            # Should NOT raise
            result = component.process_files([mock_base_file])

        assert len(result) == 1

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_silent_errors_false_raises_convert_exception(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that silent_errors=False propagates conversion exceptions."""
        mock_opendataloader = MagicMock()
        mock_opendataloader.convert.side_effect = RuntimeError("Conversion failed")

        component = component_class()
        component.set_attributes({**default_kwargs, "silent_errors": False})
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            pytest.raises(RuntimeError, match="Conversion failed"),
        ):
            component.process_files([mock_base_file])

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_process_files_multiple_pdfs(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test processing multiple PDF files in a single call."""
        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = Path(kwargs["input_path"]).stem + ".txt"
            (out_dir / filename).write_text(f"Content from {filename}")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(default_kwargs)
        component.log = Mock()

        base_files = []
        for name in ["doc1.pdf", "doc2.pdf"]:
            pdf_file = tmp_path / name
            pdf_file.write_bytes(b"%PDF-1.4 mock")
            mock_bf = Mock()
            mock_bf.path = pdf_file
            mock_bf.data = [Data(data={"file_path": str(pdf_file)})]
            mock_bf.delete_after_processing = False
            base_files.append(mock_bf)

        # Each file gets a unique output directory to avoid filename collisions
        output_dirs = [str(tmp_path / f"output_{i}") for i in range(len(base_files))]
        mkdtemp_calls = iter(output_dirs)

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", side_effect=lambda: next(mkdtemp_calls)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files(base_files)

        assert len(result) == 2
        # Verify convert was called once per file with distinct input paths and output dirs
        assert len(convert_calls) == 2
        assert convert_calls[0]["input_path"] != convert_calls[1]["input_path"]
        assert convert_calls[0]["output_dir"] != convert_calls[1]["output_dir"]

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_temp_dirs_cleaned_up_after_processing(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test that temporary directories are cleaned up after processing."""
        output_dir = tmp_path / "output"
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("content")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(default_kwargs)
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree") as mock_rmtree,
        ):
            component.process_files([mock_base_file])

        # rmtree should have been called with the temp directory
        mock_rmtree.assert_called_once_with(str(output_dir))

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_temp_dirs_cleaned_up_on_exception(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test that temp directories are cleaned up even when an exception occurs."""
        output_dir = tmp_path / "output"
        mock_opendataloader = MagicMock()
        mock_opendataloader.convert.side_effect = RuntimeError("Conversion error")

        component = component_class()
        component.set_attributes({**default_kwargs, "silent_errors": False})
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree") as mock_rmtree,
            pytest.raises(RuntimeError),
        ):
            component.process_files([mock_base_file])

        # rmtree should still be called in the finally block
        mock_rmtree.assert_called_once_with(str(output_dir))

    # ------------------------------ Page parsing tests --------------------------------

    def test_parse_pages_from_json_data(self, component_class, default_kwargs, tmp_path):
        """Test that JSON content is split into per-page Data objects."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})

        pdf_file = str(tmp_path / "test.pdf")
        json_content = json.dumps(
            {
                "file name": "test.pdf",
                "number of pages": 2,
                "kids": [
                    {"type": "heading", "page number": 1, "content": "Title Page 1"},
                    {
                        "type": "paragraph",
                        "page number": 1,
                        "content": "Body text page 1.",
                    },
                    {"type": "heading", "page number": 2, "content": "Title Page 2"},
                    {
                        "type": "paragraph",
                        "page number": 2,
                        "content": "Body text page 2.",
                    },
                ],
            }
        )

        data_list = [
            Data(
                data={
                    "text": json_content,
                    "source": "test.pdf",
                    "file_path": pdf_file,
                    "format": "json",
                }
            )
        ]

        pages = component._parse_pages_from_data(data_list)

        assert len(pages) == 2
        assert pages[0].data["page_number"] == 1
        assert pages[0].data["total_pages"] == 2
        assert "Title Page 1" in pages[0].data["text"]
        assert "Body text page 1." in pages[0].data["text"]
        assert pages[0].data["source"] == "test.pdf"

        assert pages[1].data["page_number"] == 2
        assert "Title Page 2" in pages[1].data["text"]

    def test_parse_pages_from_json_empty_kids(self, component_class, default_kwargs, tmp_path):
        """Test JSON parsing with empty kids array."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})

        pdf_file = str(tmp_path / "empty.pdf")
        json_content = json.dumps(
            {
                "file name": "empty.pdf",
                "number of pages": 1,
                "kids": [],
            }
        )

        data_list = [
            Data(
                data={
                    "text": json_content,
                    "source": "empty.pdf",
                    "file_path": pdf_file,
                    "format": "json",
                }
            )
        ]

        pages = component._parse_pages_from_data(data_list)
        assert len(pages) == 0

    def test_parse_pages_from_sentinel_text(self, component_class, default_kwargs, tmp_path):
        """Test sentinel-based page splitting for text format.

        The opendataloader-pdf library places the sentinel BEFORE each page's content,
        and %page-number% is the page number of the content that follows.
        """
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        pdf_file = str(tmp_path / "doc.pdf")
        content = (
            "\n---ODL_PAGE_BREAK_1---\n"
            "Page one content here."
            "\n---ODL_PAGE_BREAK_2---\n"
            "Page two content here."
            "\n---ODL_PAGE_BREAK_3---\n"
            "Page three content here."
        )

        data_list = [
            Data(
                data={
                    "text": content,
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]

        pages = component._parse_pages_from_data(data_list)

        assert len(pages) == 3
        assert pages[0].data["page_number"] == 1
        assert "Page one content" in pages[0].data["text"]
        assert pages[1].data["page_number"] == 2
        assert "Page two content" in pages[1].data["text"]
        assert pages[2].data["page_number"] == 3
        assert "Page three content" in pages[2].data["text"]
        # All should share the same total_pages
        assert all(p.data["total_pages"] == 3 for p in pages)

    def test_parse_pages_no_sentinel_single_page(self, component_class, default_kwargs, tmp_path):
        """Test that content without sentinel is treated as a single page."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        pdf_file = str(tmp_path / "doc.pdf")
        data_list = [
            Data(
                data={
                    "text": "Just some text.",
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]

        pages = component._parse_pages_from_data(data_list)
        assert len(pages) == 1
        assert pages[0].data["page_number"] == 1
        assert pages[0].data["total_pages"] == 1

    def test_parse_pages_pdf_format_skipped(self, component_class, default_kwargs, tmp_path):
        """Test that pdf format (binary) is skipped for page parsing."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "pdf"})

        pdf_file = str(tmp_path / "doc.pdf")
        data_list = [
            Data(
                data={
                    "text": "base64data",
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "pdf",
                }
            )
        ]

        pages = component._parse_pages_from_data(data_list)
        assert len(pages) == 0

    # ------------------------------ Metadata enrichment tests -------------------------

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_data_metadata_includes_total_pages_and_word_count(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that processed Data includes total_pages and word_count fields."""
        output_dir = tmp_path / "output"
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            # Simulate 2-page text output with sentinel (placed before each page)
            content = "\n---ODL_PAGE_BREAK_1---\nFirst page text.\n---ODL_PAGE_BREAK_2---\nSecond page text."
            (out_dir / "test.txt").write_text(content)

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(default_kwargs)
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        original_data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = original_data
        mock_base_file.delete_after_processing = False
        mock_base_file.merge_data = lambda new_data: [
            Data(data={**d.data, **nd.data})
            for d in original_data
            for nd in (new_data if isinstance(new_data, list) else [new_data])
        ]

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files([mock_base_file])

        data = result[0].data[0]
        assert data.data["total_pages"] == 2
        assert data.data["word_count"] > 0

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_data_metadata_json_format_total_pages(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test that JSON format correctly reads total_pages from 'number of pages'."""
        output_dir = tmp_path / "output"
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            content = json.dumps(
                {
                    "file name": "test.pdf",
                    "number of pages": 5,
                    "kids": [{"type": "paragraph", "page number": 1, "content": "Hello"}],
                }
            )
            (out_dir / "test.json").write_text(content)

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        original_data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = original_data
        mock_base_file.delete_after_processing = False
        mock_base_file.merge_data = lambda new_data: [
            Data(data={**d.data, **nd.data})
            for d in original_data
            for nd in (new_data if isinstance(new_data, list) else [new_data])
        ]

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files([mock_base_file])

        data = result[0].data[0]
        assert data.data["total_pages"] == 5

    # ------------------------------ Sentinel injection tests --------------------------

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_sentinel_injected_for_text_format(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test that page sentinel is auto-injected when user hasn't set a separator."""
        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("content")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text", "text_page_separator": ""})
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        output_dir = tmp_path / "output"
        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        call_args = convert_calls[0]
        assert "text_page_separator" in call_args
        assert "%page-number%" in call_args["text_page_separator"]

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_sentinel_not_injected_when_user_sets_separator(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that user-set separator is preserved (sentinel not overwritten)."""
        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("content")

        mock_opendataloader.convert = mock_convert

        user_separator = "--- Page %page-number% ---"
        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "format": "text",
                "text_page_separator": user_separator,
            }
        )
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        output_dir = tmp_path / "output"
        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        call_args = convert_calls[0]
        assert call_args["text_page_separator"] == user_separator

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_sentinel_not_injected_for_json_format(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test that no sentinel is injected for JSON format (parsed from structure)."""
        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.json").write_text('{"kids":[], "number of pages": 1}')

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        output_dir = tmp_path / "output"
        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        call_args = convert_calls[0]
        # JSON format has no separator key, so no sentinel should be injected
        for key in [
            "text_page_separator",
            "markdown_page_separator",
            "html_page_separator",
        ]:
            assert key not in call_args or "ODL_PAGE_BREAK" not in str(call_args.get(key, ""))

    # --- Tests for _file_path_as_list Message.files handling ---

    def test_file_path_as_list_message_with_files(self, component_class, default_kwargs, tmp_path):
        """Test that _file_path_as_list extracts paths from Message.files."""
        from lfx.schema.message import Message

        component = component_class()
        component.set_attributes({**default_kwargs})

        pdf_file = str(tmp_path / "test.pdf")
        msg = Message(text="Analyze this PDF", files=[pdf_file])
        component.file_path = msg

        result = component._file_path_as_list()
        assert len(result) == 1
        assert result[0].data["file_path"] == pdf_file

    def test_file_path_as_list_message_with_multiple_files(self, component_class, default_kwargs, tmp_path):
        """Test that _file_path_as_list handles multiple files in Message.files."""
        from lfx.schema.message import Message

        component = component_class()
        component.set_attributes({**default_kwargs})

        file_a = str(tmp_path / "a.pdf")
        file_b = str(tmp_path / "b.pdf")
        msg = Message(text="", files=[file_a, file_b])
        component.file_path = msg

        result = component._file_path_as_list()
        assert len(result) == 2
        assert result[0].data["file_path"] == file_a
        assert result[1].data["file_path"] == file_b

    def test_file_path_as_list_message_empty_files_falls_back_to_text(self, component_class, default_kwargs, tmp_path):
        """Test backward compatibility: empty files falls back to message.text as path."""
        from lfx.schema.message import Message

        component = component_class()
        component.set_attributes({**default_kwargs})

        server_path = str(tmp_path / "doc.pdf")
        msg = Message(text=server_path, files=[])
        component.file_path = msg

        result = component._file_path_as_list()
        assert len(result) == 1
        assert result[0].data["file_path"] == server_path

    def test_file_path_as_list_message_list_with_files(self, component_class, default_kwargs, tmp_path):
        """Test that a list of Messages with files is handled correctly."""
        from lfx.schema.message import Message

        component = component_class()
        component.set_attributes({**default_kwargs})

        file_first = str(tmp_path / "first.pdf")
        file_second = str(tmp_path / "second.pdf")
        msgs = [
            Message(text="First", files=[file_first]),
            Message(text="Second", files=[file_second]),
        ]
        component.file_path = msgs

        result = component._file_path_as_list()
        assert len(result) == 2
        assert result[0].data["file_path"] == file_first
        assert result[1].data["file_path"] == file_second

    # ------------------------------ Cache behavior tests ------------------------------

    def test_cached_data_calls_load_files_base_once(self, component_class, default_kwargs, tmp_path):
        """Test that _get_cached_data() calls load_files_base() only once."""
        component = component_class()
        component.set_attributes(default_kwargs)

        pdf_file = str(tmp_path / "test.pdf")
        mock_data = [Data(data={"text": "cached content", "file_path": pdf_file})]
        with patch.object(component, "load_files_base", return_value=mock_data) as mock_load:
            result1 = component._get_cached_data()
            result2 = component._get_cached_data()

        # load_files_base should be called exactly once
        mock_load.assert_called_once()
        assert result1 is result2  # Same object returned

    def test_cached_data_is_per_instance(self, component_class, default_kwargs):
        """Test that cache is per-instance, not shared across instances."""
        comp1 = component_class()
        comp1.set_attributes(default_kwargs)
        comp2 = component_class()
        comp2.set_attributes(default_kwargs)

        data1 = [Data(data={"text": "from comp1"})]
        data2 = [Data(data={"text": "from comp2"})]

        with patch.object(comp1, "load_files_base", return_value=data1):
            result1 = comp1._get_cached_data()
        with patch.object(comp2, "load_files_base", return_value=data2):
            result2 = comp2._get_cached_data()

        assert result1[0].data["text"] == "from comp1"
        assert result2[0].data["text"] == "from comp2"

    def test_load_files_uses_cache(self, component_class, default_kwargs, tmp_path):
        """Test that overridden load_files() uses _get_cached_data()."""
        component = component_class()
        component.set_attributes(default_kwargs)

        pdf_file = str(tmp_path / "test.pdf")
        mock_data = [Data(data={"text": "content", "file_path": pdf_file, "format": "text"})]
        with patch.object(component, "_get_cached_data", return_value=mock_data) as mock_cache:
            result = component.load_files()

        mock_cache.assert_called_once()
        assert len(result) == 1

    def test_load_files_message_uses_cache(self, component_class, default_kwargs, tmp_path):
        """Test that overridden load_files_message() uses _get_cached_data()."""
        component = component_class()
        component.set_attributes(default_kwargs)

        pdf_file = str(tmp_path / "test.pdf")
        mock_data = [Data(data={"text": "page content", "file_path": pdf_file})]
        with patch.object(component, "_get_cached_data", return_value=mock_data) as mock_cache:
            result = component.load_files_message()

        mock_cache.assert_called_once()
        assert "page content" in result.text

    def test_load_files_by_page_returns_dataframe(self, component_class, default_kwargs, tmp_path):
        """Test that load_files_by_page() returns a proper DataFrame with expected columns."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        pdf_file = str(tmp_path / "test.pdf")
        mock_data = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nPage 1 text\n---ODL_PAGE_BREAK_2---\nPage 2 text",
                    "source": "test.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]
        with patch.object(component, "_get_cached_data", return_value=mock_data):
            result = component.load_files_by_page()

        assert len(result) == 2
        assert "page_number" in result.columns
        assert "total_pages" in result.columns
        assert "text" in result.columns

    # ----------------------- Hybrid Mode edge-case tests -----------------------

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_hybrid_fallback_excluded_when_hybrid_off(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that hybrid_fallback is excluded from convert_params when hybrid is off.

        hybrid_fallback is only relevant when hybrid mode is active, so it should
        not be passed to the library when hybrid is off.
        """
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("Extracted text")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "hybrid": "off"})
        component.log = Mock()

        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        call_args = convert_calls[0]
        # hybrid_fallback should NOT be in convert_params when hybrid is off
        assert "hybrid_fallback" not in call_args

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_hybrid_timeout_none_excluded(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test that hybrid_timeout is excluded from convert_params when it is None/0."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("Extracted text")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "hybrid": "docling-fast",
                "hybrid_mode": "auto",
                "hybrid_timeout": 0,
            }
        )
        component.log = Mock()

        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        call_args = convert_calls[0]
        assert call_args["hybrid"] == "docling-fast"
        # hybrid_timeout should NOT be present when value is 0 (falsy)
        assert "hybrid_timeout" not in call_args

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_hybrid_convert_failure_with_fallback_enabled(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that conversion errors are caught by silent_errors when hybrid backend fails."""
        mock_opendataloader = MagicMock()
        mock_opendataloader.convert.side_effect = RuntimeError("Connection to hybrid backend refused")

        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "hybrid": "docling-fast",
                "hybrid_mode": "auto",
                "hybrid_fallback": True,
                "silent_errors": True,
            }
        )
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}):
            # Should NOT raise because silent_errors=True
            result = component.process_files([mock_base_file])

        assert len(result) == 1
        # Error should be logged
        error_logs = [str(call) for call in component.log.call_args_list if "Error processing" in str(call)]
        assert len(error_logs) >= 1

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_hybrid_convert_failure_without_silent_errors_raises(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that conversion errors propagate when silent_errors is disabled."""
        mock_opendataloader = MagicMock()
        mock_opendataloader.convert.side_effect = RuntimeError("Connection to hybrid backend refused")

        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "hybrid": "docling-fast",
                "hybrid_mode": "full",
                "hybrid_fallback": False,
                "silent_errors": False,
            }
        )
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            pytest.raises(RuntimeError, match="Connection to hybrid backend refused"),
        ):
            component.process_files([mock_base_file])

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_hybrid_multiple_files_each_gets_hybrid_params(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that hybrid parameters are passed for every file in multi-file processing."""
        output_dir = tmp_path / "output"
        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = Path(kwargs["input_path"]).stem + ".txt"
            (out_dir / filename).write_text(f"Content from {filename}")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "hybrid": "docling-fast",
                "hybrid_mode": "full",
                "hybrid_url": "http://my-server:5002",
                "hybrid_timeout": 45000,
            }
        )
        component.log = Mock()

        base_files = []
        for name in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
            pdf_file = tmp_path / name
            pdf_file.write_bytes(b"%PDF-1.4 mock")
            mock_bf = Mock()
            mock_bf.path = pdf_file
            mock_bf.data = [Data(data={"file_path": str(pdf_file)})]
            mock_bf.delete_after_processing = False
            base_files.append(mock_bf)

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files(base_files)

        # All 3 files should be processed
        assert len(convert_calls) == 3
        assert len(result) == 3
        # Each call should include hybrid params
        for call_args in convert_calls:
            assert call_args["hybrid"] == "docling-fast"
            assert call_args["hybrid_mode"] == "full"
            assert call_args["hybrid_url"] == "http://my-server:5002"
            assert call_args["hybrid_timeout"] == "45000"
            assert call_args["hybrid_fallback"] is True

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_hybrid_no_log_when_hybrid_off(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test that no hybrid log message is emitted when hybrid is off."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("Extracted text")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "hybrid": "off"})
        component.log = Mock()

        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        # No "Hybrid mode enabled" log should be present
        log_messages = [str(call) for call in component.log.call_args_list]
        hybrid_logs = [m for m in log_messages if "Hybrid mode enabled" in m]
        assert len(hybrid_logs) == 0, f"Unexpected hybrid log when hybrid is off: {hybrid_logs}"

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_hybrid_with_markdown_format(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test hybrid mode works correctly with markdown format output."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.md").write_text("# Title\n\nSome content from hybrid backend")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "format": "markdown",
                "hybrid": "docling-fast",
                "hybrid_mode": "auto",
            }
        )
        component.log = Mock()

        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files([mock_base_file])

        assert len(result) == 1
        call_args = convert_calls[0]
        assert call_args["format"] == ["markdown"]
        assert call_args["hybrid"] == "docling-fast"
        assert call_args["hybrid_mode"] == "auto"

    # ------------------------------ content_safety_filters edge cases -----------------

    def test_content_safety_disabled_empty_filters_defaults_to_all(self, component_class, default_kwargs):
        """Test that empty content_safety_filters defaults to ['all'] when safety is disabled."""
        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "content_safety": "disabled",
                "content_safety_filters": "",
            }
        )
        result = component._get_content_safety_off()
        assert result == ["all"]

    def test_content_safety_disabled_whitespace_only_filters_defaults_to_all(self, component_class, default_kwargs):
        """Test that whitespace-only content_safety_filters defaults to ['all']."""
        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "content_safety": "disabled",
                "content_safety_filters": "   ",
            }
        )
        result = component._get_content_safety_off()
        assert result == ["all"]

    # ------------------------------ _count_total_pages tests --------------------------

    def test_count_total_pages_json_format(self, component_class, default_kwargs):
        """Test _count_total_pages with JSON format reads 'number of pages'."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})

        content = json.dumps({"number of pages": 7, "kids": []})
        assert component._count_total_pages(content) == 7

    def test_count_total_pages_json_with_parsed_json(self, component_class, default_kwargs):
        """Test _count_total_pages uses pre-parsed dict when provided."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})

        parsed = {"number of pages": 12, "kids": []}
        # Content string is ignored when parsed_json is provided
        assert component._count_total_pages("ignored", parsed_json=parsed) == 12

    def test_count_total_pages_json_parsed_json_missing_field(self, component_class, default_kwargs):
        """Test _count_total_pages defaults to 1 when parsed_json lacks 'number of pages'."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})

        parsed = {"kids": []}
        assert component._count_total_pages("ignored", parsed_json=parsed) == 1

    def test_count_total_pages_json_missing_field(self, component_class, default_kwargs):
        """Test _count_total_pages defaults to 1 when 'number of pages' is absent."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})

        content = json.dumps({"kids": []})
        assert component._count_total_pages(content) == 1

    def test_count_total_pages_json_invalid_json(self, component_class, default_kwargs):
        """Test _count_total_pages returns 1 for invalid JSON."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})

        assert component._count_total_pages("not valid json") == 1

    def test_count_total_pages_text_with_sentinels(self, component_class, default_kwargs):
        """Test _count_total_pages counts sentinel page markers in text format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        content = "\n---ODL_PAGE_BREAK_1---\nPage 1\n---ODL_PAGE_BREAK_2---\nPage 2\n---ODL_PAGE_BREAK_3---\nPage 3"
        assert component._count_total_pages(content) == 3

    def test_count_total_pages_text_no_sentinels(self, component_class, default_kwargs):
        """Test _count_total_pages returns 1 when no sentinels are present."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        assert component._count_total_pages("Just plain text") == 1

    def test_count_total_pages_markdown_format(self, component_class, default_kwargs):
        """Test _count_total_pages works for markdown format with sentinels."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "markdown"})

        content = "\n---ODL_PAGE_BREAK_1---\n# Title\n---ODL_PAGE_BREAK_2---\n## Section"
        assert component._count_total_pages(content) == 2

    # ------------------------------ Empty data output tests ---------------------------

    def test_load_files_empty_data_returns_empty_dataframe(self, component_class, default_kwargs):
        """Test that load_files() returns empty DataFrame when no data is cached."""
        component = component_class()
        component.set_attributes(default_kwargs)

        with patch.object(component, "_get_cached_data", return_value=[]):
            result = component.load_files()

        assert len(result) == 0

    def test_load_files_message_empty_data_returns_empty_message(self, component_class, default_kwargs):
        """Test that load_files_message() returns empty Message when no data is cached."""
        component = component_class()
        component.set_attributes(default_kwargs)

        with patch.object(component, "_get_cached_data", return_value=[]):
            result = component.load_files_message()

        assert result.text is None or result.text == ""

    def test_load_files_by_page_empty_data_returns_empty_dataframe(self, component_class, default_kwargs):
        """Test that load_files_by_page() returns empty DataFrame when no data is cached."""
        component = component_class()
        component.set_attributes(default_kwargs)

        with patch.object(component, "_get_cached_data", return_value=[]):
            result = component.load_files_by_page()

        assert len(result) == 0

    def test_load_files_by_page_pdf_format_returns_empty(self, component_class, default_kwargs, tmp_path):
        """Test that load_files_by_page() returns empty DataFrame for pdf format (binary)."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "pdf"})

        pdf_file = str(tmp_path / "doc.pdf")
        mock_data = [
            Data(
                data={
                    "text": "base64data",
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "pdf",
                }
            )
        ]
        with patch.object(component, "_get_cached_data", return_value=mock_data):
            result = component.load_files_by_page()

        assert len(result) == 0

    # ------------------------------ Tool error handling tests -------------------------

    @pytest.mark.asyncio
    async def test_read_pdf_tool_no_data_returns_message(self, component_class, default_kwargs, tmp_path):
        """Test that read_pdf tool returns a message when no text is extracted."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": [str(tmp_path / "test.pdf")]})

        with patch.object(component, "_get_cached_data", return_value=[]):
            tools = await component._get_tools()
            result = await tools[0].ainvoke({})

        assert "No text extracted" in result

    @pytest.mark.asyncio
    async def test_read_pdf_tool_returns_concatenated_text(self, component_class, default_kwargs, tmp_path):
        """Test that read_pdf tool returns concatenated text from all files."""
        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "path": [str(tmp_path / "a.pdf"), str(tmp_path / "b.pdf")],
            }
        )

        mock_data = [
            Data(data={"text": "Content from file A"}),
            Data(data={"text": "Content from file B"}),
        ]
        with patch.object(component, "_get_cached_data", return_value=mock_data):
            tools = await component._get_tools()
            result = await tools[0].ainvoke({})

        assert "Content from file A" in result
        assert "Content from file B" in result

    @pytest.mark.asyncio
    async def test_read_pdf_tool_handles_exception(self, component_class, default_kwargs, tmp_path):
        """Test that read_pdf tool catches exceptions and returns error message."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": [str(tmp_path / "test.pdf")]})

        with patch.object(
            component,
            "_get_cached_data",
            side_effect=FileNotFoundError("File not found"),
        ):
            tools = await component._get_tools()
            result = await tools[0].ainvoke({})

        assert "Error processing PDF files" in result

    @pytest.mark.asyncio
    async def test_read_pdf_page_tool_returns_page_content(self, component_class, default_kwargs, tmp_path):
        """Test that read_pdf_page tool returns content for a specific page."""
        pdf_file = str(tmp_path / "test.pdf")
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text", "path": [pdf_file]})

        mock_data = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nFirst page\n---ODL_PAGE_BREAK_2---\nSecond page",
                    "source": "test.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]
        with patch.object(component, "_get_cached_data", return_value=mock_data):
            tools = await component._get_tools()
            result = await tools[1].ainvoke({"page_number": 2})

        assert "Second page" in result

    @pytest.mark.asyncio
    async def test_read_pdf_page_tool_page_not_found(self, component_class, default_kwargs, tmp_path):
        """Test that read_pdf_page tool returns helpful message when page is not found."""
        pdf_file = str(tmp_path / "test.pdf")
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text", "path": [pdf_file]})

        mock_data = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nOnly one page",
                    "source": "test.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]
        with patch.object(component, "_get_cached_data", return_value=mock_data):
            tools = await component._get_tools()
            result = await tools[1].ainvoke({"page_number": 99})

        assert "Page 99 not found" in result
        assert "Available pages" in result

    @pytest.mark.asyncio
    async def test_read_pdf_page_tool_no_pages_extracted(self, component_class, default_kwargs, tmp_path):
        """Test that read_pdf_page tool handles case where no pages could be extracted."""
        pdf_file = str(tmp_path / "doc.pdf")
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "pdf", "path": [pdf_file]})

        mock_data = [
            Data(
                data={
                    "text": "base64data",
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "pdf",
                }
            )
        ]
        with patch.object(component, "_get_cached_data", return_value=mock_data):
            tools = await component._get_tools()
            result = await tools[1].ainvoke({"page_number": 1})

        assert "not found" in result
        assert "No pages could be extracted" in result

    @pytest.mark.asyncio
    async def test_read_pdf_page_tool_handles_exception(self, component_class, default_kwargs, tmp_path):
        """Test that read_pdf_page tool catches exceptions and returns error message."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": [str(tmp_path / "test.pdf")]})

        with patch.object(component, "_get_cached_data", side_effect=RuntimeError("Unexpected error")):
            tools = await component._get_tools()
            result = await tools[1].ainvoke({"page_number": 1})

        assert "Error reading page 1" in result

    # ------------------------------ Thread-safety tests --------------------------------

    def test_cached_data_thread_safe(self, component_class, default_kwargs, tmp_path):
        """Test that _get_cached_data() is thread-safe under concurrent access."""
        import threading

        component = component_class()
        component.set_attributes(default_kwargs)

        call_count = 0
        call_lock = threading.Lock()

        pdf_file = str(tmp_path / "test.pdf")
        mock_data = [Data(data={"text": "cached content", "file_path": pdf_file})]

        def counting_load():
            nonlocal call_count
            with call_lock:
                call_count += 1
            return mock_data

        results = []

        def worker():
            results.append(component._get_cached_data())

        with patch.object(component, "load_files_base", side_effect=counting_load):
            threads = [threading.Thread(target=worker) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # load_files_base should be called exactly once despite concurrent access
        assert call_count == 1
        assert len(results) == 5
        assert all(r is results[0] for r in results)

    # ------------------------------ load_files DataFrame column tests ------------------

    def test_load_files_returns_expected_columns(self, component_class, default_kwargs, tmp_path):
        """Test that load_files() returns a DataFrame with expected columns."""
        component = component_class()
        component.set_attributes(default_kwargs)

        pdf_file = str(tmp_path / "test.pdf")
        mock_data = [
            Data(
                data={
                    "text": "Content",
                    "file_path": pdf_file,
                    "format": "text",
                    "source": "test.pdf",
                    "total_pages": 1,
                    "word_count": 1,
                }
            )
        ]
        with patch.object(component, "_get_cached_data", return_value=mock_data):
            result = component.load_files()

        assert len(result) == 1
        assert "text" in result.columns
        assert "file_path" in result.columns
        assert "format" in result.columns
        assert "total_pages" in result.columns
        assert "word_count" in result.columns

    # ------------------------------ _compute_word_count tests ----------------------

    def test_compute_word_count_text_format(self, component_class, default_kwargs):
        """Test _compute_word_count strips sentinels for text format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        content = "\n---ODL_PAGE_BREAK_1---\nHello world\n---ODL_PAGE_BREAK_2---\nFoo bar baz"
        assert component._compute_word_count(content) == 5  # "Hello world Foo bar baz"

    def test_compute_word_count_json_format(self, component_class, default_kwargs):
        """Test _compute_word_count extracts words from JSON kids content fields."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})

        content = json.dumps(
            {
                "number of pages": 1,
                "kids": [
                    {"type": "heading", "page number": 1, "content": "Document Title"},
                    {
                        "type": "paragraph",
                        "page number": 1,
                        "content": "Body text here.",
                    },
                ],
            }
        )
        # "Document Title Body text here." = 5 words
        assert component._compute_word_count(content) == 5

    def test_compute_word_count_json_with_parsed_json(self, component_class, default_kwargs):
        """Test _compute_word_count uses pre-parsed dict when provided."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})

        parsed = {
            "kids": [
                {"content": "One two three"},
            ],
        }
        assert component._compute_word_count("ignored", parsed_json=parsed) == 3

    def test_compute_word_count_pdf_format_returns_zero(self, component_class, default_kwargs):
        """Test _compute_word_count returns 0 for PDF (base64) format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "pdf"})

        assert component._compute_word_count("SGVsbG8gV29ybGQ=") == 0

    def test_compute_word_count_text_no_sentinels(self, component_class, default_kwargs):
        """Test _compute_word_count counts words normally when no sentinels exist."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        assert component._compute_word_count("Simple plain text content") == 4

    # ------------------------------ _parse_pages_from_sentinel total_pages tests ----

    def test_parse_pages_sentinel_total_pages_with_empty_trailing_page(self, component_class, default_kwargs, tmp_path):
        """Test that total_pages counts all sentinels, including pages with empty text."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        pdf_file = str(tmp_path / "doc.pdf")
        # Page 3 has no text content, but total_pages should still be 3
        content = (
            "\n---ODL_PAGE_BREAK_1---\n"
            "Page one content."
            "\n---ODL_PAGE_BREAK_2---\n"
            "Page two content."
            "\n---ODL_PAGE_BREAK_3---\n"
            "   "  # empty after strip
        )

        data_list = [
            Data(
                data={
                    "text": content,
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]
        pages = component._parse_pages_from_data(data_list)

        # Only 2 pages have text, but total_pages should be 3
        assert len(pages) == 2
        assert all(p.data["total_pages"] == 3 for p in pages)

    # ------------------------------ Sentinel injection for all text-like formats ------

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_sentinel_injected_for_markdown_with_html_format(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that sentinel is auto-injected for markdown-with-html format."""
        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.md").write_text("content")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "format": "markdown-with-html",
                "markdown_page_separator": "",
            }
        )
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        output_dir = tmp_path / "output"
        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        call_args = convert_calls[0]
        assert "markdown_page_separator" in call_args
        assert "%page-number%" in call_args["markdown_page_separator"]

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_sentinel_injected_for_markdown_with_images_format(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that sentinel is auto-injected for markdown-with-images format."""
        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.md").write_text("content")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "format": "markdown-with-images",
                "markdown_page_separator": "",
            }
        )
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        output_dir = tmp_path / "output"
        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        call_args = convert_calls[0]
        assert "markdown_page_separator" in call_args
        assert "%page-number%" in call_args["markdown_page_separator"]

    # ------------------------------ JSON page parsing edge cases -------------------

    def test_parse_pages_from_json_malformed_json(self, component_class, default_kwargs, tmp_path):
        """Test that malformed JSON content returns empty page list."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})

        pdf_file = str(tmp_path / "bad.pdf")
        data_list = [
            Data(
                data={
                    "text": "not valid json {{{",
                    "source": "bad.pdf",
                    "file_path": pdf_file,
                    "format": "json",
                }
            )
        ]

        pages = component._parse_pages_from_data(data_list)
        assert len(pages) == 0

    def test_parse_pages_from_json_kids_without_content(self, component_class, default_kwargs, tmp_path):
        """Test that JSON kids elements without 'content' field are skipped."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})

        pdf_file = str(tmp_path / "doc.pdf")
        json_content = json.dumps(
            {
                "number of pages": 1,
                "kids": [
                    {"type": "image", "page number": 1},  # no content field
                    {
                        "type": "paragraph",
                        "page number": 1,
                        "content": "",
                    },  # empty content
                    {"type": "heading", "page number": 1, "content": "Real Content"},
                ],
            }
        )

        data_list = [
            Data(
                data={
                    "text": json_content,
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "json",
                }
            )
        ]
        pages = component._parse_pages_from_data(data_list)

        assert len(pages) == 1
        assert "Real Content" in pages[0].data["text"]

    # ------------------------------ _compute_word_count for markdown variants ------

    def test_compute_word_count_markdown_with_html_format(self, component_class, default_kwargs):
        """Test _compute_word_count strips sentinels for markdown-with-html format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "markdown-with-html"})

        content = "\n---ODL_PAGE_BREAK_1---\n<h1>Title</h1>\n---ODL_PAGE_BREAK_2---\nBody text"
        word_count = component._compute_word_count(content)
        assert word_count > 0

    # ------------------------------ get_tool_description edge cases ----------------

    def test_get_tool_description_with_path_objects(self, component_class, default_kwargs, tmp_path):
        """Test that get_tool_description handles Path objects in path list."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": [tmp_path / "report.pdf"]})
        desc = component.get_tool_description()
        assert "report.pdf" in desc

    def test_get_tool_description_with_none_in_path_list(self, component_class, default_kwargs):
        """Test that get_tool_description skips None entries in path list."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": [None, "flow123/valid.pdf"]})
        desc = component.get_tool_description()
        assert "valid.pdf" in desc

    # ------------------------------ Custom output_dir multi-file tests ----------------

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_custom_output_dir_multi_file_reads_correct_output(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that each file's output is correctly read when using a shared custom output_dir.

        Regression test: without preferring the exact expected filename, the glob
        ``*.txt`` could match a stale file from a previous iteration and
        ``output_files[0]`` would return the wrong content.
        """
        custom_output = tmp_path / "shared_output"
        convert_calls = []

        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            # Output file name matches input stem (opendataloader-pdf convention)
            filename = Path(kwargs["input_path"]).stem + ".txt"
            content = f"Unique content from {Path(kwargs['input_path']).stem}"
            (out_dir / filename).write_text(content, encoding="utf-8")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "format": "text",
                "output_dir": str(custom_output),
            }
        )
        component.log = Mock()

        base_files = []
        for name in ["alpha.pdf", "beta.pdf"]:
            pdf_file = tmp_path / name
            pdf_file.write_bytes(b"%PDF-1.4 mock")
            original_data = [Data(data={"file_path": str(pdf_file)})]
            mock_bf = Mock()
            mock_bf.path = pdf_file
            mock_bf.data = original_data
            mock_bf.delete_after_processing = False
            mock_bf.merge_data = lambda new_data, od=original_data: [
                Data(data={**d.data, **nd.data})
                for d in od
                for nd in (new_data if isinstance(new_data, list) else [new_data])
            ]
            base_files.append(mock_bf)

        with patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}):
            result = component.process_files(base_files)

        assert len(convert_calls) == 2
        assert len(result) == 2

        # Verify each result contains the CORRECT file's content (not the other file's)
        result_texts = [bf.data[0].data["text"] for bf in result]
        assert "Unique content from alpha" in result_texts[0], (
            f"First result should contain alpha's content, got: {result_texts[0]}"
        )
        assert "Unique content from beta" in result_texts[1], (
            f"Second result should contain beta's content, got: {result_texts[1]}"
        )

    # ------------------------------ Preamble deduplication tests ----------------------

    def test_parse_pages_sentinel_preamble_merged_into_first_page(self, component_class, default_kwargs, tmp_path):
        """Test that text before the first sentinel is merged into the first page, not duplicated."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        pdf_file = str(tmp_path / "doc.pdf")
        # Content has preamble text before the first sentinel
        content = (
            "Preamble text before any sentinel."
            "\n---ODL_PAGE_BREAK_1---\n"
            "Page one content."
            "\n---ODL_PAGE_BREAK_2---\n"
            "Page two content."
        )

        data_list = [
            Data(
                data={
                    "text": content,
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]
        pages = component._parse_pages_from_data(data_list)

        # Should be exactly 2 pages (not 3 with a duplicate page 1)
        assert len(pages) == 2
        # Page 1 should contain both preamble and page one content
        assert pages[0].data["page_number"] == 1
        assert "Preamble text" in pages[0].data["text"]
        assert "Page one content" in pages[0].data["text"]
        # Page 2 is normal
        assert pages[1].data["page_number"] == 2
        assert "Page two content" in pages[1].data["text"]
        # total_pages should be 2
        assert all(p.data["total_pages"] == 2 for p in pages)

    def test_parse_pages_sentinel_no_preamble_unchanged(self, component_class, default_kwargs, tmp_path):
        """Test that normal sentinel content (no preamble) still works correctly."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        pdf_file = str(tmp_path / "doc.pdf")
        content = "\n---ODL_PAGE_BREAK_1---\nPage one content.\n---ODL_PAGE_BREAK_2---\nPage two content."

        data_list = [
            Data(
                data={
                    "text": content,
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]
        pages = component._parse_pages_from_data(data_list)

        assert len(pages) == 2
        assert pages[0].data["page_number"] == 1
        assert pages[1].data["page_number"] == 2

    # ------------------------------ _count_total_pages fmt param tests ----------------

    def test_count_total_pages_explicit_fmt_json(self, component_class, default_kwargs):
        """Test _count_total_pages with explicit fmt='json' overrides self.format."""
        component = component_class()
        # self.format is text, but we pass fmt="json" explicitly
        component.set_attributes({**default_kwargs, "format": "text"})

        content = json.dumps({"number of pages": 7, "kids": []})
        assert component._count_total_pages(content, fmt="json") == 7

    def test_compute_word_count_explicit_fmt_pdf(self, component_class, default_kwargs):
        """Test _compute_word_count with explicit fmt='pdf' returns 0."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        # self.format is text, but fmt="pdf" overrides → returns 0
        assert component._compute_word_count("some content", fmt="pdf") == 0

    # ------------------------------ Page cache tests ----------------------------------

    def test_get_cached_page_data_calls_parse_once(self, component_class, default_kwargs, tmp_path):
        """Test that _get_cached_page_data() parses pages only once."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        pdf_file = str(tmp_path / "test.pdf")
        mock_data = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nPage 1\n---ODL_PAGE_BREAK_2---\nPage 2",
                    "source": "test.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]
        with patch.object(component, "_get_cached_data", return_value=mock_data):
            result1 = component._get_cached_page_data()
            result2 = component._get_cached_page_data()

        assert result1 is result2  # Same cached object
        assert len(result1) == 2

    def test_cached_page_data_is_per_instance(self, component_class, default_kwargs, tmp_path):
        """Test that page cache is per-instance."""
        comp1 = component_class()
        comp1.set_attributes({**default_kwargs, "format": "text"})
        comp2 = component_class()
        comp2.set_attributes({**default_kwargs, "format": "text"})

        pdf_file = str(tmp_path / "test.pdf")
        data1 = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nComp1 page",
                    "source": "test.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]
        data2 = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nComp2 page\n---ODL_PAGE_BREAK_2---\nComp2 page 2",
                    "source": "test.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]

        with patch.object(comp1, "_get_cached_data", return_value=data1):
            pages1 = comp1._get_cached_page_data()
        with patch.object(comp2, "_get_cached_data", return_value=data2):
            pages2 = comp2._get_cached_page_data()

        assert len(pages1) == 1
        assert len(pages2) == 2

    # ------------------------------ description property setter tests -----------------

    def test_description_property_setter_no_error(self, component_class, default_kwargs):
        """Test that setting description does not raise an error."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": ["flow123/report.pdf"]})

        # Should not raise AttributeError
        component.description = "Some external description"

        # description property still returns dynamic value
        assert "report.pdf" in component.description

    # ------------------------------ get_tool_description type safety tests ------------

    def test_get_tool_description_with_non_string_path(self, component_class, default_kwargs, tmp_path):
        """Test that get_tool_description handles non-string types in path list."""
        from pathlib import PurePosixPath

        component = component_class()
        component.set_attributes({**default_kwargs, "path": [PurePosixPath("/uploads/report.pdf")]})
        desc = component.get_tool_description()
        assert "report.pdf" in desc

    def test_load_files_by_page_sets_status(self, component_class, default_kwargs, tmp_path):
        """Test that load_files_by_page() sets self.status for UI tracking.

        load_files() sets self.status but load_files_by_page() must also set it
        so the Pages output has a status preview in the UI.
        """
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        pdf_file = str(tmp_path / "test.pdf")
        mock_data = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nPage 1\n---ODL_PAGE_BREAK_2---\nPage 2",
                    "source": "test.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]
        with patch.object(component, "_get_cached_data", return_value=mock_data):
            result = component.load_files_by_page()

        assert component.status is not None
        assert len(component.status) == 2
        assert component.status is result

    # ------------------------------ _file_path_as_list edge cases ---------------------

    def test_file_path_as_list_single_data_object(self, component_class, default_kwargs, tmp_path):
        """Test _file_path_as_list when file_path is a single Data object (not in a list)."""
        component = component_class()
        component.set_attributes(default_kwargs)

        pdf_file = str(tmp_path / "report.pdf")
        data_obj = Data(data={"file_path": pdf_file})
        component.file_path = data_obj

        result = component._file_path_as_list()
        assert len(result) == 1
        assert result[0] is data_obj

    def test_file_path_as_list_none_returns_empty(self, component_class, default_kwargs):
        """Test _file_path_as_list returns [] when file_path is None."""
        component = component_class()
        component.set_attributes(default_kwargs)
        component.file_path = None

        result = component._file_path_as_list()
        assert result == []

    def test_file_path_as_list_empty_list_returns_empty(self, component_class, default_kwargs):
        """Test _file_path_as_list returns [] when file_path is an empty list."""
        component = component_class()
        component.set_attributes(default_kwargs)
        component.file_path = []

        result = component._file_path_as_list()
        assert result == []

    def test_file_path_as_list_mixed_message_and_data(self, component_class, default_kwargs, tmp_path):
        """Test _file_path_as_list with a mixed list of Message and Data objects."""
        from lfx.schema.message import Message

        component = component_class()
        component.set_attributes(default_kwargs)

        file_msg = str(tmp_path / "msg.pdf")
        file_data = str(tmp_path / "data.pdf")
        mixed_list = [
            Message(text="unused", files=[file_msg]),
            Data(data={"file_path": file_data}),
        ]
        component.file_path = mixed_list

        result = component._file_path_as_list()
        assert len(result) == 2
        assert result[0].data["file_path"] == file_msg
        assert result[1].data["file_path"] == file_data

    def test_file_path_as_list_unsupported_type_delegates_to_super(self, component_class, default_kwargs):
        """Test _file_path_as_list delegates to super() for unsupported types (e.g. str)."""
        component = component_class()
        component.set_attributes({**default_kwargs, "silent_errors": False})
        component.file_path = "/some/path/to/file.pdf"
        component.log = Mock()

        # BaseFileComponent now resolves strings as literal paths instead of raising ValueError
        result = component._file_path_as_list()
        assert len(result) == 1
        assert result[0].data["file_path"] == "/some/path/to/file.pdf"

    # ------------------------------ load_files_message edge cases ---------------------

    def test_load_files_message_skips_empty_text(self, component_class, default_kwargs, tmp_path):
        """Test load_files_message() skips Data items with empty text."""
        component = component_class()
        component.set_attributes(default_kwargs)

        mock_data = [
            Data(data={"text": "", "file_path": str(tmp_path / "empty.pdf")}),
            Data(data={"text": "Real content", "file_path": str(tmp_path / "good.pdf")}),
        ]
        with patch.object(component, "_get_cached_data", return_value=mock_data):
            result = component.load_files_message()

        assert "Real content" in result.text

    # ------------------------------ JSON page parsing edge cases ----------------------

    def test_parse_pages_from_json_missing_number_of_pages(self, component_class, default_kwargs, tmp_path):
        """Test _parse_pages_from_json defaults total_pages to 1 when 'number of pages' is absent."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "json"})

        pdf_file = str(tmp_path / "doc.pdf")
        json_content = json.dumps(
            {
                "kids": [
                    {"type": "paragraph", "page number": 1, "content": "Some text"},
                ],
            }
        )
        data_list = [
            Data(
                data={
                    "text": json_content,
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "json",
                }
            )
        ]

        pages = component._parse_pages_from_data(data_list)
        assert len(pages) == 1
        assert pages[0].data["total_pages"] == 1

    # ------------------------------ description property contract ---------------------

    def test_description_property_delegates_to_get_tool_description(self, component_class, default_kwargs):
        """Test that the description property returns the same as get_tool_description()."""
        component = component_class()
        component.set_attributes({**default_kwargs, "path": ["flow123/report.pdf"]})

        assert component.description == component.get_tool_description()

    # ------------------------------ HTML format tests ---------------------------------

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_process_files_html_format(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test PDF processing with HTML output format uses .html extension."""
        output_dir = tmp_path / "output"
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.html").write_text("<p>Hello</p>")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "format": "html"})
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        original_data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = original_data
        mock_base_file.delete_after_processing = False
        mock_base_file.merge_data = lambda new_data: [
            Data(data={**d.data, **nd.data})
            for d in original_data
            for nd in (new_data if isinstance(new_data, list) else [new_data])
        ]

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files([mock_base_file])

        data = result[0].data[0]
        assert data.data["text"] == "<p>Hello</p>"
        assert data.data["format"] == "html"

    def test_parse_pages_from_sentinel_html(self, component_class, default_kwargs, tmp_path):
        """Test sentinel-based page splitting for HTML format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "html"})

        pdf_file = str(tmp_path / "doc.pdf")
        content = "\n---ODL_PAGE_BREAK_1---\n<p>Page one</p>\n---ODL_PAGE_BREAK_2---\n<p>Page two</p>"

        data_list = [
            Data(
                data={
                    "text": content,
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "html",
                }
            )
        ]

        pages = component._parse_pages_from_data(data_list)

        assert len(pages) == 2
        assert pages[0].data["page_number"] == 1
        assert "<p>Page one</p>" in pages[0].data["text"]
        assert pages[1].data["page_number"] == 2
        assert "<p>Page two</p>" in pages[1].data["text"]
        assert all(p.data["total_pages"] == 2 for p in pages)

    def test_count_total_pages_html_format(self, component_class, default_kwargs):
        """Test _count_total_pages works for HTML format with sentinels."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "html"})

        content = "\n---ODL_PAGE_BREAK_1---\n<p>Page 1</p>\n---ODL_PAGE_BREAK_2---\n<p>Page 2</p>"
        assert component._count_total_pages(content) == 2

    def test_compute_word_count_html_format(self, component_class, default_kwargs):
        """Test _compute_word_count strips sentinels for HTML format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "html"})

        content = "\n---ODL_PAGE_BREAK_1---\n<p>Hello world</p>\n---ODL_PAGE_BREAK_2---\n<p>Foo bar</p>"
        word_count = component._compute_word_count(content)
        # Sentinel markers stripped; HTML tags counted as words (raw text counting)
        assert word_count > 0

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_data_metadata_html_format(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test that HTML format includes correct metadata (total_pages, word_count)."""
        output_dir = tmp_path / "output"
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            content = (
                "\n---ODL_PAGE_BREAK_1---\n<p>First page</p>"
                "\n---ODL_PAGE_BREAK_2---\n<p>Second page</p>"
                "\n---ODL_PAGE_BREAK_3---\n<p>Third page</p>"
            )
            (out_dir / "test.html").write_text(content)

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "format": "html"})
        component.log = Mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")
        original_data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = original_data
        mock_base_file.delete_after_processing = False
        mock_base_file.merge_data = lambda new_data: [
            Data(data={**d.data, **nd.data})
            for d in original_data
            for nd in (new_data if isinstance(new_data, list) else [new_data])
        ]

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            result = component.process_files([mock_base_file])

        data = result[0].data[0]
        assert data.data["total_pages"] == 3
        assert data.data["word_count"] > 0
        assert data.data["format"] == "html"
        assert data.data["source"] == "test.pdf"

    # ------------------------------ Markdown variant format tests ----------------------

    def test_parse_pages_from_sentinel_markdown(self, component_class, default_kwargs, tmp_path):
        """Test sentinel-based page splitting for markdown format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "markdown"})

        pdf_file = str(tmp_path / "doc.pdf")
        content = (
            "\n---ODL_PAGE_BREAK_1---\n"
            "# Title\n\nFirst page paragraph."
            "\n---ODL_PAGE_BREAK_2---\n"
            "## Section\n\nSecond page paragraph."
        )

        data_list = [
            Data(
                data={
                    "text": content,
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "markdown",
                }
            )
        ]

        pages = component._parse_pages_from_data(data_list)

        assert len(pages) == 2
        assert pages[0].data["page_number"] == 1
        assert "# Title" in pages[0].data["text"]
        assert pages[1].data["page_number"] == 2
        assert "## Section" in pages[1].data["text"]
        assert all(p.data["total_pages"] == 2 for p in pages)
        assert all(p.data["format"] == "markdown" for p in pages)

    def test_parse_pages_from_sentinel_markdown_with_html(self, component_class, default_kwargs, tmp_path):
        """Test sentinel-based page splitting for markdown-with-html format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "markdown-with-html"})

        pdf_file = str(tmp_path / "doc.pdf")
        content = (
            "\n---ODL_PAGE_BREAK_1---\n"
            "# Title\n<table><tr><td>Cell</td></tr></table>"
            "\n---ODL_PAGE_BREAK_2---\n"
            "## Section\n<div>Content</div>"
        )

        data_list = [
            Data(
                data={
                    "text": content,
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "markdown-with-html",
                }
            )
        ]

        pages = component._parse_pages_from_data(data_list)

        assert len(pages) == 2
        assert pages[0].data["page_number"] == 1
        assert "<table>" in pages[0].data["text"]
        assert pages[1].data["page_number"] == 2
        assert "<div>Content</div>" in pages[1].data["text"]
        assert all(p.data["format"] == "markdown-with-html" for p in pages)

    def test_parse_pages_from_sentinel_markdown_with_images(self, component_class, default_kwargs, tmp_path):
        """Test sentinel-based page splitting for markdown-with-images format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "markdown-with-images"})

        pdf_file = str(tmp_path / "doc.pdf")
        content = (
            "\n---ODL_PAGE_BREAK_1---\n"
            "# Title\n![Figure 1](image1.png)"
            "\n---ODL_PAGE_BREAK_2---\n"
            "More text\n![Figure 2](image2.png)"
        )

        data_list = [
            Data(
                data={
                    "text": content,
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "markdown-with-images",
                }
            )
        ]

        pages = component._parse_pages_from_data(data_list)

        assert len(pages) == 2
        assert pages[0].data["page_number"] == 1
        assert "![Figure 1]" in pages[0].data["text"]
        assert pages[1].data["page_number"] == 2
        assert "![Figure 2]" in pages[1].data["text"]
        assert all(p.data["format"] == "markdown-with-images" for p in pages)

    def test_count_total_pages_markdown_with_html_format(self, component_class, default_kwargs):
        """Test _count_total_pages for markdown-with-html format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "markdown-with-html"})

        content = (
            "\n---ODL_PAGE_BREAK_1---\n# Title\n---ODL_PAGE_BREAK_2---\n## Section\n---ODL_PAGE_BREAK_3---\n## Another"
        )
        assert component._count_total_pages(content) == 3

    def test_count_total_pages_markdown_with_images_format(self, component_class, default_kwargs):
        """Test _count_total_pages for markdown-with-images format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "markdown-with-images"})

        content = "\n---ODL_PAGE_BREAK_1---\n![img](a.png)\n---ODL_PAGE_BREAK_2---\nText"
        assert component._count_total_pages(content) == 2

    def test_compute_word_count_markdown_format(self, component_class, default_kwargs):
        """Test _compute_word_count strips sentinels for markdown format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "markdown"})

        content = "\n---ODL_PAGE_BREAK_1---\n# Title text\n---ODL_PAGE_BREAK_2---\nBody words here"
        word_count = component._compute_word_count(content)
        # "# Title text Body words here" = 6 words (# is a word token)
        assert word_count == 6

    def test_compute_word_count_markdown_with_images_format(self, component_class, default_kwargs):
        """Test _compute_word_count strips sentinels for markdown-with-images format."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "markdown-with-images"})

        content = "\n---ODL_PAGE_BREAK_1---\nSome text ![img](a.png) more words"
        word_count = component._compute_word_count(content)
        assert word_count > 0

    # ------------------------------ PDF format _count_total_pages test -----------------

    def test_count_total_pages_pdf_format_returns_one(self, component_class, default_kwargs):
        """Test _count_total_pages returns 1 for PDF (base64) format.

        PDF binary content cannot be split by page, so page count defaults to 1.
        This was a bug where pdf format fell through to sentinel logic on base64 content.
        """
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "pdf"})

        # Base64-encoded content should not be searched for sentinels
        assert component._count_total_pages("SGVsbG8gV29ybGQ=") == 1

    def test_count_total_pages_pdf_format_explicit_fmt(self, component_class, default_kwargs):
        """Test _count_total_pages with explicit fmt='pdf' returns 1."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": "text"})

        # Even though self.format is "text", explicit fmt="pdf" should return 1
        assert component._count_total_pages("any content", fmt="pdf") == 1

    # ======================== Output scenario tests (Files / Pages / Text) =============
    #
    # Each test verifies the three outputs for a specific format using mock cached data.
    # ----------------------------------------------------------------------------------

    def _make_component_with_cached_data(self, component_class, default_kwargs, fmt, mock_data):
        """Helper: create a component with mock cached data for output tests."""
        component = component_class()
        component.set_attributes({**default_kwargs, "format": fmt})
        # Bypass load_files_base() by injecting cached data directly.
        component._cached_data = mock_data
        return component

    # ---- text format outputs ----

    def test_output_scenario_text_files(self, component_class, default_kwargs, tmp_path):
        """Files output for text format: one row per file with sentinel in raw text."""
        pdf_file = str(tmp_path / "report.pdf")
        mock_data = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nFirst page.\n---ODL_PAGE_BREAK_2---\nSecond page.",
                    "file_path": pdf_file,
                    "format": "text",
                    "source": "report.pdf",
                    "total_pages": 2,
                    "word_count": 4,
                }
            )
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "text", mock_data)
        df = component.load_files()

        assert len(df) == 1
        assert "ODL_PAGE_BREAK" in df.iloc[0]["text"]  # raw data keeps sentinel
        assert df.iloc[0]["total_pages"] == 2

    def test_output_scenario_text_pages(self, component_class, default_kwargs, tmp_path):
        """Pages output for text format: one row per page, sentinel removed."""
        pdf_file = str(tmp_path / "report.pdf")
        mock_data = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nFirst page.\n---ODL_PAGE_BREAK_2---\nSecond page.",
                    "source": "report.pdf",
                    "file_path": pdf_file,
                    "format": "text",
                }
            )
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "text", mock_data)
        df = component.load_files_by_page()

        assert len(df) == 2
        assert df.iloc[0]["page_number"] == 1
        assert "First page" in df.iloc[0]["text"]
        assert "ODL_PAGE_BREAK" not in df.iloc[0]["text"]
        assert df.iloc[1]["page_number"] == 2
        assert "Second page" in df.iloc[1]["text"]

    def test_output_scenario_text_message(self, component_class, default_kwargs, tmp_path):
        """Text (Message) output for text format: sentinel stripped, clean text."""
        pdf_file = str(tmp_path / "report.pdf")
        mock_data = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nFirst page.\n---ODL_PAGE_BREAK_2---\nSecond page.",
                    "file_path": pdf_file,
                    "format": "text",
                    "source": "report.pdf",
                }
            )
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "text", mock_data)
        msg = component.load_files_message()

        assert "First page" in msg.text
        assert "Second page" in msg.text
        assert "ODL_PAGE_BREAK" not in msg.text

    # ---- json format outputs ----

    def test_output_scenario_json_files(self, component_class, default_kwargs, tmp_path):
        """Files output for JSON format: raw JSON string in text field."""
        pdf_file = str(tmp_path / "report.pdf")
        json_content = json.dumps(
            {
                "number of pages": 3,
                "kids": [
                    {"page number": 1, "content": "Page 1 text"},
                    {"page number": 2, "content": "Page 2 text"},
                    {"page number": 3, "content": "Page 3 text"},
                ],
            }
        )
        mock_data = [
            Data(
                data={
                    "text": json_content,
                    "file_path": pdf_file,
                    "format": "json",
                    "source": "report.pdf",
                    "total_pages": 3,
                    "word_count": 9,
                }
            )
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "json", mock_data)
        df = component.load_files()

        assert len(df) == 1
        # Raw JSON is preserved in Files output
        parsed = json.loads(df.iloc[0]["text"])
        assert parsed["number of pages"] == 3

    def test_output_scenario_json_pages(self, component_class, default_kwargs, tmp_path):
        """Pages output for JSON format: parsed kids grouped by page number."""
        pdf_file = str(tmp_path / "report.pdf")
        json_content = json.dumps(
            {
                "number of pages": 2,
                "kids": [
                    {"page number": 1, "content": "Heading"},
                    {"page number": 1, "content": "Paragraph on page 1"},
                    {"page number": 2, "content": "Page 2 content"},
                ],
            }
        )
        mock_data = [
            Data(
                data={
                    "text": json_content,
                    "source": "report.pdf",
                    "file_path": pdf_file,
                    "format": "json",
                }
            )
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "json", mock_data)
        df = component.load_files_by_page()

        assert len(df) == 2
        assert df.iloc[0]["page_number"] == 1
        # Page 1 combines two kids
        assert "Heading" in df.iloc[0]["text"]
        assert "Paragraph on page 1" in df.iloc[0]["text"]
        assert df.iloc[1]["page_number"] == 2
        assert "Page 2 content" in df.iloc[1]["text"]

    def test_output_scenario_json_message(self, component_class, default_kwargs, tmp_path):
        """Text (Message) output for JSON format: raw JSON (no sentinels to strip)."""
        pdf_file = str(tmp_path / "report.pdf")
        json_content = json.dumps({"number of pages": 1, "kids": [{"content": "Hi"}]})
        mock_data = [
            Data(
                data={
                    "text": json_content,
                    "file_path": pdf_file,
                    "format": "json",
                    "source": "report.pdf",
                }
            )
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "json", mock_data)
        msg = component.load_files_message()

        # JSON format has no sentinels, so raw JSON is expected
        assert "number of pages" in msg.text

    # ---- markdown format outputs ----

    def test_output_scenario_markdown_message_no_sentinel(self, component_class, default_kwargs, tmp_path):
        """Text (Message) output for markdown format: sentinel stripped."""
        pdf_file = str(tmp_path / "doc.pdf")
        mock_data = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\n# Title\n---ODL_PAGE_BREAK_2---\n## Section",
                    "file_path": pdf_file,
                    "format": "markdown",
                    "source": "doc.pdf",
                }
            )
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "markdown", mock_data)
        msg = component.load_files_message()

        assert "# Title" in msg.text
        assert "## Section" in msg.text
        assert "ODL_PAGE_BREAK" not in msg.text

    # ---- html format outputs ----

    def test_output_scenario_html_message_no_sentinel(self, component_class, default_kwargs, tmp_path):
        """Text (Message) output for HTML format: sentinel stripped."""
        pdf_file = str(tmp_path / "doc.pdf")
        mock_data = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\n<p>Para 1</p>\n---ODL_PAGE_BREAK_2---\n<p>Para 2</p>",
                    "file_path": pdf_file,
                    "format": "html",
                    "source": "doc.pdf",
                }
            )
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "html", mock_data)
        msg = component.load_files_message()

        assert "<p>Para 1</p>" in msg.text
        assert "<p>Para 2</p>" in msg.text
        assert "ODL_PAGE_BREAK" not in msg.text

    # ---- pdf format outputs ----

    def test_output_scenario_pdf_files(self, component_class, default_kwargs, tmp_path):
        """Files output for PDF format: base64 content in text field."""
        pdf_file = str(tmp_path / "doc.pdf")
        mock_data = [
            Data(
                data={
                    "text": "JVBER0base64content",
                    "file_path": pdf_file,
                    "format": "pdf",
                    "source": "doc.pdf",
                    "total_pages": 1,
                    "word_count": 0,
                }
            )
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "pdf", mock_data)
        df = component.load_files()

        assert len(df) == 1
        assert df.iloc[0]["text"] == "JVBER0base64content"
        assert df.iloc[0]["word_count"] == 0

    def test_output_scenario_pdf_pages_empty(self, component_class, default_kwargs, tmp_path):
        """Pages output for PDF format: empty (binary cannot be split by page)."""
        pdf_file = str(tmp_path / "doc.pdf")
        mock_data = [
            Data(
                data={
                    "text": "JVBER0base64content",
                    "source": "doc.pdf",
                    "file_path": pdf_file,
                    "format": "pdf",
                }
            )
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "pdf", mock_data)
        df = component.load_files_by_page()

        assert len(df) == 0

    def test_output_scenario_pdf_message(self, component_class, default_kwargs, tmp_path):
        """Text (Message) output for PDF format: base64 content (no sentinels)."""
        pdf_file = str(tmp_path / "doc.pdf")
        mock_data = [
            Data(
                data={
                    "text": "JVBER0base64content",
                    "file_path": pdf_file,
                    "format": "pdf",
                    "source": "doc.pdf",
                }
            )
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "pdf", mock_data)
        msg = component.load_files_message()

        assert msg.text == "JVBER0base64content"

    # ---- multi-file scenario ----

    def test_output_scenario_multi_file_text_message(self, component_class, default_kwargs, tmp_path):
        """Text (Message) output with multiple files: joined with separator, sentinels stripped."""
        mock_data = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nFile A page 1\n---ODL_PAGE_BREAK_2---\nFile A page 2",
                    "file_path": str(tmp_path / "a.pdf"),
                    "format": "text",
                    "source": "a.pdf",
                }
            ),
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nFile B page 1",
                    "file_path": str(tmp_path / "b.pdf"),
                    "format": "text",
                    "source": "b.pdf",
                }
            ),
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "text", mock_data)
        msg = component.load_files_message()

        assert "File A page 1" in msg.text
        assert "File A page 2" in msg.text
        assert "File B page 1" in msg.text
        assert "ODL_PAGE_BREAK" not in msg.text

    def test_output_scenario_multi_file_pages(self, component_class, default_kwargs, tmp_path):
        """Pages output with multiple files: pages from all files combined."""
        mock_data = [
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nFile A page 1\n---ODL_PAGE_BREAK_2---\nFile A page 2",
                    "source": "a.pdf",
                    "file_path": str(tmp_path / "a.pdf"),
                    "format": "text",
                }
            ),
            Data(
                data={
                    "text": "\n---ODL_PAGE_BREAK_1---\nFile B page 1",
                    "source": "b.pdf",
                    "file_path": str(tmp_path / "b.pdf"),
                    "format": "text",
                }
            ),
        ]
        component = self._make_component_with_cached_data(component_class, default_kwargs, "text", mock_data)
        df = component.load_files_by_page()

        assert len(df) == 3  # 2 pages from A + 1 page from B
        sources = list(df["source"])
        assert sources.count("a.pdf") == 2
        assert sources.count("b.pdf") == 1

    # ----------------------- API parameter correctness tests -----------------------

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_content_safety_enabled_not_in_convert_params(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that content_safety_off is not passed to API when safety is enabled."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("Extracted text")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "content_safety": "enabled"})
        component.log = Mock()

        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        call_args = convert_calls[0]
        # When content safety is enabled, content_safety_off should not be in params
        assert "content_safety_off" not in call_args

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_content_safety_disabled_in_convert_params(
        self, _mock_java_check, component_class, default_kwargs, tmp_path
    ):
        """Test that content_safety_off is passed to API when safety is disabled."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("Extracted text")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes(
            {
                **default_kwargs,
                "content_safety": "disabled",
                "content_safety_filters": "hidden-text,off-page",
            }
        )
        component.log = Mock()

        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        call_args = convert_calls[0]
        # When content safety is disabled, content_safety_off should be in params
        assert call_args["content_safety_off"] == ["hidden-text", "off-page"]

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_image_dir_passed_when_set(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test that image_dir is passed to convert() when explicitly set."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("Extracted text")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "image_dir": str(tmp_path / "images"), "image_output": "external"})
        component.log = Mock()

        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        call_args = convert_calls[0]
        assert call_args["image_dir"] == str(tmp_path / "images")

    @patch.object(OpenDataLoaderPDFComponent, "_check_java_installed", return_value=True)
    def test_image_dir_excluded_when_empty(self, _mock_java_check, component_class, default_kwargs, tmp_path):
        """Test that image_dir is not passed to convert() when empty."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        convert_calls = []
        mock_opendataloader = MagicMock()

        def mock_convert(**kwargs):
            convert_calls.append(kwargs)
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "test.txt").write_text("Extracted text")

        mock_opendataloader.convert = mock_convert

        component = component_class()
        component.set_attributes({**default_kwargs, "image_dir": ""})
        component.log = Mock()

        mock_base_file = Mock()
        mock_base_file.path = pdf_file
        mock_base_file.data = [Data(data={"file_path": str(pdf_file)})]
        mock_base_file.delete_after_processing = False

        with (
            patch.dict(sys.modules, {"opendataloader_pdf": mock_opendataloader}),
            patch("tempfile.mkdtemp", return_value=str(output_dir)),
            patch("shutil.rmtree"),
        ):
            component.process_files([mock_base_file])

        call_args = convert_calls[0]
        assert "image_dir" not in call_args
