import pytest

from langflow.components.agentql import AgentQL
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAgentQLComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AgentQL

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "url": "https://example.com",
            "query": "SELECT * FROM data",
            "timeout": 900,
            "params": {
                "mode": "fast",
                "wait_for": 0,
                "is_scroll_to_bottom_enabled": False,
                "is_screenshot_enabled": False,
            },
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "agentql", "file_name": "AgentQL"},
        ]

    async def test_build_output_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build_output()
        assert result is not None
        assert hasattr(result, "result")
        assert hasattr(result, "metadata")

    async def test_build_output_invalid_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.api_key = "invalid_api_key"
        with pytest.raises(ValueError) as exc_info:
            await component.build_output()
        assert "Please, provide a valid API Key." in str(exc_info.value)

    async def test_build_output_http_error(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.url = "https://invalid-url.com"
        with pytest.raises(ValueError) as exc_info:
            await component.build_output()
        assert "HTTP" in str(exc_info.value)

    async def test_build_output_timeout(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.timeout = 1  # Set a low timeout to trigger a timeout error
        with pytest.raises(ValueError) as exc_info:
            await component.build_output()
        assert "HTTP" in str(exc_info.value)
