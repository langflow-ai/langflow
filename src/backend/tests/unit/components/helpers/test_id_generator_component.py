import pytest

from langflow.components.helpers import IDGeneratorComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestIDGeneratorComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return IDGeneratorComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"unique_id": None, "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_generate_id(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.generate_id()
        assert result is not None
        assert result.text is not None
        assert len(result.text) > 0  # Ensure that an ID is generated

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, None, "unique_id")
        assert "unique_id" in updated_config
        assert "value" in updated_config["unique_id"]
        assert len(updated_config["unique_id"]["value"]) > 0  # Ensure that a UUID is generated
