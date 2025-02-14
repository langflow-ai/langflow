import pytest

from langflow.components.processing import AlterMetadataComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAlterMetadataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AlterMetadataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": [],
            "text_in": "Sample text",
            "metadata": {"key1": "value1", "key2": "value2"},
            "remove_fields": [],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_process_output_with_metadata(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.process_output()

        assert len(result) == 1
        assert result[0].data["text"] == "Sample text"
        assert result[0].data["key1"] == "value1"
        assert result[0].data["key2"] == "value2"

    def test_process_output_with_removal(self, component_class, default_kwargs):
        default_kwargs["remove_fields"] = ["key1"]
        component = component_class(**default_kwargs)
        result = component.process_output()

        assert len(result) == 1
        assert "key1" not in result[0].data
        assert result[0].data["key2"] == "value2"

    def test_process_output_with_empty_text(self, component_class, default_kwargs):
        default_kwargs["text_in"] = ""
        component = component_class(**default_kwargs)
        result = component.process_output()

        assert len(result) == 0  # No Data object should be created

    def test_process_output_with_input_value(self, component_class, default_kwargs):
        default_kwargs["input_value"] = [Data(data={"existing_key": "existing_value"})]
        component = component_class(**default_kwargs)
        result = component.process_output()

        assert len(result) == 1
        assert result[0].data["existing_key"] == "existing_value"
        assert result[0].data["key1"] == "value1"
        assert result[0].data["key2"] == "value2"
