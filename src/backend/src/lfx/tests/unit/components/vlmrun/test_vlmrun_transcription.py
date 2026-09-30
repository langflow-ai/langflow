from unittest.mock import Mock, patch

import pytest
from langflow.schema.data import Data
from lfx.components.vlmrun import VLMRunTranscription
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
        return {
            "api_key": "test-api-key",  # pragma: allowlist secret
            "media_type": "audio",
            "_session_id": "test-session-123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return file names mapping for different versions."""
        # Since this is a new component, return empty list
        return []

    def test_component_metadata(self, component_class):
        """Test component metadata attributes."""
        # Using pytest comparison for better error messages
        if component_class.display_name != "VLM Run Transcription":
            pytest.fail(f"Expected display_name to be 'VLM Run Transcription', got '{component_class.display_name}'")
        if (
            component_class.description
            != "Extract structured data from audio and video using [VLM Run AI](https://app.vlm.run)"
        ):
            pytest.fail(f"Expected description mismatch, got '{component_class.description}'")
        if component_class.documentation != "https://docs.vlm.run":
            pytest.fail(f"Expected documentation to be 'https://docs.vlm.run', got '{component_class.documentation}'")
        if component_class.icon != "VLMRun":
            pytest.fail(f"Expected icon to be 'VLMRun', got '{component_class.icon}'")
        if component_class.beta is not True:
            pytest.fail(f"Expected beta to be True, got '{component_class.beta}'")

    def test_component_inputs(self, component_class):
        """Test component input definitions."""
        component = component_class()
        inputs_dict = {inp.name: inp for inp in component.inputs}

        # Check API key input
        if "api_key" not in inputs_dict:
            pytest.fail("api_key not found in inputs_dict")
        if inputs_dict["api_key"].display_name != "VLM Run API Key":
            pytest.fail(
                f"Expected api_key display_name to be 'VLM Run API Key', got '{inputs_dict['api_key'].display_name}'"
            )
        if inputs_dict["api_key"].required is not True:
            pytest.fail(f"Expected api_key to be required, got {inputs_dict['api_key'].required}")

        # Check media type input
        if "media_type" not in inputs_dict:
            pytest.fail("media_type not found in inputs_dict")
        if inputs_dict["media_type"].display_name != "Media Type":
            pytest.fail(
                f"Expected media_type display_name to be 'Media Type', got '{inputs_dict['media_type'].display_name}'"
            )
        if inputs_dict["media_type"].options != ["audio", "video"]:
            pytest.fail(
                f"Expected media_type options to be ['audio', 'video'], got {inputs_dict['media_type'].options}"
            )
        if inputs_dict["media_type"].value != "audio":
            pytest.fail(f"Expected media_type value to be 'audio', got '{inputs_dict['media_type'].value}'")

        # Check media files input
        if "media_files" not in inputs_dict:
            pytest.fail("media_files not found in inputs_dict")
        if inputs_dict["media_files"].display_name != "Media Files":
            pytest.fail(
                f"Expected media_files display_name to be 'Media Files', "
                f"got '{inputs_dict['media_files'].display_name}'"
            )
        if inputs_dict["media_files"].is_list is not True:
            pytest.fail(f"Expected media_files.is_list to be True, got {inputs_dict['media_files'].is_list}")
        if inputs_dict["media_files"].required is not False:
            pytest.fail(f"Expected media_files to not be required, got {inputs_dict['media_files'].required}")

        # Check media URL input
        if "media_url" not in inputs_dict:
            pytest.fail("media_url not found in inputs_dict")
        if inputs_dict["media_url"].display_name != "Media URL":
            pytest.fail(
                f"Expected media_url display_name to be 'Media URL', got '{inputs_dict['media_url'].display_name}'"
            )
        if inputs_dict["media_url"].required is not False:
            pytest.fail(f"Expected media_url to not be required, got {inputs_dict['media_url'].required}")
        if inputs_dict["media_url"].advanced is not True:
            pytest.fail(f"Expected media_url to be advanced, got {inputs_dict['media_url'].advanced}")

    def test_component_outputs(self, component_class):
        """Test component output definitions."""
        component = component_class()
        outputs_dict = {out.name: out for out in component.outputs}

        if "result" not in outputs_dict:
            pytest.fail("result not found in outputs_dict")
        if outputs_dict["result"].display_name != "Result":
            pytest.fail(f"Expected result display_name to be 'Result', got '{outputs_dict['result'].display_name}'")
        if outputs_dict["result"].method != "process_media":
            pytest.fail(f"Expected result method to be 'process_media', got '{outputs_dict['result'].method}'")

    def test_no_input_validation(self, component_class, default_kwargs):
        """Test validation when no media input is provided."""
        component = component_class(**default_kwargs)

        result = component.process_media()

        if not isinstance(result, Data):
            pytest.fail(f"Expected result to be Data instance, got {type(result)}")
        if "error" not in result.data:
            pytest.fail("error not found in result.data")
        if result.data["error"] != "Either media files or media URL must be provided":
            pytest.fail(f"Expected error message mismatch, got '{result.data['error']}'")
        if component.status != "Either media files or media URL must be provided":
            pytest.fail(f"Expected status mismatch, got '{component.status}'")

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

        if not isinstance(result, Data):
            pytest.fail(f"Expected result to be Data instance, got {type(result)}")
        if "error" not in result.data:
            pytest.fail("error not found in result.data")
        if "VLM Run SDK not installed" not in result.data["error"]:
            pytest.fail(f"Expected 'VLM Run SDK not installed' in error message, got '{result.data['error']}'")

    def test_frontend_node_generation(self, component_class, default_kwargs):
        """Test frontend node generation."""
        component = component_class(**default_kwargs)

        frontend_node = component.to_frontend_node()

        # Verify node structure
        if frontend_node is None:
            pytest.fail("frontend_node is None")
        if not isinstance(frontend_node, dict):
            pytest.fail(f"Expected frontend_node to be dict, got {type(frontend_node)}")
        if "data" not in frontend_node:
            pytest.fail("data not found in frontend_node")
        if "type" not in frontend_node["data"]:
            pytest.fail("type not found in frontend_node['data']")

        node_data = frontend_node["data"]["node"]
        if "description" not in node_data:
            pytest.fail("description not found in node_data")
        if "icon" not in node_data:
            pytest.fail("icon not found in node_data")
        if "template" not in node_data:
            pytest.fail("template not found in node_data")

        # Verify template has correct inputs
        template = node_data["template"]
        if "api_key" not in template:
            pytest.fail("api_key not found in template")
        if "media_type" not in template:
            pytest.fail("media_type not found in template")
        if "media_files" not in template:
            pytest.fail("media_files not found in template")
        if "media_url" not in template:
            pytest.fail("media_url not found in template")

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
            if file_type not in media_files_input.file_types:
                pytest.fail(f"Expected file type '{file_type}' not found in media_files_input.file_types")

    def test_component_initialization(self, component_class, default_kwargs):
        """Test component can be initialized with default kwargs."""
        component = component_class(**default_kwargs)

        if component.api_key != "test-api-key":  # pragma: allowlist secret
            pytest.fail(f"Expected api_key to be 'test-api-key', got '{component.api_key}'")
        if component.media_type != "audio":
            pytest.fail(f"Expected media_type to be 'audio', got '{component.media_type}'")
        if not hasattr(component, "media_files"):
            pytest.fail("component does not have 'media_files' attribute")
        if not hasattr(component, "media_url"):
            pytest.fail("component does not have 'media_url' attribute")

    def test_media_type_options(self, component_class):
        """Test media type dropdown has correct options."""
        component = component_class()
        inputs_dict = {inp.name: inp for inp in component.inputs}

        media_type_input = inputs_dict["media_type"]
        if media_type_input.options != ["audio", "video"]:
            pytest.fail(f"Expected media_type options to be ['audio', 'video'], got {media_type_input.options}")
        if media_type_input.value != "audio":  # Default value
            pytest.fail(f"Expected media_type value to be 'audio', got '{media_type_input.value}'")

    def test_api_key_info_contains_url(self, component_class):
        """Test that API key input contains app URL for user guidance."""
        component = component_class()
        inputs_dict = {inp.name: inp for inp in component.inputs}

        api_key_input = inputs_dict["api_key"]
        if "https://app.vlm.run" not in api_key_input.info:
            pytest.fail(f"Expected 'https://app.vlm.run' in api_key info, got '{api_key_input.info}'")

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

        if not isinstance(result, Data):
            pytest.fail(f"Expected result to be Data instance, got {type(result)}")
        if "results" not in result.data:
            pytest.fail("results not found in result.data")
        if len(result.data["results"]) != 1:
            pytest.fail(f"Expected 1 result, got {len(result.data['results'])}")

        audio_result = result.data["results"][0]
        if audio_result["prediction_id"] != "test-prediction-123":
            pytest.fail(f"Expected prediction_id to be 'test-prediction-123', got '{audio_result['prediction_id']}'")
        if audio_result["transcription"] != "Hello world This is a test":
            pytest.fail(f"Expected transcription mismatch, got '{audio_result['transcription']}'")
        expected_duration = 10.5
        if audio_result["metadata"]["duration"] != pytest.approx(expected_duration):
            pytest.fail(f"Expected duration to be {expected_duration}, got {audio_result['metadata']['duration']}")
        if audio_result["status"] != "completed":
            pytest.fail(f"Expected status to be 'completed', got '{audio_result['status']}'")
        expected_tokens = 150
        if audio_result["usage"].total_tokens != expected_tokens:
            pytest.fail(f"Expected total_tokens to be {expected_tokens}, got {audio_result['usage'].total_tokens}")
        if "filename" not in audio_result:
            pytest.fail("filename not found in audio_result")
        if audio_result["filename"] != "test.mp3":
            pytest.fail(f"Expected filename to be 'test.mp3', got '{audio_result['filename']}'")

        # Verify the client was called correctly
        mock_client.audio.generate.assert_called_once()
        mock_client.predictions.wait.assert_called_once_with(mock_response.id, timeout=600)

        # Verify API key was passed correctly
        mock_vlmrun_class.assert_called_once_with(
            api_key="test-api-key"  # pragma: allowlist secret
        )

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

        if not isinstance(result, Data):
            pytest.fail(f"Expected result to be Data instance, got {type(result)}")
        if "results" not in result.data:
            pytest.fail("results not found in result.data")
        if len(result.data["results"]) != 1:
            pytest.fail(f"Expected 1 result, got {len(result.data['results'])}")

        video_result = result.data["results"][0]
        if video_result["prediction_id"] != "test-video-456":
            pytest.fail(f"Expected prediction_id to be 'test-video-456', got '{video_result['prediction_id']}'")
        # Check that transcription includes both video content and audio in brackets
        expected_transcription = (
            "Scene description 1 [Audio: Dialog line 1] Scene description 2 [Audio: Dialog line 2] Scene description 3"
        )
        if video_result["transcription"] != expected_transcription:
            pytest.fail(f"Expected transcription mismatch, got '{video_result['transcription']}'")
        if video_result["metadata"]["media_type"] != "video":
            pytest.fail(f"Expected media_type to be 'video', got '{video_result['metadata']['media_type']}'")
        expected_video_duration = 120.0
        if video_result["metadata"]["duration"] != pytest.approx(expected_video_duration):
            pytest.fail(
                f"Expected duration to be {expected_video_duration}, got {video_result['metadata']['duration']}"
            )
        if video_result["status"] != "completed":
            pytest.fail(f"Expected status to be 'completed', got '{video_result['status']}'")
        expected_video_tokens = 300
        if video_result["usage"].total_tokens != expected_video_tokens:
            pytest.fail(
                f"Expected total_tokens to be {expected_video_tokens}, got {video_result['usage'].total_tokens}"
            )

        # Verify the client was called correctly
        mock_client.video.generate.assert_called_once()
        mock_client.predictions.wait.assert_called_once_with(mock_response.id, timeout=600)

        # Verify API key was passed correctly
        mock_vlmrun_class.assert_called_once_with(api_key="test-api-key")  # pragma: allowlist secret

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

        if not isinstance(result, Data):
            pytest.fail(f"Expected result to be Data instance, got {type(result)}")
        if "results" not in result.data:
            pytest.fail("results not found in result.data")
        expected_file_count = 2
        if len(result.data["results"]) != expected_file_count:
            pytest.fail(f"Expected {expected_file_count} results, got {len(result.data['results'])}")
        if result.data["total_files"] != expected_file_count:
            pytest.fail(f"Expected total_files to be {expected_file_count}, got {result.data['total_files']}")

        # Verify individual transcription results are accessible
        if result.data["results"][0]["transcription"] != "File 1 content":
            pytest.fail(
                f"Expected first transcription to be 'File 1 content', "
                f"got '{result.data['results'][0]['transcription']}'"
            )
        if result.data["results"][1]["transcription"] != "File 2 content":
            pytest.fail(
                f"Expected second transcription to be 'File 2 content', "
                f"got '{result.data['results'][1]['transcription']}'"
            )
        if result.data["results"][0]["filename"] != "file1.mp3":
            pytest.fail(f"Expected first filename to be 'file1.mp3', got '{result.data['results'][0]['filename']}'")
        if result.data["results"][1]["filename"] != "file2.mp3":
            pytest.fail(f"Expected second filename to be 'file2.mp3', got '{result.data['results'][1]['filename']}'")

        # Verify the client was called correctly for both files
        if mock_client.audio.generate.call_count != expected_file_count:
            pytest.fail(
                f"Expected audio.generate to be called {expected_file_count} times, "
                f"got {mock_client.audio.generate.call_count}"
            )
        if mock_client.predictions.wait.call_count != expected_file_count:
            pytest.fail(
                f"Expected predictions.wait to be called {expected_file_count} times, "
                f"got {mock_client.predictions.wait.call_count}"
            )

        # Verify API key was passed correctly
        mock_vlmrun_class.assert_called_once_with(api_key="test-api-key")  # pragma: allowlist secret

        # Verify predictions.wait was called with correct IDs and timeout
        wait_calls = mock_client.predictions.wait.call_args_list
        default_timeout = 600
        if wait_calls[0][0][0] != "pred-1":
            pytest.fail(f"Expected first wait call ID to be 'pred-1', got '{wait_calls[0][0][0]}'")
        if wait_calls[0][1]["timeout"] != default_timeout:
            pytest.fail(f"Expected first wait call timeout to be {default_timeout}, got {wait_calls[0][1]['timeout']}")
        if wait_calls[1][0][0] != "pred-2":
            pytest.fail(f"Expected second wait call ID to be 'pred-2', got '{wait_calls[1][0][0]}'")
        if wait_calls[1][1]["timeout"] != default_timeout:
            pytest.fail(f"Expected second wait call timeout to be {default_timeout}, got {wait_calls[1][1]['timeout']}")

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

        if not isinstance(result, Data):
            pytest.fail(f"Expected result to be Data instance, got {type(result)}")
        if "results" not in result.data:
            pytest.fail("results not found in result.data")
        audio_result = result.data["results"][0]
        if "source" not in audio_result:  # URL should use 'source' not 'filename'
            pytest.fail("source not found in audio_result")
        if audio_result["source"] != "https://example.com/media.mp3":
            pytest.fail(f"Expected source to be 'https://example.com/media.mp3', got '{audio_result['source']}'")

        # Verify the client was called with the correct URL and API key
        mock_client.audio.generate.assert_called_once()
        mock_client.predictions.wait.assert_called_once_with(mock_response.id, timeout=600)
        mock_vlmrun_class.assert_called_once_with(api_key="test-api-key")  # pragma: allowlist secret

        # Verify URL parameter was passed correctly
        call_args = mock_client.audio.generate.call_args
        if "url" not in call_args.kwargs:
            pytest.fail("url not found in call_args.kwargs")
        if call_args.kwargs["url"] != "https://example.com/media.mp3":
            pytest.fail(f"Expected url to be 'https://example.com/media.mp3', got '{call_args.kwargs['url']}'")

    def test_advanced_inputs_added(self, component_class):
        """Test that new advanced inputs are properly added."""
        component = component_class()
        inputs_dict = {inp.name: inp for inp in component.inputs}

        # Check timeout_seconds input
        default_timeout = 600
        if "timeout_seconds" not in inputs_dict:
            pytest.fail("timeout_seconds not found in inputs_dict")
        if inputs_dict["timeout_seconds"].display_name != "Timeout (seconds)":
            pytest.fail(
                f"Expected timeout_seconds display_name to be 'Timeout (seconds)', "
                f"got '{inputs_dict['timeout_seconds'].display_name}'"
            )
        if inputs_dict["timeout_seconds"].value != default_timeout:
            pytest.fail(
                f"Expected timeout_seconds value to be {default_timeout}, got {inputs_dict['timeout_seconds'].value}"
            )
        if inputs_dict["timeout_seconds"].advanced is not True:
            pytest.fail(f"Expected timeout_seconds to be advanced, got {inputs_dict['timeout_seconds'].advanced}")

        # Check domain input
        if "domain" not in inputs_dict:
            pytest.fail("domain not found in inputs_dict")
        if inputs_dict["domain"].display_name != "Processing Domain":
            pytest.fail(
                f"Expected domain display_name to be 'Processing Domain', got '{inputs_dict['domain'].display_name}'"
            )
        if inputs_dict["domain"].options != ["transcription"]:
            pytest.fail(f"Expected domain options to be ['transcription'], got {inputs_dict['domain'].options}")
        if inputs_dict["domain"].value != "transcription":
            pytest.fail(f"Expected domain value to be 'transcription', got '{inputs_dict['domain'].value}'")
        if inputs_dict["domain"].advanced is not True:
            pytest.fail(f"Expected domain to be advanced, got {inputs_dict['domain'].advanced}")

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

        if not isinstance(result, Data):
            pytest.fail(f"Expected result to be Data instance, got {type(result)}")
        if "error" not in result.data:
            pytest.fail("error not found in result.data")
        if "Processing failed: API request failed" not in result.data["error"]:
            pytest.fail(
                f"Expected 'Processing failed: API request failed' in error message, got '{result.data['error']}'"
            )
        if component.status is None:
            pytest.fail("Expected component.status to not be None")

        # Verify the client was called correctly
        mock_client.audio.generate.assert_called_once()
        mock_vlmrun_class.assert_called_once_with(api_key="test-api-key")  # pragma: allowlist secret

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

        if not isinstance(result, Data):
            pytest.fail(f"Expected result to be Data instance, got {type(result)}")
        if "results" not in result.data:
            pytest.fail("results not found in result.data")

        # Verify timeout was passed to predictions.wait
        mock_client.predictions.wait.assert_called_once_with(mock_response.id, timeout=300)
