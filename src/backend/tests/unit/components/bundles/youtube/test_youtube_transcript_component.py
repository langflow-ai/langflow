from unittest.mock import Mock, patch

import pytest
from langflow.schema import Data, DataFrame, Message
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled

from lfx.components.youtube.youtube_transcripts import YouTubeTranscriptsComponent
from tests.base import ComponentTestBaseWithoutClient


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
        """Return mock transcript data for testing."""
        return [
            Mock(page_content="First part of the transcript", metadata={"start_seconds": 0}),
            Mock(page_content="Second part of the transcript", metadata={"start_seconds": 60}),
        ]

    def test_basic_setup(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)
        assert component.url == default_kwargs["url"]
        assert component.chunk_size_seconds == default_kwargs["chunk_size_seconds"]
        assert component.translation == default_kwargs["translation"]

    @patch("lfx.components.youtube.youtube_transcripts.YoutubeLoader")
    def test_get_dataframe_output_success(self, mock_loader, component_class, default_kwargs, mock_transcript_data):
        """Test successful DataFrame output generation."""
        mock_loader.from_youtube_url.return_value.load.return_value = mock_transcript_data

        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.get_dataframe_output()

        assert isinstance(result, DataFrame)
        result_df = result  # More descriptive variable name
        assert len(result_df) == 2
        assert list(result_df.columns) == ["timestamp", "text"]
        assert result_df.iloc[0]["timestamp"] == "00:00"
        assert result_df.iloc[1]["timestamp"] == "01:00"
        assert result_df.iloc[0]["text"] == "First part of the transcript"

    @patch("lfx.components.youtube.youtube_transcripts.YoutubeLoader")
    def test_get_message_output_success(self, mock_loader, component_class, default_kwargs, mock_transcript_data):
        """Test successful Message output generation."""
        mock_loader.from_youtube_url.return_value.load.return_value = mock_transcript_data

        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.get_message_output()

        assert isinstance(result, Message)
        assert result.text == "First part of the transcript"

    @patch("lfx.components.youtube.youtube_transcripts.YoutubeLoader")
    def test_get_data_output_success(self, mock_loader, component_class, default_kwargs, mock_transcript_data):
        """Test successful Data output generation."""
        mock_loader.from_youtube_url.return_value.load.return_value = mock_transcript_data

        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.get_data_output()

        assert isinstance(result, Data)
        assert result.data["video_url"] == default_kwargs["url"]
        assert result.data["transcript"] == "First part of the transcript Second part of the transcript"
        assert "error" not in result.data

    @patch("lfx.components.youtube.youtube_transcripts.YoutubeLoader")
    def test_transcript_disabled_error(self, mock_loader, component_class, default_kwargs):
        """Test handling of TranscriptsDisabled error."""
        error_message = "Transcripts are disabled for this video"

        # Mock the load method to raise TranscriptsDisabled
        def raise_error(*_):  # Use underscore to indicate unused arguments
            raise TranscriptsDisabled(error_message)

        mock_loader.from_youtube_url.return_value.load.side_effect = raise_error

        component = component_class()
        component.set_attributes(default_kwargs)

        # Test DataFrame output
        df_result = component.get_dataframe_output()
        assert isinstance(df_result, DataFrame)
        assert len(df_result) == 1  # One row for error message
        assert "error" in df_result.columns
        assert "Failed to get YouTube transcripts" in df_result["error"][0]

        # Test Message output
        msg_result = component.get_message_output()
        assert isinstance(msg_result, Message)
        assert "Failed to get YouTube transcripts" in msg_result.text

        # Test Data output
        data_result = component.get_data_output()
        assert isinstance(data_result, Data)
        assert "error" in data_result.data
        assert data_result.data["transcript"] == ""

    @patch("lfx.components.youtube.youtube_transcripts.YoutubeLoader")
    def test_no_transcript_found_error(self, mock_loader, component_class, default_kwargs):
        """Test handling of NoTranscriptFound error."""
        video_id = "test123"
        requested_langs = ["en"]
        transcript_data = {"en": {"translationLanguages": []}}

        # Mock the load method to raise NoTranscriptFound
        def raise_error(*_):  # Use underscore to indicate unused arguments
            raise NoTranscriptFound(video_id, requested_langs, transcript_data)

        mock_loader.from_youtube_url.return_value.load.side_effect = raise_error

        component = component_class()
        component.set_attributes(default_kwargs)

        data_result = component.get_data_output()
        assert isinstance(data_result, Data)
        assert "error" in data_result.data
        assert data_result.data["transcript"] == ""

    def test_translation_setting(self, component_class):
        """Test setting different translation languages."""
        component = component_class()
        test_cases = ["en", "es", "fr", ""]

        for lang in test_cases:
            component.set_attributes({"url": "https://youtube.com/watch?v=test", "translation": lang})
            assert component.translation == lang

    @patch("lfx.components.youtube.youtube_transcripts.YoutubeLoader")
    def test_empty_transcript_handling(self, mock_loader, component_class, default_kwargs):
        """Test handling of empty transcript response."""
        mock_loader.from_youtube_url.return_value.load.return_value = []

        component = component_class()
        component.set_attributes(default_kwargs)

        # Test Data output with empty transcript
        data_result = component.get_data_output()
        assert data_result.data["error"] == "No transcripts found."
        assert data_result.data["transcript"] == ""

        # Test DataFrame output with empty transcript
        df_result = component.get_dataframe_output()
        assert len(df_result) == 0
