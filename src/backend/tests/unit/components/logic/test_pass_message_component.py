import pytest
from langflow.components.logic import PassMessageComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestPassMessageComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return PassMessageComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"input_message": "Hello, World!", "ignored_message": "This will be ignored."}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_pass_message_functionality(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.pass_message()
        assert result == default_kwargs["input_message"], "The output message should match the input message."

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result == default_kwargs["input_message"], (
            "Component should return the input message for the latest version."
        )
