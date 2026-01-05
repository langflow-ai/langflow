from unittest.mock import Mock, patch

import pytest
from lfx.components.youtube.youtube_transcripts import YouTubeTranscriptsComponent
from lfx.schema import Data, DataFrame, Message
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled

from tests.base import ComponentTestBaseWithoutClient


class FetchedTranscriptSnippetMock:
    """Mock for youtube_transcript_api FetchedTranscriptSnippet."""

    def __init__(self, text: str, start: float, duration: float):
        self.text = text
        self.start = start
        self.duration = duration


class TestYouTubeTranscriptsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return YouTubeTranscriptsComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "url": "https://www.youtube.com/watch?v=test123",
            "chunk_size_seconds": 60,
            "translation": "",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        return []

    @pytest.fixture
    def mock_transcript_data(self):
        """Return mock transcript data using new API format."""
        return [
            FetchedTranscriptSnippetMock("First part of the transcript", 0.0, 30.0),
            FetchedTranscriptSnippetMock("Second part of the transcript", 30.0, 30.0),
            FetchedTranscriptSnippetMock("Third part of the transcript", 60.0, 30.0),
        ]

    @pytest.fixture
    def mock_transcript_list(self):
        """Return mock transcript list."""
        mock_transcript = Mock()
        mock_transcript.video_id = "test123"
        mock_transcript.language_code = "en"
        mock_transcript.language = "English"

        mock_list = Mock()
        mock_list.find_transcript.return_value = mock_transcript
        mock_list.find_generated_transcript.return_value = mock_transcript
        return mock_list

    def test_basic_setup(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)
        assert component.url == default_kwargs["url"]
        assert component.chunk_size_seconds == default_kwargs["chunk_size_seconds"]
        assert component.translation == default_kwargs["translation"]

    def test_extract_video_id_watch_url(self, component_class):
        """Test video ID extraction from standard watch URL."""
        component = component_class()
        component.set_attributes({"url": "https://www.youtube.com/watch?v=abc123"})
        video_id = component._extract_video_id(component.url)
        assert video_id == "abc123"

    def test_extract_video_id_short_url(self, component_class):
        """Test video ID extraction from short URL."""
        component = component_class()
        component.set_attributes({"url": "https://youtu.be/xyz789"})
        video_id = component._extract_video_id(component.url)
        assert video_id == "xyz789"

    def test_extract_video_id_embed_url(self, component_class):
        """Test video ID extraction from embed URL."""
        component = component_class()
        component.set_attributes({"url": "https://www.youtube.com/embed/embed123"})
        video_id = component._extract_video_id(component.url)
        assert video_id == "embed123"

    def test_extract_video_id_with_params(self, component_class):
        """Test video ID extraction from URL with extra parameters."""
        component = component_class()
        component.set_attributes({"url": "https://www.youtube.com/watch?v=param123&t=30s"})
        video_id = component._extract_video_id(component.url)
        assert video_id == "param123"

    def test_extract_video_id_invalid_url(self, component_class):
        """Test video ID extraction from invalid URL."""
        component = component_class()
        component.set_attributes({"url": "https://example.com/not-a-youtube-url"})
        with pytest.raises(ValueError, match="Could not extract video ID"):
            component._extract_video_id(component.url)

    @patch("lfx.components.youtube.youtube_transcripts.YouTubeTranscriptApi")
    def test_get_dataframe_output_success(
        self, mock_api_class, component_class, default_kwargs, mock_transcript_data, mock_transcript_list
    ):
        """Test successful DataFrame output generation."""
        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list
        mock_api.fetch.return_value = mock_transcript_data
        mock_api_class.return_value = mock_api

        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.get_dataframe_output()

        assert isinstance(result, DataFrame)
        result_df = result
        assert len(result_df) == 2  # Two chunks (0-60s and 60-90s)
        assert list(result_df.columns) == ["timestamp", "text"]
        assert result_df.iloc[0]["timestamp"] == "00:00"
        assert result_df.iloc[1]["timestamp"] == "01:00"
        assert "First part" in result_df.iloc[0]["text"]
        assert "Third part" in result_df.iloc[1]["text"]

    @patch("lfx.components.youtube.youtube_transcripts.YouTubeTranscriptApi")
    def test_get_message_output_success(
        self, mock_api_class, component_class, default_kwargs, mock_transcript_data, mock_transcript_list
    ):
        """Test successful Message output generation."""
        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list
        mock_api.fetch.return_value = mock_transcript_data
        mock_api_class.return_value = mock_api

        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.get_message_output()

        assert isinstance(result, Message)
        assert "First part of the transcript" in result.text
        assert "Second part of the transcript" in result.text
        assert "Third part of the transcript" in result.text

    @patch("lfx.components.youtube.youtube_transcripts.YouTubeTranscriptApi")
    def test_get_data_output_success(
        self, mock_api_class, component_class, default_kwargs, mock_transcript_data, mock_transcript_list
    ):
        """Test successful Data output generation."""
        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list
        mock_api.fetch.return_value = mock_transcript_data
        mock_api_class.return_value = mock_api

        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.get_data_output()

        assert isinstance(result, Data)
        assert result.data["video_url"] == default_kwargs["url"]
        assert "First part" in result.data["transcript"]
        assert "Second part" in result.data["transcript"]
        assert "Third part" in result.data["transcript"]
        assert "error" not in result.data

    @patch("lfx.components.youtube.youtube_transcripts.YouTubeTranscriptApi")
    def test_transcript_disabled_error(self, mock_api_class, component_class, default_kwargs):
        """Test handling of TranscriptsDisabled error."""
        mock_api = Mock()
        mock_api.list.side_effect = TranscriptsDisabled("test123")
        mock_api_class.return_value = mock_api

        component = component_class()
        component.set_attributes(default_kwargs)

        # Test DataFrame output
        df_result = component.get_dataframe_output()
        assert isinstance(df_result, DataFrame)
        assert len(df_result) == 1
        assert "error" in df_result.columns
        assert "Failed to get YouTube transcripts" in df_result["error"][0]

        # Test Message output
        msg_result = component.get_message_output()
        assert isinstance(msg_result, Message)
        assert "Failed to get YouTube transcripts" in msg_result.text

        # Test Data output
        data_result = component.get_data_output()
        assert isinstance(data_result, Data)
        assert data_result.data["error"] is not None
        assert data_result.data["transcript"] == ""

    @patch("lfx.components.youtube.youtube_transcripts.YouTubeTranscriptApi")
    def test_no_transcript_found_error(self, mock_api_class, component_class, default_kwargs, mock_transcript_list):
        """Test handling of NoTranscriptFound error."""
        mock_transcript_list.find_transcript.side_effect = NoTranscriptFound(
            "test123", ["en"], {"en": {"translationLanguages": []}}
        )
        mock_transcript_list.find_generated_transcript.side_effect = NoTranscriptFound(
            "test123", ["en"], {"en": {"translationLanguages": []}}
        )

        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list
        mock_api_class.return_value = mock_api

        component = component_class()
        component.set_attributes(default_kwargs)

        data_result = component.get_data_output()
        assert isinstance(data_result, Data)
        assert data_result.data["error"] is not None
        assert data_result.data["transcript"] == ""

    def test_translation_setting(self, component_class):
        """Test setting different translation languages."""
        component = component_class()
        test_cases = ["en", "es", "fr", ""]

        for lang in test_cases:
            component.set_attributes({"url": "https://youtube.com/watch?v=test", "translation": lang})
            assert component.translation == lang

    @patch("lfx.components.youtube.youtube_transcripts.YouTubeTranscriptApi")
    def test_empty_transcript_handling(self, mock_api_class, component_class, default_kwargs, mock_transcript_list):
        """Test handling of empty transcript response."""
        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list
        mock_api.fetch.return_value = []
        mock_api_class.return_value = mock_api

        component = component_class()
        component.set_attributes(default_kwargs)

        # Test Data output with empty transcript
        data_result = component.get_data_output()
        assert data_result.data["error"] == "No transcripts found."
        assert data_result.data["transcript"] == ""

        # Test DataFrame output with empty transcript
        df_result = component.get_dataframe_output()
        assert len(df_result) == 0

    @patch("lfx.components.youtube.youtube_transcripts.YouTubeTranscriptApi")
    def test_chunking_behavior(self, mock_api_class, component_class, default_kwargs, mock_transcript_list):
        """Test transcript chunking with custom chunk size."""
        # Create transcript data spanning 150 seconds
        mock_data = [
            FetchedTranscriptSnippetMock("Part 1", 0.0, 30.0),
            FetchedTranscriptSnippetMock("Part 2", 30.0, 30.0),
            FetchedTranscriptSnippetMock("Part 3", 60.0, 30.0),
            FetchedTranscriptSnippetMock("Part 4", 90.0, 30.0),
            FetchedTranscriptSnippetMock("Part 5", 120.0, 30.0),
        ]

        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list
        mock_api.fetch.return_value = mock_data
        mock_api_class.return_value = mock_api

        # Test with 60-second chunks
        component = component_class()
        component.set_attributes({**default_kwargs, "chunk_size_seconds": 60})
        result = component.get_dataframe_output()

        # Should have 3 chunks: 0-60s, 60-120s, 120-150s
        assert len(result) == 3
        assert result.iloc[0]["timestamp"] == "00:00"
        assert result.iloc[1]["timestamp"] == "01:00"
        assert result.iloc[2]["timestamp"] == "02:00"

    @patch("lfx.components.youtube.youtube_transcripts.YouTubeTranscriptApi")
    def test_translation_parameter(
        self, mock_api_class, component_class, default_kwargs, mock_transcript_list, mock_transcript_data
    ):
        """Test transcript translation functionality."""
        mock_translated = Mock()
        mock_translated.video_id = "test123"
        mock_translated.language_code = "es"
        mock_transcript_list.find_transcript.return_value.translate.return_value = mock_translated

        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list
        mock_api.fetch.return_value = mock_transcript_data
        mock_api_class.return_value = mock_api

        component = component_class()
        component.set_attributes({**default_kwargs, "translation": "es"})
        result = component.get_message_output()

        # Verify translate was called
        mock_transcript_list.find_transcript.return_value.translate.assert_called_once_with("es")
        assert isinstance(result, Message)

    @patch("lfx.components.youtube.youtube_transcripts.YouTubeTranscriptApi")
    def test_general_exception_handling(self, mock_api_class, component_class, default_kwargs):
        """Test handling of general exceptions."""
        mock_api = Mock()
        mock_api.list.side_effect = RuntimeError("Network error")
        mock_api_class.return_value = mock_api

        component = component_class()
        component.set_attributes(default_kwargs)

        result = component.get_data_output()
        assert isinstance(result, Data)
        assert result.data["error"] is not None
        assert "Could not retrieve transcripts" in str(result.data["error"])
