import pytest

from langflow.components.astra_assistants import Dotenv
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestDotenvComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return Dotenv

    @pytest.fixture
    def default_kwargs(self):
        return {"dotenv_file_content": "VAR1=value1\nVAR2=value2"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_process_inputs_with_variables(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.process_inputs()
        assert result is not None
        assert result.text == "Loaded .env"

    def test_process_inputs_without_variables(self, component_class):
        component = component_class(dotenv_file_content="")
        result = component.process_inputs()
        assert result is not None
        assert result.text == "No variables found in .env"
