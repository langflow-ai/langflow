import pytest
from lfx.components.data import URLComponent
from lfx.components.processing import SplitTextComponent
from lfx.schema import Data, DataFrame
from lfx.schema.message import Message

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

    @pytest.mark.parametrize(
        ("keep_separator", "expected"),
        [
            ("False", ["aaa", "bbb", "ccc", "ddd"]),
            ("True", ["aaa", ".bbb", ".ccc", ".ddd"]),
            ("Start", ["aaa", ".bbb", ".ccc", ".ddd"]),
            ("End", ["aaa.", "bbb.", "ccc.", "ddd"]),
            ("end", ["aaa.", "bbb.", "ccc.", "ddd"]),
            (True, ["aaa", ".bbb", ".ccc", ".ddd"]),
            (False, ["aaa", "bbb", "ccc", "ddd"]),
            ("", ["aaa", "bbb", "ccc", "ddd"]),
            (None, ["aaa", "bbb", "ccc", "ddd"]),
        ],
    )
    def test_keep_separator(self, keep_separator, expected):
        component = self._keep_separator_component(keep_separator)

        result = component.split_text()

        assert result["text"].tolist() == expected

    @staticmethod
    def _keep_separator_component(keep_separator):
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": [Data(text="aaa.bbb.ccc.ddd")],
                "chunk_overlap": 0,
                "chunk_size": 4,
                "separator": ".",
                "keep_separator": keep_separator,
                "text_key": "text",
            }
        )
        return component

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

    @pytest.mark.parametrize("label", [0, ("source", "id"), None])
    def test_split_text_keeps_non_string_metadata_labels(self, label):
        """Test that non-string metadata column labels survive the default column ordering."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": DataFrame({"text": ["alpha\nbeta"], label: ["source-1"]}),
                "text_key": "text",
                "chunk_overlap": 0,
                "chunk_size": 6,
                "separator": "\n",
                "clean_output": False,
            }
        )

        data_frame = component.split_text()

        assert list(data_frame.columns) == ["text", label]
        assert data_frame.to_numpy().tolist() == [["alpha", "source-1"], ["beta", "source-1"]]

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

    @pytest.mark.parametrize("clean_output", [False, True])
    def test_split_text_list_uses_configured_text_key(self, clean_output):
        """Test that Text Key selects the text field of every record in a list, without changing the records."""
        records = [
            Data(data={"body": "Alpha\nBeta", "source": "memo"}),
            Data(data={"body": "Gamma", "source": "note"}),
        ]
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": records,
                "text_key": "body",
                "chunk_overlap": 0,
                "chunk_size": 5,
                "separator": "\n",
                "clean_output": clean_output,
            }
        )

        results = component.split_text()

        assert results["text"].tolist() == ["Alpha", "Beta", "Gamma"]
        if clean_output:
            assert list(results.columns) == ["text"]
        else:
            assert results["source"].tolist() == ["memo", "memo", "note"]
        assert [(record.text_key, record.data) for record in records] == [
            ("text", {"body": "Alpha\nBeta", "source": "memo"}),
            ("text", {"body": "Gamma", "source": "note"}),
        ]

    def test_split_text_list_skips_records_without_text_key(self):
        """Test that a record lacking the configured Text Key contributes no chunk."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": [Data(data={"body": "Alpha"}), Data(data={"text": "Gamma"})],
                "text_key": "body",
                "chunk_overlap": 0,
                "chunk_size": 5,
                "separator": "\n",
            }
        )

        results = component.split_text()

        assert results["text"].tolist() == ["Alpha"]

    @pytest.mark.parametrize("text_key", ["text", "body"])
    @pytest.mark.parametrize("as_list", [False, True])
    def test_split_text_message_ignores_text_key(self, text_key, as_list):
        """Test that Message input splits its own text whatever Text Key is set to."""
        message = Message(text="Alpha\nBeta")
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": [message] if as_list else message,
                "text_key": text_key,
                "chunk_overlap": 0,
                "chunk_size": 5,
                "separator": "\n",
            }
        )

        results = component.split_text()

        assert results["text"].tolist() == ["Alpha", "Beta"]

    @pytest.mark.parametrize("clean_output", [False, True])
    @pytest.mark.parametrize("input_shape", ["list", "single", "table"])
    def test_split_text_chunk_replaces_record_text_field(self, input_shape, clean_output):
        """Test that each chunk's text replaces a record's own "text" field when Text Key names another field."""
        record = {"body": "Alpha\nBeta", "text": "OLD", "source": "memo"}
        data_inputs = {
            "list": [Data(data=dict(record))],
            "single": Data(data=dict(record)),
            "table": DataFrame([record]),
        }[input_shape]
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": data_inputs,
                "text_key": "body",
                "chunk_overlap": 0,
                "chunk_size": 5,
                "separator": "\n",
                "clean_output": clean_output,
            }
        )

        results = component.split_text()

        assert results["text"].tolist() == ["Alpha", "Beta"]
        if not clean_output:
            assert results["source"].tolist() == ["memo", "memo"]

    def test_split_text_chunk_replaces_text_field_when_record_has_own_text_key(self):
        """Test that a record's leftover "text" field gives way to the chunk under the default Text Key."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": [
                    Data(text_key="content", data={"content": "Alpha\nBeta", "text": "OLD", "source": "memo"})
                ],
                "chunk_overlap": 0,
                "chunk_size": 5,
                "separator": "\n",
            }
        )

        results = component.split_text()

        assert results.to_dict("records") == [
            {"text": "Alpha", "source": "memo"},
            {"text": "Beta", "source": "memo"},
        ]

    def test_split_text_table_chunk_replaces_partial_text_column(self):
        """Test that a Table whose "text" column is only partly filled still returns every chunk, not NaN."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": DataFrame(
                    [{"body": "Alpha\nBeta", "source": "memo"}, {"body": "Gamma", "text": "OLD", "source": "note"}]
                ),
                "text_key": "body",
                "chunk_overlap": 0,
                "chunk_size": 5,
                "separator": "\n",
            }
        )

        results = component.split_text()

        assert results.to_dict("records") == [
            {"text": "Alpha", "source": "memo"},
            {"text": "Beta", "source": "memo"},
            {"text": "Gamma", "source": "note"},
        ]

    def test_split_text_list_keeps_record_text_key_with_default_text_key(self):
        """Test that records carrying their own text_key keep it when Text Key is left at its default."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": [Data(text_key="content", data={"content": "Alpha\nBeta", "source": "memo"})],
                "chunk_overlap": 0,
                "chunk_size": 5,
                "separator": "\n",
            }
        )

        results = component.split_text()

        assert results["text"].tolist() == ["Alpha", "Beta"]
        assert results["source"].tolist() == ["memo", "memo"]

    def test_split_text_list_keeps_record_text_key_when_text_key_is_empty(self):
        """Test that an empty Text Key leaves each record's own text_key in charge."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": [Data(data={"text": "Alpha\nBeta"})],
                "text_key": "",
                "chunk_overlap": 0,
                "chunk_size": 5,
                "separator": "\n",
            }
        )

        results = component.split_text()

        assert results["text"].tolist() == ["Alpha", "Beta"]

    def test_split_text_mixed_list_reads_message_text_and_record_text_key(self):
        """Test that a list mixing a Message and a record splits each by its own text field."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": [Message(text="Alpha\nBeta"), Data(data={"body": "Gamma", "source": "note"})],
                "text_key": "body",
                "chunk_overlap": 0,
                "chunk_size": 5,
                "separator": "\n",
            }
        )

        results = component.split_text()

        assert results["text"].tolist() == ["Alpha", "Beta", "Gamma"]
        assert results["source"].tolist()[2] == "note"

    def test_split_text_single_record_uses_configured_text_key(self):
        """Test that a single record is split on the configured Text Key."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": Data(data={"body": "Alpha\nBeta", "source": "memo"}),
                "text_key": "body",
                "chunk_overlap": 0,
                "chunk_size": 5,
                "separator": "\n",
            }
        )

        results = component.split_text()

        assert results["text"].tolist() == ["Alpha", "Beta"]
        assert results["source"].tolist() == ["memo", "memo"]

    def test_split_text_dataframe_uses_configured_text_key(self):
        """Test that a Table input is split on the configured Text Key column."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": DataFrame([{"body": "Alpha\nBeta", "source": "memo"}, {"body": "Gamma"}]),
                "text_key": "body",
                "chunk_overlap": 0,
                "chunk_size": 5,
                "separator": "\n",
            }
        )

        results = component.split_text()

        assert results["text"].tolist() == ["Alpha", "Beta", "Gamma"]

    @pytest.mark.parametrize(
        ("data_inputs", "error"),
        [
            ([], "No data inputs provided"),
            (["plain string", 42], "No valid Data inputs found"),
            (DataFrame([]), "DataFrame is empty"),
        ],
    )
    def test_split_text_raises_type_error_when_input_has_no_records(self, data_inputs, error):
        """Test that inputs without any record raise a TypeError naming the problem."""
        component = SplitTextComponent()
        component.set_attributes(
            {
                "data_inputs": data_inputs,
                "text_key": "body",
                "chunk_overlap": 0,
                "chunk_size": 5,
                "separator": "\n",
            }
        )

        with pytest.raises(TypeError, match=error):
            component.split_text()

    async def test_with_url_loader(self):
        """Test splitting text with URL loader."""
        component = SplitTextComponent()
        url = ["https://en.wikipedia.org/wiki/London", "https://en.wikipedia.org/wiki/Paris"]
        data_frame = await URLComponent(urls=url, format="Text").fetch_content()
        assert isinstance(data_frame, DataFrame), "Expected DataFrame instance"
        assert len(data_frame) == 2, f"Expected DataFrame with 2 rows, got {len(data_frame)}"

        # Use a reasonable chunk size that will work with varying URL content lengths
        # The test validates that URL-loaded content can be split, not the exact number of chunks
        component.set_attributes(
            {
                "data_inputs": data_frame,
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
