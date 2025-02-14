import pytest
from langflow.components.processing import CombineTextComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCombineTextComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CombineTextComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"text1": "Hello", "text2": "World", "delimiter": ", "}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "text", "file_name": "CombineText"},
        ]

    def test_combine_texts(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.combine_texts()
        assert result is not None
        assert result.text == "Hello, World"
        assert component.status == "Hello, World"

    def test_combine_texts_with_default_delimiter(self, component_class):
        default_kwargs = {"text1": "Hello", "text2": "World"}
        component = component_class(**default_kwargs)
        result = component.combine_texts()
        assert result is not None
        assert result.text == "Hello World"
        assert component.status == "Hello World"
