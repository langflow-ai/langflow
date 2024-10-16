from langflow.components.tools.PythonREPLTool import PythonREPLToolComponent
from langflow.custom.custom_component.component import Component
from langflow.custom.utils import build_custom_component_template


def test_python_repl_tool_template():
    python_repl_tool = PythonREPLToolComponent()
    component = Component(_code=python_repl_tool._code)
    frontend_node, _ = build_custom_component_template(component)
    assert "outputs" in frontend_node
    output_names = [output["name"] for output in frontend_node["outputs"]]
    assert "api_run_model" in output_names
    assert "api_build_tool" in output_names
    assert all(output["types"] != [] for output in frontend_node["outputs"])

    # Additional assertions specific to PythonREPLToolComponent
    input_names = [input_["name"] for input_ in frontend_node["template"].values() if isinstance(input_, dict)]
    # assert "input_value" in input_names
    assert "name" in input_names
    assert "description" in input_names
    assert "global_imports" in input_names

    global_imports_input = next(
        input_
        for input_ in frontend_node["template"].values()
        if isinstance(input_, dict) and input_["name"] == "global_imports"
    )
    assert global_imports_input["type"] == "str"
    # assert global_imports_input["combobox"] is True
    assert global_imports_input["value"] == "math"
