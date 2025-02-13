import pytest

from langflow.components.deactivated.store_message import StoreMessageComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestStoreMessageComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return StoreMessageComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"message": Message(text="Hello, World!")}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_build_stores_message(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build(default_kwargs["message"])

        assert result is not None
        assert result.text == "Hello, World!"
        assert component.status is not None

    async def test_build_with_flow_id(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.graph = Mock()
        component.graph.flow_id = "test_flow_id"

        result = await component.build(default_kwargs["message"])

        assert result is not None
        assert component.graph.flow_id == "test_flow_id"
