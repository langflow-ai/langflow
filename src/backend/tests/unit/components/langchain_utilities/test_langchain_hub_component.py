import pytest

from langflow.components.langchain_utilities import LangChainHubPromptComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestLangChainHubPromptComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return LangChainHubPromptComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "langchain_api_key": "test_api_key",
            "langchain_hub_prompt": "efriis/my-first-prompt",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_update_build_config_with_custom_fields(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, "efriis/my-first-prompt", "langchain_hub_prompt")

        assert "param_" in updated_config
        assert "info" in updated_config["langchain_hub_prompt"]
        assert isinstance(updated_config["langchain_hub_prompt"]["info"], str)

    async def test_build_prompt(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        await component.update_build_config({}, "efriis/my-first-prompt", "langchain_hub_prompt")
        result = await component.build_prompt()

        assert result is not None
        assert isinstance(result, Message)
        assert "template" in result.text

    def test_fetch_langchain_hub_template_without_api_key(self, component_class):
        component = component_class(langchain_hub_prompt="efriis/my-first-prompt")

        with pytest.raises(ValueError, match="Please provide a LangChain API Key"):
            component._fetch_langchain_hub_template()
