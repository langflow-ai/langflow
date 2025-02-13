import pytest

from langflow.components.langchain_utilities import SQLGeneratorComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSQLGeneratorComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SQLGeneratorComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Generate a list of users",
            "llm": "mock_llm",
            "db": "mock_db",
            "top_k": 5,
            "prompt": "What is the SQL for `{question}`?",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "sql_generator", "file_name": "SQLGenerator"},
        ]

    def test_invoke_chain_with_valid_prompt(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.invoke_chain()
        assert result is not None
        assert "SELECT" in result  # Assuming the SQL query starts with SELECT

    def test_invoke_chain_without_prompt(self, component_class, default_kwargs):
        default_kwargs["prompt"] = None
        component = component_class(**default_kwargs)
        result = component.invoke_chain()
        assert result is not None
        assert "SELECT" in result  # Assuming the SQL query starts with SELECT

    def test_invoke_chain_with_invalid_top_k(self, component_class, default_kwargs):
        default_kwargs["top_k"] = 0
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Top K must be greater than 0."):
            component.invoke_chain()

    def test_invoke_chain_with_invalid_prompt(self, component_class, default_kwargs):
        default_kwargs["prompt"] = "Invalid prompt without question"
        component = component_class(**default_kwargs)
        with pytest.raises(
            ValueError, match="Prompt must contain `{question}` to be used with Natural Language to SQL."
        ):
            component.invoke_chain()
