import pytest

from langflow.components.logic import RunFlowComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestRunFlowComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return RunFlowComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"flow_name_selected": "example_flow", "flow_tweak_data": {}, "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "run_flow", "file_name": "RunFlow"},
            {"version": "1.1.0", "module": "run_flow", "file_name": "run_flow"},
        ]

    async def test_update_build_config_with_valid_flow(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"flow_name_selected": {"options": []}}
        updated_config = await component.update_build_config(build_config, "example_flow", "flow_name_selected")
        assert "options" in updated_config["flow_name_selected"]
        assert isinstance(updated_config["flow_name_selected"]["options"], list)

    async def test_update_build_config_with_missing_keys(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        with pytest.raises(ValueError, match="Missing required keys in build_config"):
            await component.update_build_config(build_config, "example_flow", "flow_name_selected")

    async def test_run_flow_with_tweaks(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component._attributes["flow_tweak_data"] = {"node1~param1": "value1"}
        result = await component.run_flow_with_tweaks()
        assert result is not None  # Assuming run_flow returns a non-null result

    async def test_run_flow_with_empty_tweaks(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component._attributes["flow_tweak_data"] = {}
        result = await component.run_flow_with_tweaks()
        assert result is not None  # Assuming run_flow returns a non-null result
