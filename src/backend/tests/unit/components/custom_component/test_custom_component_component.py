import pytest
from langflow.components.custom_component import CustomComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCustomComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CustomComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"input_value": "Hello, World!", "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_output(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.build_output()
        assert result is not None
        assert result.value == "Hello, World!"

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
