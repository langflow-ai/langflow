import pytest

from langflow.components.astra_assistants import AssistantsListAssistants
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAssistantsListAssistants(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AssistantsListAssistants

    @pytest.fixture
    def default_kwargs(self):
        return {}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "assistants", "file_name": "AssistantsListAssistants"},
        ]

    def test_process_inputs(self, component_class):
        # Arrange
        component = component_class()
        component.client.beta.assistants.list = lambda: Mock(data=[Mock(id="assistant_1"), Mock(id="assistant_2")])

        # Act
        result = component.process_inputs()

        # Assert
        assert result is not None
        assert result.text == "assistant_1\nassistant_2"
