import pytest
from langflow.custom.custom_component.custom_component import CustomComponent
from lfx.field_typing.constants import Data


@pytest.fixture
def component(
    client,  # noqa: ARG001
    active_user,
):
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


async def test_list_flows_flow_objects(component):
    flows = await component.alist_flows()
    are_flows = [isinstance(flow, Data) for flow in flows]
    flow_types = [type(flow) for flow in flows]
    assert all(are_flows), f"Expected all flows to be Data objects, got {flow_types}"


async def test_list_flows_return_type(component):
    flows = await component.alist_flows()
    assert isinstance(flows, list)
