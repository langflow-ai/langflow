import pytest
from langflow.components.needle import NeedleComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestNeedleComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NeedleComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "needle_api_key": "test_needle_api_key",
            "openai_api_key": "test_openai_api_key",
            "collection_id": "test_collection_id",
            "query": "What is the capital of France?",
            "output_type": "answer",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "needle", "file_name": "Needle"},
            {"version": "1.1.0", "module": "needle", "file_name": "needle"},
        ]

    def test_run_with_valid_inputs(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run()
        assert result is not None
        assert isinstance(result, Message)
        assert "answer" in result.text

    def test_run_with_empty_needle_api_key(self, component_class):
        component = component_class(
            needle_api_key="",
            openai_api_key="test_openai_api_key",
            collection_id="test_collection_id",
            query="What is the capital of France?",
            output_type="answer",
        )
        with pytest.raises(ValueError, match="The Needle API key cannot be empty."):
            component.run()

    def test_run_with_empty_openai_api_key(self, component_class):
        component = component_class(
            needle_api_key="test_needle_api_key",
            openai_api_key="",
            collection_id="test_collection_id",
            query="What is the capital of France?",
            output_type="answer",
        )
        with pytest.raises(ValueError, match="The OpenAI API key cannot be empty."):
            component.run()

    def test_run_with_empty_collection_id(self, component_class):
        component = component_class(
            needle_api_key="test_needle_api_key",
            openai_api_key="test_openai_api_key",
            collection_id="",
            query="What is the capital of France?",
            output_type="answer",
        )
        with pytest.raises(ValueError, match="The Collection ID cannot be empty."):
            component.run()

    def test_run_with_empty_query(self, component_class):
        component = component_class(
            needle_api_key="test_needle_api_key",
            openai_api_key="test_openai_api_key",
            collection_id="test_collection_id",
            query="",
            output_type="answer",
        )
        with pytest.raises(ValueError, match="The query cannot be empty."):
            component.run()
