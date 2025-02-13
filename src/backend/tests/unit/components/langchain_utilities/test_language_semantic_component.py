import pytest
from langflow.components.langchain_utilities import SemanticTextSplitterComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSemanticTextSplitterComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SemanticTextSplitterComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "data_inputs": [{"text": "Hello world.", "metadata": {}}],
            "embeddings": "mock_embeddings",
            "breakpoint_threshold_type": "percentile",
            "breakpoint_threshold_amount": 0.5,
            "number_of_chunks": 5,
            "sentence_split_regex": "",
            "buffer_size": 0,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_split_text_with_valid_inputs(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.split_text()
        assert result is not None
        assert isinstance(result, list)

    def test_split_text_without_embeddings(self, component_class, default_kwargs):
        default_kwargs["embeddings"] = None
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="An embeddings model is required for SemanticTextSplitter."):
            component.split_text()

    def test_split_text_without_data_inputs(self, component_class, default_kwargs):
        default_kwargs["data_inputs"] = []
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Data inputs cannot be empty."):
            component.split_text()

    def test_split_text_with_invalid_data_input_type(self, component_class, default_kwargs):
        default_kwargs["data_inputs"] = ["invalid_data"]
        component = component_class(**default_kwargs)
        with pytest.raises(TypeError, match="Invalid data input type: invalid_data"):
            component.split_text()
