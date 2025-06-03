import pytest
from langflow.components.data import URLComponent
from langflow.components.processing import SplitTextComponent
from langflow.schema import Data, DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestSplitTextComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return SplitTextComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "data_inputs": [Data(text="Hello World")],
            "chunk_overlap": 200,
            "chunk_size": 1000,
            "separator": "\n",
            "session_id": "test_session",
            "sender": "test_sender",
            "sender_name": "test_sender_name",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        return [
            # It was in helpers in version 1.0.19
            {"version": "1.0.19", "module": "helpers", "file_name": "SplitText"},
            {"version": "1.1.0", "module": "processing", "file_name": "split_text"},
            {"version": "1.1.1", "module": "processing", "file_name": "split_text"},
        ]

    def test_split_text_basic(self):
        """Test basic text splitting functionality."""
        component = SplitTextComponent()
        test_text = "This is a test.\nIt has multiple lines.\nEach line should be a chunk."
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text)],
                "chunk_overlap": 0,
                "chunk_size": 15,
                "separator": "\n",
                "text_key": "text",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert len(results) == 3, f"Expected 3 chunks, got {len(results)}"
        assert "This is a test" in results[0].text, f"Expected 'This is a test', got '{results[0].text}'"
        assert "It has multiple lines" in results[1].text, f"Expected 'It has multiple lines', got '{results[1].text}'"
        assert "Each line should be a chunk" in results[2].text, (
            f"Expected 'Each line should be a chunk', got '{results[2].text}'"
        )

    def test_split_text_with_overlap(self):
        """Test text splitting with overlap."""
        component = SplitTextComponent()
        test_text = "First chunk.\nSecond chunk.\nThird chunk."
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text)],
                "chunk_overlap": 5,  # Small overlap to test functionality
                "chunk_size": 20,
                "separator": "\n",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert len(results) > 1, f"Expected more than 1 chunk, got {len(results)}"
        # Check that chunks contain the expected text
        assert "First chunk" in results[0].text, f"Expected 'First chunk' in '{results[0].text}'"
        assert "Second chunk" in results[1].text, f"Expected 'Second chunk' in '{results[1].text}'"
        assert "Third chunk" in results[2].text, f"Expected 'Third chunk' in '{results[2].text}'"

    def test_split_text_custom_separator(self):
        """Test text splitting with a custom separator."""
        component = SplitTextComponent()
        test_text = "First part|Second part|Third part"
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text)],
                "chunk_overlap": 0,
                "chunk_size": 10,
                "separator": "|",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert len(results) == 3, f"Expected 3 chunks, got {len(results)}"
        assert "First part" in results[0].text, f"Expected 'First part', got '{results[0].text}'"
        assert "Second part" in results[1].text, f"Expected 'Second part', got '{results[1].text}'"
        assert "Third part" in results[2].text, f"Expected 'Third part', got '{results[2].text}'"

    def test_split_text_with_metadata(self):
        """Test text splitting while preserving metadata."""
        component = SplitTextComponent()
        test_metadata = {"source": "test.txt", "author": "test"}
        test_text = "Chunk 1\nChunk 2"
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text, data=test_metadata)],
                "chunk_overlap": 0,
                "chunk_size": 7,
                "separator": "\n",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert len(results) == 2, f"Expected 2 chunks, got {len(results)}"
        for result in results:
            assert result.data["source"] == test_metadata["source"], (
                f"Expected source '{test_metadata['source']}', got '{result.data.get('source')}'"
            )
            assert result.data["author"] == test_metadata["author"], (
                f"Expected author '{test_metadata['author']}', got '{result.data.get('author')}'"
            )

    def test_split_text_as_dataframe(self):
        """Test converting split text results to DataFrame."""
        component = SplitTextComponent()
        test_text = "First chunk\nSecond chunk\nThird chunk"
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text)],
                "chunk_overlap": 0,
                "chunk_size": 11,
                "separator": "\n",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        data_frame = component.as_dataframe()
        assert isinstance(data_frame, DataFrame), "Expected DataFrame instance"
        assert len(data_frame) == 3, f"Expected DataFrame with 3 rows, got {len(data_frame)}"
        assert list(data_frame.columns) == ["text"], f"Expected columns ['text'], got {list(data_frame.columns)}"
        assert "First chunk" in data_frame.iloc[0]["text"], (
            f"Expected 'First chunk', got '{data_frame.iloc[0]['text']}'"
        )
        assert "Second chunk" in data_frame.iloc[1]["text"], (
            f"Expected 'Second chunk', got '{data_frame.iloc[1]['text']}'"
        )
        assert "Third chunk" in data_frame.iloc[2]["text"], (
            f"Expected 'Third chunk', got '{data_frame.iloc[2]['text']}'"
        )

    def test_split_text_empty_input(self):
        """Test handling of empty input text."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": [Data(text="")],
                "chunk_overlap": 0,
                "chunk_size": 10,
                "separator": "\n",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert len(results) == 0, f"Expected 0 chunks for empty input, got {len(results)}"

    def test_split_text_single_chunk(self):
        """Test text that fits in a single chunk."""
        component = SplitTextComponent()
        test_text = "Small text"
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text)],
                "chunk_overlap": 0,
                "chunk_size": 100,
                "separator": "\n",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert len(results) == 1, f"Expected 1 chunk, got {len(results)}"
        assert results[0].text == test_text, f"Expected '{test_text}', got '{results[0].text}'"

    def test_split_text_multiple_inputs(self):
        """Test splitting multiple input texts."""
        component = SplitTextComponent()
        test_texts = ["First text\nSecond line", "Another text\nAnother line"]
        component.set_attributes(
            {
                "data_inputs": [Data(text=text) for text in test_texts],
                "chunk_overlap": 0,
                "chunk_size": 10,
                "separator": "\n",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert len(results) == 4, f"Expected 4 chunks (2 from each text), got {len(results)}"
        assert "First text" in results[0].text, f"Expected 'First text', got '{results[0].text}'"
        assert "Second line" in results[1].text, f"Expected 'Second line', got '{results[1].text}'"
        assert "Another text" in results[2].text, f"Expected 'Another text', got '{results[2].text}'"
        assert "Another line" in results[3].text, f"Expected 'Another line', got '{results[3].text}'"

    def test_split_text_with_dataframe_input(self):
        """Test splitting text with DataFrame input."""
        component = SplitTextComponent()
        test_texts = ["First text\nSecond line", "Another text\nAnother line"]
        data_frame = DataFrame([Data(text=text) for text in test_texts])
        component.set_attributes(
            {
                "data_inputs": data_frame,
                "chunk_overlap": 0,
                "chunk_size": 10,
                "separator": "\n",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert len(results) == 4, f"Expected 4 chunks (2 from each text), got {len(results)}"
        assert "First text" in results[0].text, f"Expected 'First text', got '{results[0].text}'"
        assert "Second line" in results[1].text, f"Expected 'Second line', got '{results[1].text}'"
        assert "Another text" in results[2].text, f"Expected 'Another text', got '{results[2].text}'"
        assert "Another line" in results[3].text, f"Expected 'Another line', got '{results[3].text}'"

    def test_with_url_loader(self):
        """Test splitting text with URL loader."""
        component = SplitTextComponent()
        url = ["https://en.wikipedia.org/wiki/London", "https://en.wikipedia.org/wiki/Paris"]
        data_frame = URLComponent(urls=url, format="Text").fetch_content()
        assert isinstance(data_frame, DataFrame), "Expected DataFrame instance"
        assert len(data_frame) == 2, f"Expected DataFrame with 2 rows, got {len(data_frame)}"
        component.set_attributes(
            {
                "data_inputs": data_frame,
                "chunk_overlap": 0,
                "chunk_size": 10,
                "separator": "\n",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, list), "Expected list instance"
        assert len(results) > 2, f"Expected DataFrame with more than 2 rows, got {len(results)}"
