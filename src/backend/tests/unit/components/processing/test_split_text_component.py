import pytest
from langflow.schema import Data, DataFrame

from lfx.components.data import URLComponent
from lfx.components.processing import SplitTextComponent
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
        test_text = "First chunk\nSecond chunk\nThird chunk"
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

        data_frame = component.split_text()
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

        data_frame = component.split_text()
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

    def test_split_text_custom_separator(self):
        """Test text splitting with a custom separator."""
        component = SplitTextComponent()
        test_text = "First chunk.|Second chunk.|Third chunk."
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

        data_frame = component.split_text()
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

    def test_split_text_with_metadata(self):
        """Test text splitting while preserving metadata."""
        component = SplitTextComponent()
        test_metadata = {"source": "test.txt", "author": "test"}
        test_text = "First chunk\nSecond chunk"
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

        data_frame = component.split_text()
        assert isinstance(data_frame, DataFrame), "Expected DataFrame instance"
        assert len(data_frame) == 2, f"Expected DataFrame with 2 rows, got {len(data_frame)}"
        assert "First chunk" in data_frame.iloc[0]["text"], (
            f"Expected 'First chunk', got '{data_frame.iloc[0]['text']}'"
        )
        assert "Second chunk" in data_frame.iloc[1]["text"], (
            f"Expected 'Second chunk', got '{data_frame.iloc[1]['text']}'"
        )
        # Loop over each row to check metadata
        for _, row in data_frame.iterrows():
            assert row["source"] == test_metadata["source"], (
                f"Expected source '{test_metadata['source']}', got '{row['source']}'"
            )
            assert row["author"] == test_metadata["author"], (
                f"Expected author '{test_metadata['author']}', got '{row['author']}'"
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
        assert results["text"][0] == test_text, f"Expected '{test_text}', got '{results['text'][0]}'"

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
        assert "First text" in results["text"][0], f"Expected 'First text', got '{results['text'][0]}'"
        assert "Second line" in results["text"][1], f"Expected 'Second line', got '{results['text'][1]}'"
        assert "Another text" in results["text"][2], f"Expected 'Another text', got '{results['text'][2]}'"
        assert "Another line" in results["text"][3], f"Expected 'Another line', got '{results['text'][3]}'"

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
        assert "First text" in results["text"][0], f"Expected 'First text', got '{results['text'][0]}'"
        assert "Second line" in results["text"][1], f"Expected 'Second line', got '{results['text'][1]}'"
        assert "Another text" in results["text"][2], f"Expected 'Another text', got '{results['text'][2]}'"
        assert "Another line" in results["text"][3], f"Expected 'Another line', got '{results['text'][3]}'"

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
        assert isinstance(results, DataFrame), "Expected DataFrame instance"
        assert len(results) > 2, f"Expected DataFrame with more than 2 rows, got {len(results)}"
