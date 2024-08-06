from langflow.services.database.models.flow import Flow


def test_list_flows_flow_objects(component):
    flows = component.list_flows()
    assert all(isinstance(flow, Flow) for flow in flows)
