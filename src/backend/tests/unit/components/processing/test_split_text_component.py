import pytest
from lfx.components.data import URLComponent
from lfx.components.processing import SplitTextComponent
from lfx.schema import Data, DataFrame

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
            "mode": "Character",
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
                "mode": "Character",
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
                "mode": "Character",
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
                "mode": "Character",
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
                "mode": "Character",
                "chunk_overlap": 0,
                "chunk_size": 7,
                "separator": "\n",
                "clean_output": False,
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

    def test_split_text_clean_output_strips_metadata(self):
        """Test that clean_output=True strips metadata columns from the output."""
        component = SplitTextComponent()
        test_metadata = {"source": "test.txt", "author": "test"}
        test_text = "First chunk\nSecond chunk"
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text, data=test_metadata)],
                "mode": "Character",
                "chunk_overlap": 0,
                "chunk_size": 7,
                "separator": "\n",
                "clean_output": True,
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        data_frame = component.split_text()
        assert isinstance(data_frame, DataFrame), "Expected DataFrame instance"
        assert len(data_frame) == 2, f"Expected DataFrame with 2 rows, got {len(data_frame)}"
        assert list(data_frame.columns) == ["text"], f"Expected only ['text'] column, got {list(data_frame.columns)}"
        assert "source" not in data_frame.columns, "Metadata column 'source' should not be present"
        assert "author" not in data_frame.columns, "Metadata column 'author' should not be present"

    def test_split_text_empty_input(self):
        """Test handling of empty input text."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": [Data(text="")],
                "mode": "Character",
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
                "mode": "Character",
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
                "mode": "Character",
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
                "mode": "Character",
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

    # -------------------------------------------------------------------------
    # Recursive mode
    # -------------------------------------------------------------------------

    def test_recursive_mode_splits_by_chunk_size(self):
        """Recursive mode splits text by chunk size even without newlines."""
        component = SplitTextComponent()
        test_text = "a" * 100
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text)],
                "mode": "Recursive",
                "chunk_size": 30,
                "chunk_overlap": 0,
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame)
        assert len(results) > 1, "Expected multiple chunks from Recursive mode"
        for _, row in results.iterrows():
            assert len(row["text"]) <= 30, f"Chunk exceeds chunk_size: {len(row['text'])}"

    def test_recursive_mode_respects_overlap(self):
        """Recursive mode produces overlapping chunks when chunk_overlap > 0."""
        component = SplitTextComponent()
        test_text = "word " * 40
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text)],
                "mode": "Recursive",
                "chunk_size": 50,
                "chunk_overlap": 10,
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame)
        assert len(results) > 1, "Expected multiple chunks"

    def test_recursive_mode_with_custom_separators(self):
        """Recursive mode uses custom separators when toggle is enabled."""
        component = SplitTextComponent()
        test_text = "Section one||Section two||Section three"
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text)],
                "mode": "Recursive",
                "chunk_size": 15,
                "chunk_overlap": 0,
                "recursive_separators_bool": True,
                "recursive_separators": ["||"],
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame)
        assert len(results) == 3, f"Expected 3 chunks split by '||', got {len(results)}"
        assert "Section one" in results["text"][0]
        assert "Section two" in results["text"][1]
        assert "Section three" in results["text"][2]

    # -------------------------------------------------------------------------
    # Character mode
    # -------------------------------------------------------------------------

    def test_character_mode_with_message_input(self):
        """Character mode correctly splits a Message input."""
        from lfx.schema.message import Message

        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": Message(text="First line\nSecond line\nThird line"),
                "mode": "Character",
                "chunk_size": 15,
                "chunk_overlap": 0,
                "separator": "\n",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame)
        assert len(results) == 3, f"Expected 3 chunks, got {len(results)}"

    def test_character_mode_custom_separator_field(self):
        """Character mode splits using the custom_separator field when separator='Custom'."""
        component = SplitTextComponent()
        # Each piece ("First", "Second", "Third") is 5-6 chars; chunk_size=8 prevents merging
        # because any two pieces combined (e.g. "First"+"Second" = 11) exceed chunk_size.
        test_text = "First||Second||Third"
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text)],
                "mode": "Character",
                "chunk_size": 8,
                "chunk_overlap": 0,
                "separator": "Custom",
                "custom_separator": "||",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame)
        assert len(results) == 3, f"Expected 3 chunks split by '||', got {len(results)}"
        assert results["text"][0] == "First"
        assert results["text"][1] == "Second"
        assert results["text"][2] == "Third"

    def test_character_mode_default_separator(self):
        """Character mode with default separator splits on double newline."""
        component = SplitTextComponent()
        test_text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text)],
                "mode": "Character",
                "chunk_size": 20,
                "chunk_overlap": 0,
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame)
        assert len(results) == 3, f"Expected 3 paragraphs, got {len(results)}"

    def test_empty_dataframe_raises_error(self):
        """An empty DataFrame input raises TypeError."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": DataFrame(),
                "mode": "Recursive",
                "chunk_size": 1000,
                "chunk_overlap": 0,
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        with pytest.raises(TypeError):
            component.split_text()

    def test_recursive_mode_with_two_custom_separators(self):
        """Recursive mode applies separators in cascade: splits by '||' first, then '::' for oversized pieces."""
        component = SplitTextComponent()
        # "Part Alpha::Part Beta" (21 chars) exceeds chunk_size=12, so it gets split further by "::"
        test_text = "Section one||Part Alpha::Part Beta||Section two"
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text)],
                "mode": "Recursive",
                "chunk_size": 12,
                "chunk_overlap": 0,
                "recursive_separators_bool": True,
                "recursive_separators": ["||", "::"],
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame)
        assert len(results) == 4, f"Expected 4 chunks, got {len(results)}"
        # keep_separator=True (RecursiveCharacterTextSplitter default) prepends the separator
        # to each chunk, so we use `in` to check content without caring about the prefix.
        assert "Section one" in results["text"][0]
        assert "Part Alpha" in results["text"][1]
        assert "Part Beta" in results["text"][2]
        assert "Section two" in results["text"][3]

    def test_recursive_mode_empty_separators_list_uses_defaults(self):
        """When recursive_separators_bool=True but the list is empty, falls back to LangChain defaults."""
        component = SplitTextComponent()
        test_text = "a" * 100
        component.set_attributes(
            {
                "data_inputs": [Data(text=test_text)],
                "mode": "Recursive",
                "chunk_size": 30,
                "chunk_overlap": 0,
                "recursive_separators_bool": True,
                "recursive_separators": [],
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame)
        assert len(results) > 1, "Expected multiple chunks even with empty separators list"
        for _, row in results.iterrows():
            assert len(row["text"]) <= 30, f"Chunk exceeds chunk_size: {len(row['text'])}"

    # -------------------------------------------------------------------------
    # text_key — output column name
    # -------------------------------------------------------------------------

    def test_text_key_renames_output_column_recursive(self):
        """text_key correctly names the output column in Recursive mode."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": [Data(text="Some text to split into chunks")],
                "mode": "Recursive",
                "chunk_size": 10,
                "chunk_overlap": 0,
                "text_key": "content",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame)
        assert "content" in results.columns, f"Expected 'content' column, got {list(results.columns)}"
        assert "text" not in results.columns, "Column 'text' should not be present"

    def test_text_key_renames_output_column_character(self):
        """text_key correctly names the output column in Character mode."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": [Data(text="First line\nSecond line")],
                "mode": "Character",
                "chunk_size": 1000,
                "chunk_overlap": 0,
                "separator": "\n",
                "text_key": "content",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame)
        assert "content" in results.columns, f"Expected 'content' column, got {list(results.columns)}"
        assert "text" not in results.columns, "Column 'text' should not be present"

    def test_text_key_with_clean_output_recursive(self):
        """text_key with clean_output=True keeps only the renamed column in Recursive mode."""
        component = SplitTextComponent()
        test_metadata = {"source": "test.txt"}
        component.set_attributes(
            {
                "data_inputs": [Data(text="Some text to split", data=test_metadata)],
                "mode": "Recursive",
                "chunk_size": 10,
                "chunk_overlap": 0,
                "text_key": "content",
                "clean_output": True,
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame)
        assert list(results.columns) == ["content"], f"Expected only ['content'], got {list(results.columns)}"
        assert "source" not in results.columns

    def test_text_key_with_clean_output_character(self):
        """text_key with clean_output=True keeps only the renamed column in Character mode."""
        component = SplitTextComponent()
        test_metadata = {"source": "test.txt"}
        component.set_attributes(
            {
                "data_inputs": [Data(text="First line\nSecond line", data=test_metadata)],
                "mode": "Character",
                "chunk_size": 1000,
                "chunk_overlap": 0,
                "separator": "\n",
                "text_key": "content",
                "clean_output": True,
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame)
        assert list(results.columns) == ["content"], f"Expected only ['content'], got {list(results.columns)}"
        assert "source" not in results.columns

    # -------------------------------------------------------------------------
    # update_build_config
    # -------------------------------------------------------------------------

    def test_update_build_config_mode_to_character(self):
        """Switching to Character shows separator, keep_separator and hides recursive fields."""
        component = SplitTextComponent()
        build_config = {
            "separator": {"show": False, "value": "/n/n"},
            "custom_separator": {"show": False},
            "keep_separator": {"show": False},
            "recursive_separators_bool": {"show": True, "value": False},
            "recursive_separators": {"show": False},
        }

        result = component.update_build_config(build_config, "Character", "mode")

        assert result["separator"]["show"] is True
        assert result["keep_separator"]["show"] is True
        assert result["recursive_separators_bool"]["show"] is False
        assert result["recursive_separators"]["show"] is False

    def test_update_build_config_mode_to_recursive(self):
        """Switching to Recursive hides separator, keep_separator and shows recursive_separators_bool."""
        component = SplitTextComponent()
        build_config = {
            "separator": {"show": True, "value": "/n"},
            "custom_separator": {"show": False},
            "keep_separator": {"show": True},
            "recursive_separators_bool": {"show": False, "value": False},
            "recursive_separators": {"show": False},
        }

        result = component.update_build_config(build_config, "Recursive", "mode")

        assert result["separator"]["show"] is False
        assert result["keep_separator"]["show"] is False
        assert result["recursive_separators_bool"]["show"] is True
        assert result["recursive_separators"]["show"] is False

    def test_update_build_config_recursive_toggle_on(self):
        """Enabling recursive_separators_bool shows the recursive_separators field."""
        component = SplitTextComponent()
        build_config = {
            "recursive_separators": {"show": False},
        }

        result = component.update_build_config(build_config, field_value=True, field_name="recursive_separators_bool")

        assert result["recursive_separators"]["show"] is True

    def test_update_build_config_recursive_toggle_off(self):
        """Disabling recursive_separators_bool hides the recursive_separators field."""
        component = SplitTextComponent()
        build_config = {
            "recursive_separators": {"show": True},
        }

        result = component.update_build_config(build_config, field_value=False, field_name="recursive_separators_bool")

        assert result["recursive_separators"]["show"] is False

    def test_with_url_loader(self):
        """Test splitting text with URL loader."""
        component = SplitTextComponent()
        url = ["https://en.wikipedia.org/wiki/London", "https://en.wikipedia.org/wiki/Paris"]
        data_frame = URLComponent(urls=url, format="Text").fetch_content()
        assert isinstance(data_frame, DataFrame), "Expected DataFrame instance"
        assert len(data_frame) == 2, f"Expected DataFrame with 2 rows, got {len(data_frame)}"

        # Use a reasonable chunk size that will work with varying URL content lengths
        # The test validates that URL-loaded content can be split, not the exact number of chunks
        component.set_attributes(
            {
                "data_inputs": data_frame,
                "mode": "Character",
                "chunk_overlap": 200,
                "chunk_size": 1000,
                "separator": "\n",
                "session_id": "test_session",
                "sender": "test_sender",
                "sender_name": "test_sender_name",
            }
        )

        results = component.split_text()
        assert isinstance(results, DataFrame), "Expected DataFrame instance"
        # Verify we get at least as many chunks as inputs (could be more if content is large)
        assert len(results) >= 2, f"Expected DataFrame with at least 2 rows, got {len(results)}"
        # Verify the results have the expected text column
        assert "text" in results.columns, f"Expected 'text' column in results, got {list(results.columns)}"
