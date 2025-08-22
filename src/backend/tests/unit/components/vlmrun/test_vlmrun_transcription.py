from unittest.mock import Mock, patch

import pytest
from langflow.components.vlmrun.vlmrun_transcription import VLMRunTranscription
from langflow.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient


class TestVLMRunTranscription(ComponentTestBaseWithoutClient):
    """Test class for VLM Run Transcription component."""

    def _create_mock_usage(self, total_tokens=100, prompt_tokens=70, completion_tokens=30):
        """Helper method to create a mock usage object."""
        mock_usage = Mock()
        mock_usage.configure_mock(
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model_dump=Mock(return_value={"total_tokens": total_tokens}),
            dict=Mock(return_value={"total_tokens": total_tokens}),
        )
        return mock_usage

    def _create_mock_response(self, prediction_id, segments, duration, usage, status="completed"):
        """Helper method to create a mock VLM Run response object."""
        mock_response = Mock()
        mock_response.configure_mock(
            id=prediction_id,
            response={"segments": segments, "metadata": {"duration": duration}},
            usage=usage,
            status=status,
        )
        return mock_response

    def _create_mock_vlm_client(self, audio_response=None, video_response=None):
        """Helper method to create a mock VLM Run client."""
        mock_client = Mock()

        if audio_response:
            mock_client.audio.generate.return_value = audio_response
            mock_client.predictions.wait.return_value = audio_response
        if video_response:
            mock_client.video.generate.return_value = video_response
            mock_client.predictions.wait.return_value = video_response

        return mock_client

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

    @patch("builtins.__import__")
    def test_vlmrun_import_error(self, mock_import, component_class, default_kwargs):
        """Test handling of VLM Run SDK import error."""
        # Configure mock import to raise ImportError for vlmrun.client
        original_import = __import__

        def side_effect(name, *args):
            if name == "vlmrun.client":
                error_msg = "No module named 'vlmrun'"
                raise ImportError(error_msg)
            return original_import(name, *args)

        mock_import.side_effect = side_effect

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

    @patch("vlmrun.client.VLMRun")
    def test_single_audio_file_with_mocked_client(self, mock_vlmrun_class, component_class, default_kwargs):
        """Test single audio file processing with mocked VLMRun client."""
        # Create mock objects using helper methods
        mock_usage = self._create_mock_usage(total_tokens=150, prompt_tokens=100, completion_tokens=50)
        segments = [{"audio": {"content": "Hello world"}}, {"audio": {"content": "This is a test"}}]
        mock_response = self._create_mock_response("test-prediction-123", segments, 10.5, mock_usage)

        # Configure mock client
        mock_client = self._create_mock_vlm_client(audio_response=mock_response)
        mock_vlmrun_class.return_value = mock_client

        component = component_class(**default_kwargs)
        component.media_files = ["/path/to/test.mp3"]

        result = component.process_media()

        assert isinstance(result, Data)
        assert "results" in result.data
        assert len(result.data["results"]) == 1

        audio_result = result.data["results"][0]
        assert audio_result["prediction_id"] == "test-prediction-123"
        assert audio_result["transcription"] == "Hello world This is a test"
        assert audio_result["metadata"]["duration"] == 10.5
        assert audio_result["status"] == "completed"
        assert audio_result["usage"].total_tokens == 150
        assert "filename" in audio_result
        assert audio_result["filename"] == "test.mp3"

        # Verify the client was called correctly
        mock_client.audio.generate.assert_called_once()
        mock_client.predictions.wait.assert_called_once_with(mock_response.id, timeout=600)

        # Verify API key was passed correctly
        mock_vlmrun_class.assert_called_once_with(api_key="test-api-key")

    @patch("vlmrun.client.VLMRun")
    def test_video_file_with_audio_content(self, mock_vlmrun_class, component_class, default_kwargs):
        """Test video file processing that includes both video and audio content."""
        # Create mock objects using helper methods
        mock_usage = self._create_mock_usage(total_tokens=300, prompt_tokens=200, completion_tokens=100)
        segments = [
            {"video": {"content": "Scene description 1"}, "audio": {"content": "Dialog line 1"}},
            {"video": {"content": "Scene description 2"}, "audio": {"content": "Dialog line 2"}},
            {"video": {"content": "Scene description 3"}},
        ]
        mock_response = self._create_mock_response("test-video-456", segments, 120.0, mock_usage)

        # Configure mock client
        mock_client = self._create_mock_vlm_client(video_response=mock_response)
        mock_vlmrun_class.return_value = mock_client

        component = component_class(**default_kwargs)
        component.media_type = "video"
        component.media_files = ["/path/to/test.mp4"]

        result = component.process_media()

        assert isinstance(result, Data)
        assert "results" in result.data
        assert len(result.data["results"]) == 1

        video_result = result.data["results"][0]
        assert video_result["prediction_id"] == "test-video-456"
        # Check that transcription includes both video content and audio in brackets
        expected_transcription = (
            "Scene description 1 [Audio: Dialog line 1] Scene description 2 [Audio: Dialog line 2] Scene description 3"
        )
        assert video_result["transcription"] == expected_transcription
        assert video_result["metadata"]["media_type"] == "video"
        assert video_result["metadata"]["duration"] == 120.0
        assert video_result["status"] == "completed"
        assert video_result["usage"].total_tokens == 300

        # Verify the client was called correctly
        mock_client.video.generate.assert_called_once()
        mock_client.predictions.wait.assert_called_once_with(mock_response.id, timeout=600)

        # Verify API key was passed correctly
        mock_vlmrun_class.assert_called_once_with(api_key="test-api-key")

    @patch("vlmrun.client.VLMRun")
    def test_multiple_files_combined_transcription(self, mock_vlmrun_class, component_class, default_kwargs):
        """Test processing multiple files returns combined transcription."""
        # Create mock objects using helper methods
        mock_usage_1 = self._create_mock_usage(total_tokens=50)
        mock_usage_2 = self._create_mock_usage(total_tokens=60)

        segments_1 = [{"audio": {"content": "File 1 content"}}]
        segments_2 = [{"audio": {"content": "File 2 content"}}]

        mock_response_1 = self._create_mock_response("pred-1", segments_1, 5, mock_usage_1)
        mock_response_2 = self._create_mock_response("pred-2", segments_2, 7, mock_usage_2)

        # Configure mock client to return different responses for each call
        mock_client = Mock()
        mock_client.audio.generate.side_effect = [mock_response_1, mock_response_2]
        mock_client.predictions.wait.side_effect = [mock_response_1, mock_response_2]
        mock_vlmrun_class.return_value = mock_client

        component = component_class(**default_kwargs)
        component.media_files = ["/path/to/file1.mp3", "/path/to/file2.mp3"]

        result = component.process_media()

        assert isinstance(result, Data)
        assert "results" in result.data
        assert len(result.data["results"]) == 2
        assert result.data["total_files"] == 2

        # Verify individual transcription results are accessible
        assert result.data["results"][0]["transcription"] == "File 1 content"
        assert result.data["results"][1]["transcription"] == "File 2 content"
        assert result.data["results"][0]["filename"] == "file1.mp3"
        assert result.data["results"][1]["filename"] == "file2.mp3"

        # Verify the client was called correctly for both files
        assert mock_client.audio.generate.call_count == 2
        assert mock_client.predictions.wait.call_count == 2

        # Verify API key was passed correctly
        mock_vlmrun_class.assert_called_once_with(api_key="test-api-key")

        # Verify predictions.wait was called with correct IDs and timeout
        wait_calls = mock_client.predictions.wait.call_args_list
        assert wait_calls[0][0][0] == "pred-1"
        assert wait_calls[0][1]["timeout"] == 600
        assert wait_calls[1][0][0] == "pred-2"
        assert wait_calls[1][1]["timeout"] == 600

    @patch("vlmrun.client.VLMRun")
    def test_url_input_processing(self, mock_vlmrun_class, component_class, default_kwargs):
        """Test processing media from URL."""
        # Create mock objects using helper methods
        mock_usage = self._create_mock_usage(total_tokens=75)
        segments = [{"audio": {"content": "URL content"}}]
        mock_response = self._create_mock_response("url-pred-789", segments, 15, mock_usage)

        # Configure mock client
        mock_client = Mock()
        mock_client.audio.generate.return_value = mock_response
        mock_client.predictions.wait.return_value = mock_response
        mock_vlmrun_class.return_value = mock_client

        component = component_class(**default_kwargs)
        component.media_url = "https://example.com/media.mp3"

        result = component.process_media()

        assert isinstance(result, Data)
        assert "results" in result.data
        audio_result = result.data["results"][0]
        assert "source" in audio_result  # URL should use 'source' not 'filename'
        assert audio_result["source"] == "https://example.com/media.mp3"

        # Verify the client was called with the correct URL and API key
        mock_client.audio.generate.assert_called_once()
        mock_client.predictions.wait.assert_called_once_with(mock_response.id, timeout=600)
        mock_vlmrun_class.assert_called_once_with(api_key="test-api-key")

        # Verify URL parameter was passed correctly
        call_args = mock_client.audio.generate.call_args
        assert "url" in call_args.kwargs
        assert call_args.kwargs["url"] == "https://example.com/media.mp3"

    def test_advanced_inputs_added(self, component_class):
        """Test that new advanced inputs are properly added."""
        component = component_class()
        inputs_dict = {inp.name: inp for inp in component.inputs}

        # Check timeout_seconds input
        assert "timeout_seconds" in inputs_dict
        assert inputs_dict["timeout_seconds"].display_name == "Timeout (seconds)"
        assert inputs_dict["timeout_seconds"].value == 600
        assert inputs_dict["timeout_seconds"].advanced is True

        # Check domain input
        assert "domain" in inputs_dict
        assert inputs_dict["domain"].display_name == "Processing Domain"
        assert inputs_dict["domain"].options == ["transcription"]
        assert inputs_dict["domain"].value == "transcription"
        assert inputs_dict["domain"].advanced is True

    @patch("vlmrun.client.VLMRun")
    def test_api_error_handling(self, mock_vlmrun_class, component_class, default_kwargs):
        """Test handling of API errors from VLM Run service."""
        # Configure mock client to raise a ValueError (which gets caught specifically)
        mock_client = Mock()
        mock_client.audio.generate.side_effect = ValueError("API request failed")
        mock_vlmrun_class.return_value = mock_client

        component = component_class(**default_kwargs)
        component.media_files = ["/path/to/test.mp3"]

        result = component.process_media()

        assert isinstance(result, Data)
        assert "error" in result.data
        assert "Processing failed: API request failed" in result.data["error"]
        assert component.status is not None

        # Verify the client was called correctly
        mock_client.audio.generate.assert_called_once()
        mock_vlmrun_class.assert_called_once_with(api_key="test-api-key")

    @patch("vlmrun.client.VLMRun")
    def test_timeout_parameter_usage(self, mock_vlmrun_class, component_class, default_kwargs):
        """Test that timeout parameter is passed to the VLM Run client."""
        # Create mock objects using helper methods
        mock_usage = self._create_mock_usage(total_tokens=100)
        segments = [{"audio": {"content": "Test content"}}]
        mock_response = self._create_mock_response("test-id", segments, 10, mock_usage)

        mock_client = self._create_mock_vlm_client(audio_response=mock_response)
        mock_vlmrun_class.return_value = mock_client

        # Set custom timeout
        component = component_class(**default_kwargs)
        component.timeout_seconds = 300
        component.media_files = ["/path/to/test.mp3"]

        result = component.process_media()

        assert isinstance(result, Data)
        assert "results" in result.data

        # Verify timeout was passed to predictions.wait
        mock_client.predictions.wait.assert_called_once_with(mock_response.id, timeout=300)
