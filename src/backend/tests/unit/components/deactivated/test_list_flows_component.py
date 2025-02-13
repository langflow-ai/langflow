import pytest

from langflow.components.deactivated import ListFlowsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestListFlowsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ListFlowsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "flows", "file_name": "ListFlows"},
        ]

    async def test_build_flows(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build()
        assert isinstance(result, list), "Expected result to be a list."
        assert all(isinstance(flow, Data) for flow in result), "All items in the result should be of type Data."

    async def test_component_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
