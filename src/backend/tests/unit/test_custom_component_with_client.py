from pathlib import Path

import pytest
from langflow.custom import Component
from langflow.custom.custom_component.custom_component import CustomComponent
from langflow.custom.utils import build_custom_component_template
from langflow.field_typing.constants import Data
from langflow.services.settings.feature_flags import FEATURE_FLAGS


@pytest.fixture
def code_component_with_multiple_outputs():
    code = Path("src/backend/tests/data/component_multiple_outputs.py").read_text(encoding="utf-8")
    return Component(_code=code)


@pytest.fixture
def component(client, active_user):
    return CustomComponent(
        user_id=active_user.id,
        field_config={
            "fields": {
                "llm": {"type": "str"},
                "url": {"type": "str"},
                "year": {"type": "int"},
            }
        },
    )


def test_list_flows_flow_objects(component):
    flows = component.list_flows()
    are_flows = [isinstance(flow, Data) for flow in flows]
    flow_types = [type(flow) for flow in flows]
    assert all(are_flows), f"Expected all flows to be Data objects, got {flow_types}"


def test_list_flows_return_type(component):
    flows = component.list_flows()
    assert isinstance(flows, list)


def test_feature_flags_add_toolkit_output(active_user, code_component_with_multiple_outputs):
    frontnd_node_dict, _ = build_custom_component_template(code_component_with_multiple_outputs, active_user.id)
    len_outputs = len(frontnd_node_dict["outputs"])
    FEATURE_FLAGS.add_toolkit_output = True
    frontnd_node_dict, _ = build_custom_component_template(code_component_with_multiple_outputs, active_user.id)
    assert len(frontnd_node_dict["outputs"]) == len_outputs + 1
