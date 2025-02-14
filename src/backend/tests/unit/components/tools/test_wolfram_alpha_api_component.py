import pytest

from langflow.components.tools import WolframAlphaAPIComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestWolframAlphaAPIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return WolframAlphaAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"input_value": "What is the population of France?", "app_id": "test_app_id"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Data)

    def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "wolfram_alpha_api"
        assert tool.description == "Answers mathematical questions."
        assert callable(tool.func)

    def test_build_wrapper(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        wrapper = component._build_wrapper()
        assert wrapper is not None
        assert wrapper.wolfram_alpha_appid == default_kwargs["app_id"]
