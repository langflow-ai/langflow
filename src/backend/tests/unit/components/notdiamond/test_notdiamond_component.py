import pytest

from langflow.components.notdiamond.notdiamond import NotDiamondComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestNotDiamondComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NotDiamondComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Hello, world!",
            "system_message": "This is a system message.",
            "models": ["gpt-4o", "gpt-4-turbo"],
            "api_key": "TEST_API_KEY",
            "tradeoff": "quality",
            "hash_content": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "not_diamond", "file_name": "NotDiamond"},
        ]

    async def test_model_select(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.model_select()
        assert result is not None
        assert isinstance(result, Message)

    async def test_get_selected_model(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        await component.model_select()
        selected_model = component.get_selected_model()
        assert selected_model is not None
        assert selected_model in default_kwargs["models"]

    async def test_format_input(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        formatted_input = component._format_input(default_kwargs["input_value"], default_kwargs["system_message"])
        assert isinstance(formatted_input, list)
        assert len(formatted_input) > 0
        assert all(isinstance(msg, dict) for msg in formatted_input)

    async def test_empty_input_value(self, component_class):
        component = await self.component_setup(component_class, {"input_value": "", "system_message": None})
        with pytest.raises(ValueError, match="The message you want to send to the router is empty."):
            await component.model_select()
