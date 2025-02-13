import pytest
from langflow.components.deactivated import SubFlowComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSubFlowComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SubFlowComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"flow_name": "TestFlow", "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "subflow", "file_name": "SubFlow"},
        ]

    async def test_get_flow_names(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        flow_names = await component.get_flow_names()
        assert isinstance(flow_names, list)

    async def test_get_flow(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        flow = await component.get_flow("TestFlow")
        assert flow is not None
        assert flow.data["name"] == "TestFlow"

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = await component.update_build_config(build_config, "TestFlow", "flow_name")
        assert "flow_name" in updated_config
        assert "options" in updated_config["flow_name"]

    async def test_build(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build("TestFlow", input_value="Sample Input")
        assert isinstance(result, list)
        assert all("result" in item for item in result)

    def test_build_config_structure(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        config = component.build_config()
        assert "input_value" in config
        assert "flow_name" in config
        assert "tweaks" in config
        assert "get_final_results_only" in config
