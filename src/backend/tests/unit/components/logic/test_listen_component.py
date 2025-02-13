import pytest

from langflow.components.logic import ListenComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestListenComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ListenComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"name": "Test Notification", "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_config(self, component_class):
        component = component_class()
        config = component.build_config()
        assert "name" in config
        assert config["name"]["display_name"] == "Name"
        assert config["name"]["info"] == "The name of the notification to listen for."

    async def test_build_method(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build(name=default_kwargs["name"])
        assert result is not None
        assert component.status == result

    def test_set_successors_ids(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component._set_successors_ids()
        assert component._vertex.is_state is True
        assert isinstance(component._vertex.graph.successor_map.get(component._vertex.id, []), list)
