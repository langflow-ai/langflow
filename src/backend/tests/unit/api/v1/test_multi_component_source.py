"""Editing a multi-class component must retain the selected class and its hooks."""

import pytest
from langflow.api.v1.schemas import CustomComponentRequest
from lfx.custom.eval import eval_custom_component_code
from lfx.custom.utils import create_component_template

SOURCE = """
from lfx.custom import Component
from lfx.io import Output, StrInput
from lfx.schema.data import Data

class First(Component):
    display_name = "First"
    outputs = [Output(name="first", display_name="First", method="run")]

    def run(self) -> Data:
        return Data(data={"which": "First"})

class Second(Component):
    display_name = "Second"
    inputs = [StrInput(name="value", display_name="Value", real_time_refresh=True)]
    outputs = [Output(name="second", display_name="Second", method="run")]

    def run(self) -> Data:
        return Data(data={"which": "Second"})

    def update_build_config(self, build_config, field_value, field_name=None):
        if field_name == "value":
            build_config["value"]["display_name"] = f"Updated: {field_value}"
        return build_config
"""


@pytest.mark.parametrize("endpoint", ["custom_component", "custom_component/update"])
async def test_should_preserve_selected_class_through_editor_requests(client, logged_in_headers, endpoint):
    component = eval_custom_component_code(SOURCE, class_name="Second")(_code=SOURCE)
    template, _ = create_component_template(component_extractor=component)
    # This is the identity supplied by the palette and retained in saved nodes.
    template["metadata"]["component_class_name"] = "Second"
    request = {"code": SOURCE, "frontend_node": template}
    if endpoint.endswith("/update"):
        request.update(template=template["template"], field="value", field_value="changed")

    response = await client.post(f"api/v1/{endpoint}", json=request, headers=logged_in_headers)

    assert response.status_code == 200, response.text
    updated = response.json() if endpoint.endswith("/update") else response.json()["data"]
    assert updated["display_name"] == "Second"
    assert [output["name"] for output in updated["outputs"]] == ["second"]
    assert updated["metadata"]["component_class_name"] == "Second"
    if endpoint.endswith("/update"):
        assert updated["template"]["value"]["display_name"] == "Updated: changed"


@pytest.mark.parametrize("metadata", [None, [], "invalid", {"component_class_name": []}, {"component_class_name": 1}])
def test_should_ignore_malformed_class_identity(metadata):
    request = CustomComponentRequest(code=SOURCE, frontend_node={"metadata": metadata})
    assert request.get_class_name() is None
