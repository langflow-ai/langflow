import pytest
from langflow.components.prompts import PromptComponent
from langflow.custom.eval import eval_custom_component_code

from tests.constants import SUPPORTED_VERSIONS
from tests.integration.utils import download_component_from_github


def build_component_instance_for_tests(version: str, file_name: str = "Prompt", **kwargs):
    component = download_component_from_github("prompts", file_name, version)
    cc_class = eval_custom_component_code(component._code)
    cc_instance = cc_class(**kwargs)
    return cc_instance()


@pytest.mark.usefixtures("client")
class TestPromptComponent:
    DEFAULT_KWARGS = {"template": "Hello {name}!", "name": "John", "_session_id": "123"}

    def test_post_code_processing(self):
        component = PromptComponent(**self.DEFAULT_KWARGS)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]
        assert node_data["template"]["template"]["value"] == "Hello {name}!"
        assert "name" in node_data["custom_fields"]["template"]
        assert "name" in node_data["template"]
        assert node_data["template"]["name"]["value"] == "John"

    @pytest.mark.parametrize("version", SUPPORTED_VERSIONS)
    def test_prompt_component_versions(self, version):
        result = build_component_instance_for_tests(version, **self.DEFAULT_KWARGS)
        assert result is not None

    def test_prompt_component_latest(self):
        result = PromptComponent(**self.DEFAULT_KWARGS)()
        assert result is not None
