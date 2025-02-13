import pytest

from langflow.components.deactivated import SplitTextComponent
from langflow.schema import Data
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSplitTextComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SplitTextComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "data_inputs": [Data(text="Hello world! This is a test document.", data={})],
            "chunk_overlap": 5,
            "chunk_size": 20,
            "separator": " ",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "text_splitters", "file_name": "SplitText"},
        ]

    def test_split_text_functionality(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.split_text()

        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(chunk, Data) for chunk in result)

    def test_split_text_with_custom_separator(self, component_class):
        custom_kwargs = {
            "data_inputs": [Data(text="Hello, world! This is a test document.", data={})],
            "chunk_overlap": 5,
            "chunk_size": 20,
            "separator": ", ",
        }
        component = component_class(**custom_kwargs)
        result = component.split_text()

        assert result is not None
        assert len(result) > 0
        assert all(isinstance(chunk, Data) for chunk in result)
        assert all("Hello" in chunk.text or "world!" in chunk.text for chunk in result)

    def test_split_text_empty_input(self, component_class):
        empty_kwargs = {"data_inputs": [], "chunk_overlap": 5, "chunk_size": 20, "separator": " "}
        component = component_class(**empty_kwargs)
        result = component.split_text()

        assert result == []
