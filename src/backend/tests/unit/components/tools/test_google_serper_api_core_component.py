import pytest

from langflow.components.tools import GoogleSerperAPICore
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGoogleSerperAPICore(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GoogleSerperAPICore

    @pytest.fixture
    def default_kwargs(self):
        return {
            "serper_api_key": "test_api_key",
            "input_value": "OpenAI",
            "k": 4,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "google_serper_api", "file_name": "GoogleSerperAPICore"},
        ]

    async def test_search_serper_success(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.search_serper()
        assert result is not None
        assert isinstance(result, DataFrame)
        assert "title" in result.columns
        assert "link" in result.columns
        assert "snippet" in result.columns

    async def test_search_serper_error_handling(self, component_class):
        component = await self.component_setup(
            component_class,
            {
                "serper_api_key": "invalid_key",
                "input_value": "OpenAI",
                "k": 4,
            },
        )
        result = await component.search_serper()
        assert result is not None
        assert isinstance(result, DataFrame)
        assert "error" in result.columns
        assert result["error"].iloc[0] is not None

    async def test_text_search_serper(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        message = await component.text_search_serper()
        assert message is not None
        assert isinstance(message, Message)
        assert "No results found." not in message.text  # Assuming valid input will yield results
