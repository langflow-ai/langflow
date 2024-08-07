import pytest

from langflow.custom.custom_component.custom_component import CustomComponent
from langflow.services.database.models.flow import Flow


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
    assert all(isinstance(flow, Flow) for flow in flows)
