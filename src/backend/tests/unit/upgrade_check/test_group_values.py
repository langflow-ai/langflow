"""Upgrade checks and repairs compare the effective values of grouped components."""

from copy import deepcopy

import pytest
from langflow.services.flow_repair.planning import plan_flow_repair
from langflow.upgrade_check.engine import Target, check_nodes, flow_status
from lfx.custom import Component
from lfx.custom.utils import build_custom_component_template
from lfx.graph.graph.utils import process_flow

CODE = """from lfx.custom import Component
from lfx.io import StrInput, Output
class SavedValueComponent(Component):
    display_name = "Saved Value"
    inputs = [StrInput(name="value", value="")]
    outputs = [Output(name="result", method="result")]
    def result(self) -> str:
        return str(self.value)
"""


@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize(
    ("group_state", "repair_reason"),
    [
        pytest.param({"value": ""}, None, id="empty-string"),
        pytest.param({"value": None}, None, id="null"),
        pytest.param({"value": []}, None, id="empty-list"),
        pytest.param({"value": {}}, None, id="empty-dict"),
        pytest.param({"value": "saved group value"}, "outdated_breaking", id="saved"),
        pytest.param({"value": None, "load_from_db": True}, "preservation_failed", id="global-reference"),
    ],
)
def test_retyping_a_group_input_preserves_saved_state(depth, group_state, repair_reason):
    saved, _ = build_custom_component_template(Component(_code=CODE))
    current, _ = build_custom_component_template(
        Component(_code=CODE.replace("StrInput", "IntInput").replace('value=""', "value=0"))
    )
    node = {"id": "leaf", "data": {"id": "leaf", "type": "SavedValueComponent", "node": saved}}
    field_name = "value"
    for level in range(depth):
        exposed = deepcopy(node["data"]["node"]["template"][field_name])
        exposed.update(group_state, proxy={"id": node["id"], "field": field_name})
        field_name = f"exposed_{level}"
        group_id = f"group-{level}"
        node = {
            "id": group_id,
            "data": {
                "id": group_id,
                "node": {
                    "template": {field_name: exposed},
                    "flow": {"data": {"nodes": [node], "edges": []}},
                },
            },
        }
    flow = {"nodes": [node], "edges": []}
    original = deepcopy(flow)

    registry = {"Test": {"SavedValueComponent": current}}
    results, _ = check_nodes(flow, Target.from_registry(registry))
    plan = plan_flow_repair(flow, registry)

    assert flow == original
    [result] = results
    if repair_reason:
        assert flow_status(results) == "fail"
        assert result.status == "outdated_breaking"
        assert result.dry_run == {"result": "loses"}
        assert [(reason["code"], reason["field"]) for reason in result.reasons] == [("value_dropped", "value")]
        assert plan.data is None
        assert plan.reason_codes == [repair_reason]
    else:
        assert flow_status(results) == "ok"
        assert result.status == "outdated_safe"
        assert result.dry_run == {"result": "keeps"}
        assert result.reasons == []
        assert plan.updated_nodes == 1
        assert plan.reason_codes == []
        exposed = plan.data["nodes"][0]["data"]["node"]["template"][field_name]
        [runtime] = process_flow(plan.data)["nodes"]
        for field in (exposed, runtime["data"]["node"]["template"]["value"]):
            assert field["type"] == current["template"]["value"]["type"]
            assert field["value"] == 0
