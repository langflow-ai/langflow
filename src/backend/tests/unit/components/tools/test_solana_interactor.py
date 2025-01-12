from langflow.components.tools import SolanaDAppInteractor
from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template


def test_solana_dapp_interactor_template():
    solana_interactor = SolanaDAppInteractor()
    component = Component(_code=solana_interactor._code)
    frontend_node, _ = build_custom_component_template(component)

    # Check that the "outputs" key is present in the frontend node
    assert "outputs" in frontend_node

    # Verify the output names
    output_names = [output["name"] for output in frontend_node["outputs"]]
    assert "execution_result" in output_names

    # Ensure that all outputs have types defined
    assert all(output["types"] != [] for output in frontend_node["outputs"])
