import pandas as pd
import pytest
from langchain_core.documents import Document
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame({"name": ["John", "Jane"], "text": ["name is John", "name is Jane"]})


@pytest.fixture
def dataframe_with_metadata():
    """Create a DataFrame instance with metadata for testing."""
    data_df = pd.DataFrame({"name": ["John", "Jane"], "text": ["name is John", "name is Jane"]})
    return DataFrame(data_df)


class TestDataFrameSchema:
    @pytest.mark.parametrize(
        "operation",
        [
            pytest.param(lambda frame: frame.copy(), id="copy"),
            pytest.param(lambda frame: frame.head(1), id="head"),
            pytest.param(lambda frame: frame[["body"]], id="select-columns"),
            pytest.param(lambda frame: frame.sort_values("rank"), id="sort"),
            pytest.param(lambda frame: frame.add_row({"body": "Third", "rank": 3}), id="add-row"),
            pytest.param(lambda frame: frame.add_rows([{"body": "Third", "rank": 3}]), id="add-rows"),
        ],
    )
    def test_operations_preserve_document_text_configuration(self, operation):
        """Derived tables retain the configured document body and independent fallback."""
        frame = DataFrame(
            {"body": ["First", "Second"], "rank": [2, 1]}, text_key="body", default_value="Missing content"
        )

        result = operation(frame)

        assert result.text_key == "body"
        assert result.default_value == "Missing content"
        documents = result.to_lc_documents()
        assert [document.page_content for document in documents] == result["body"].tolist()
        assert all("body" not in document.metadata for document in documents)
        result.default_value = "Changed fallback"
        assert frame.default_value == "Missing content"

    def test_copy_preserves_document_fallback(self):
        """A missing text column uses the fallback inherited from the source table."""
        frame = DataFrame({"rank": [1]}, text_key="body", default_value="Missing content")

        documents = frame.copy().to_lc_documents()

        assert documents == [Document(page_content="Missing content", metadata={"rank": 1})]

    def test_empty_copy_preserves_text_configuration(self):
        """Copying an empty table preserves its future document conversion settings."""
        frame = DataFrame(text_key="body", default_value="Missing content")

        result = frame.copy()

        assert result.empty
        assert result.text_key == "body"
        assert result.default_value == "Missing content"

    def test_to_data_list(self, sample_dataframe):
        """Test conversion of DataFrame to list of Data objects."""
        data_frame = DataFrame(sample_dataframe)
        data_list = data_frame.to_data_list()
        assert isinstance(data_list, list)
        assert all(isinstance(item, Data) for item in data_list)
        assert len(data_list) == len(sample_dataframe)
        assert data_list[0].data["name"] == "John"
        assert data_list[0].data["text"] == "name is John"

    def test_add_row(self, sample_dataframe):
        """Test adding a single row to DataFrame."""
        data_frame = DataFrame(sample_dataframe)
        # Test adding dict
        new_df = data_frame.add_row({"name": "Bob", "text": "name is Bob"})
        assert len(new_df) == len(sample_dataframe) + 1
        assert new_df.iloc[-1]["name"] == "Bob"
        assert new_df.iloc[-1]["text"] == "name is Bob"

        # Test adding Data object
        data_obj = Data(data={"name": "Alice", "text": "name is Alice"})
        new_df = data_frame.add_row(data_obj)
        assert len(new_df) == len(sample_dataframe) + 1
        assert new_df.iloc[-1]["name"] == "Alice"
        assert new_df.iloc[-1]["text"] == "name is Alice"

    def test_add_rows(self, sample_dataframe):
        """Test adding multiple rows to DataFrame."""
        data_frame = DataFrame(sample_dataframe)
        new_rows = [{"name": "Bob", "text": "name is Bob"}, Data(data={"name": "Alice", "text": "name is Alice"})]
        new_df = data_frame.add_rows(new_rows)
        assert len(new_df) == len(sample_dataframe) + 2
        assert new_df.iloc[-2:]["name"].tolist() == ["Bob", "Alice"]
        assert new_df.iloc[-2:]["text"].tolist() == ["name is Bob", "name is Alice"]

    def test_to_lc_document(self, dataframe_with_metadata):
        documents = dataframe_with_metadata.to_lc_documents()
        assert isinstance(documents, list)
        assert all(isinstance(doc, Document) for doc in documents)
        expected_documents_len = 2
        assert len(documents) == expected_documents_len
        assert documents[0].page_content == "name is John"
        assert documents[0].metadata == {"name": "John"}
        assert documents[1].page_content == "name is Jane"

    def test_bool_operator(self):
        """Test boolean operator behavior."""
        empty_df = DataFrame()
        assert not bool(empty_df)

        non_empty_df = DataFrame({"name": ["John"], "text": ["name is John"]})
        assert bool(non_empty_df)
