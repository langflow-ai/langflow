import pytest
from langflow.components.logic import SubFlowComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSubFlowComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SubFlowComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"flow_name": "Test Flow", "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "subflow", "file_name": "SubFlow"},
            {"version": "1.1.0", "module": "subflow", "file_name": "subflow"},
        ]

    async def test_get_flow_names(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        flow_names = await component.get_flow_names()
        assert isinstance(flow_names, list)

    async def test_get_flow(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        flow = await component.get_flow("Test Flow")
        assert flow is not None
        assert flow.data["name"] == "Test Flow"

    async def test_update_build_config_with_flow_name(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = await component.update_build_config(build_config, "Test Flow", "flow_name")
        assert "flow_name" in updated_config
        assert updated_config["flow_name"]["options"]

    async def test_generate_results(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.generate_results()
        assert isinstance(result, list)

    async def test_add_inputs_to_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        inputs_vertex = []  # Mocked inputs for testing
        updated_config = component.add_inputs_to_build_config(inputs_vertex, build_config)
        assert updated_config == build_config  # Assuming no inputs added for empty vertex list
