import pytest
from langflow.components.vlmrun.vlmrun_transcription import VLMRunTranscription
from langflow.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient


class TestVLMRunTranscription(ComponentTestBaseWithoutClient):
    """Test class for VLM Run Transcription component."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return VLMRunTranscription

    @pytest.fixture
    def default_kwargs(self):
        """Return default kwargs for component initialization."""
        return {"api_key": "test-api-key", "media_type": "audio", "_session_id": "test-session-123"}

    @pytest.fixture
    def file_names_mapping(self):
        """Return file names mapping for different versions."""
        # Since this is a new component, return empty list
        return []

    def test_component_metadata(self, component_class):
        """Test component metadata attributes."""
        assert component_class.display_name == "VLM Run Transcription"
        assert (
            component_class.description
            == "Extract structured data from audio and video using [VLM Run AI](https://app.vlm.run)"
        )
        assert component_class.documentation == "https://docs.vlm.run"
        assert component_class.icon == "VLMRun"
        assert component_class.beta is True

    def test_component_inputs(self, component_class):
        """Test component input definitions."""
        component = component_class()
        inputs_dict = {inp.name: inp for inp in component.inputs}

        # Check API key input
        assert "api_key" in inputs_dict
        assert inputs_dict["api_key"].display_name == "VLM Run API Key"
        assert inputs_dict["api_key"].required is True

        # Check media type input
        assert "media_type" in inputs_dict
        assert inputs_dict["media_type"].display_name == "Media Type"
        assert inputs_dict["media_type"].options == ["audio", "video"]
        assert inputs_dict["media_type"].value == "audio"

        # Check media files input
        assert "media_files" in inputs_dict
        assert inputs_dict["media_files"].display_name == "Media Files"
        assert inputs_dict["media_files"].is_list is True
        assert inputs_dict["media_files"].required is False

        # Check media URL input
        assert "media_url" in inputs_dict
        assert inputs_dict["media_url"].display_name == "Media URL"
        assert inputs_dict["media_url"].required is False
        assert inputs_dict["media_url"].advanced is True

    def test_component_outputs(self, component_class):
        """Test component output definitions."""
        component = component_class()
        outputs_dict = {out.name: out for out in component.outputs}

        assert "result" in outputs_dict
        assert outputs_dict["result"].display_name == "Result"
        assert outputs_dict["result"].method == "process_media"

    def test_no_input_validation(self, component_class, default_kwargs):
        """Test validation when no media input is provided."""
        component = component_class(**default_kwargs)

        result = component.process_media()

        assert isinstance(result, Data)
        assert "error" in result.data
        assert result.data["error"] == "Either media files or media URL must be provided"
        assert component.status == "Either media files or media URL must be provided"

    def test_vlmrun_import_error(self, component_class, default_kwargs, monkeypatch):
        """Test handling of VLM Run SDK import error."""

        # Mock the vlmrun module to not exist
        def mock_import(name, *args):
            if name == "vlmrun.client":
                msg = "No module named 'vlmrun'"
                raise ImportError(msg)
            return __import__(name, *args)

        monkeypatch.setattr("builtins.__import__", mock_import)

        component = component_class(**default_kwargs)
        component.media_files = ["/path/to/test.mp3"]

        result = component.process_media()

        assert isinstance(result, Data)
        assert "error" in result.data
        assert "VLM Run SDK not installed" in result.data["error"]

    def test_frontend_node_generation(self, component_class, default_kwargs):
        """Test frontend node generation."""
        component = component_class(**default_kwargs)

        frontend_node = component.to_frontend_node()

        # Verify node structure
        assert frontend_node is not None
        assert isinstance(frontend_node, dict)
        assert "data" in frontend_node
        assert "type" in frontend_node["data"]

        node_data = frontend_node["data"]["node"]
        assert "description" in node_data
        assert "icon" in node_data
        assert "template" in node_data

        # Verify template has correct inputs
        template = node_data["template"]
        assert "api_key" in template
        assert "media_type" in template
        assert "media_files" in template
        assert "media_url" in template

    def test_input_field_types(self, component_class):
        """Test that input fields have correct types."""
        component = component_class()
        inputs_dict = {inp.name: inp for inp in component.inputs}

        # Check that media_files accepts the expected file types
        media_files_input = inputs_dict["media_files"]
        expected_audio_types = ["mp3", "wav", "m4a", "flac", "ogg", "opus", "webm", "aac"]
        expected_video_types = ["mp4", "mov", "avi", "mkv", "flv", "wmv", "m4v"]
        expected_types = expected_audio_types + expected_video_types

        for file_type in expected_types:
            assert file_type in media_files_input.file_types

    def test_component_initialization(self, component_class, default_kwargs):
        """Test component can be initialized with default kwargs."""
        component = component_class(**default_kwargs)

        assert component.api_key == "test-api-key"
        assert component.media_type == "audio"
        assert hasattr(component, "media_files")
        assert hasattr(component, "media_url")

    def test_media_type_options(self, component_class):
        """Test media type dropdown has correct options."""
        component = component_class()
        inputs_dict = {inp.name: inp for inp in component.inputs}

        media_type_input = inputs_dict["media_type"]
        assert media_type_input.options == ["audio", "video"]
        assert media_type_input.value == "audio"  # Default value

    def test_api_key_info_contains_url(self, component_class):
        """Test that API key input contains app URL for user guidance."""
        component = component_class()
        inputs_dict = {inp.name: inp for inp in component.inputs}

        api_key_input = inputs_dict["api_key"]
        assert "https://app.vlm.run" in api_key_input.info
