from langflow.components.tools import YfinanceToolComponent
from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template


def test_yfinance_tool_template():
    yf_tool = YfinanceToolComponent()
    component = Component(_code=yf_tool._code)
    frontend_node, _ = build_custom_component_template(component)
    assert "outputs" in frontend_node
    output_names = [output["name"] for output in frontend_node["outputs"]]
    assert "data" in output_names
    assert "text" in output_names
    assert all(output["types"] != [] for output in frontend_node["outputs"])
