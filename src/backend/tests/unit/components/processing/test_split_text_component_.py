import pytest
from langflow.components.processing import SplitTextComponent
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
            "data_inputs": [Data(text="Hello world! This is a test.", data={})],
            "chunk_overlap": 5,
            "chunk_size": 10,
            "separator": " ",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_split_text_functionality(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.split_text()
        assert result is not None
        assert len(result) > 0
        assert all(isinstance(chunk, Data) for chunk in result)

    def test_as_dataframe_functionality(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        dataframe = component.as_dataframe()
        assert dataframe is not None
        assert hasattr(dataframe, "to_dict")  # Assuming DataFrame has a to_dict method
        assert len(dataframe.to_dict()) > 0

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
