import pytest
from langflow.components.retrievers import MultiQueryRetrieverComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMultiQueryRetrieverComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MultiQueryRetrieverComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"llm": "mock_llm", "retriever": "mock_retriever", "prompt": None, "parser_key": "lines"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "retrievers", "file_name": "MultiQueryRetriever"},
        ]

    def test_build_with_default_prompt(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.build(**default_kwargs)
        assert result is not None
        assert isinstance(result, MultiQueryRetriever)

    def test_build_with_custom_prompt(self, component_class, default_kwargs):
        default_kwargs["prompt"] = "What are the benefits of AI?"
        component = component_class(**default_kwargs)
        result = component.build(**default_kwargs)
        assert result is not None
        assert isinstance(result, MultiQueryRetriever)
        assert result.prompt.template == "What are the benefits of AI?"
