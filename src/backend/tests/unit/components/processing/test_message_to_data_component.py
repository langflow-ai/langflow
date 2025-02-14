import pytest
from langflow.components.processing import MessageToDataComponent
from langflow.schema import Data
from langflow.schema.message import Message

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMessageToDataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MessageToDataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"message": Message(data={"key": "value"})}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_convert_message_to_data_success(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = component.convert_message_to_data()

        # Assert
        assert isinstance(result, Data)
        assert result.data == {"key": "value"}

    def test_convert_message_to_data_failure(self, component_class):
        # Arrange
        component = component_class(message="Not a Message object")

        # Act
        result = component.convert_message_to_data()

        # Assert
        assert isinstance(result, Data)
        assert result.data == {"error": "Error converting Message to Data: Input must be a Message object"}
        assert component.status == "Error converting Message to Data: Input must be a Message object"
