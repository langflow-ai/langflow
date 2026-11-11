"""Offline dry runs compare the effective values of grouped components."""

from copy import deepcopy

import pytest
from langflow.upgrade_check.engine import Target, check_nodes, flow_status
from lfx.custom import Component
from lfx.custom.utils import build_custom_component_template

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
def test_dry_run_rejects_retyping_a_nonempty_group_value(depth):
    saved, _ = build_custom_component_template(Component(_code=CODE))
    current, _ = build_custom_component_template(
        Component(_code=CODE.replace("StrInput", "IntInput").replace('value=""', "value=0"))
    )
    node = {"id": "leaf", "data": {"id": "leaf", "type": "SavedValueComponent", "node": saved}}
    field_name = "value"
    for level in range(depth):
        exposed = {**deepcopy(node["data"]["node"]["template"][field_name]), "value": "saved group value"}
        exposed["proxy"] = {"id": node["id"], "field": field_name}
        field_name = f"exposed_{level}"
        node = {
            "id": f"group-{level}",
            "data": {
                "node": {
                    "template": {field_name: exposed},
                    "flow": {"data": {"nodes": [node], "edges": []}},
                }
            },
        }
    flow = {"nodes": [node], "edges": []}
    original = deepcopy(flow)

    results, _ = check_nodes(flow, Target.from_registry({"Test": {"SavedValueComponent": current}}))

    assert flow_status(results) == "fail"
    assert results[0].status == "outdated_breaking"
    assert results[0].dry_run == {"result": "loses"}
    assert any(reason["code"] == "value_dropped" and reason["field"] == "value" for reason in results[0].reasons)
    assert flow == original
