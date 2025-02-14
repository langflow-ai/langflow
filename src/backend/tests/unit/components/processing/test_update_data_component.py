import pytest

from langflow.components.processing import UpdateDataComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestUpdateDataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return UpdateDataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "old_data": [{"key1": "value1"}, {"key2": "value2"}],
            "number_of_fields": 2,
            "text_key": "key1",
            "text_key_validator": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "data", "file_name": "UpdateData"},
        ]

    def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, 3, "number_of_fields")

        assert updated_config["number_of_fields"]["value"] == 3
        assert "field_1_key" in updated_config
        assert "field_2_key" in updated_config
        assert "field_3_key" in updated_config

    async def test_build_data_with_list(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build_data()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["key1"] == "value1"
        assert result[1]["key2"] == "value2"

    async def test_build_data_with_single(self, component_class):
        single_data_kwargs = {
            "old_data": {"key1": "value1"},
            "number_of_fields": 1,
            "text_key": "key1",
            "text_key_validator": True,
        }
        component = component_class(**single_data_kwargs)
        result = await component.build_data()

        assert isinstance(result, dict)
        assert result["key1"] == "value1"

    def test_validate_text_key_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        data = {"key1": "value1"}
        component.validate_text_key(data)  # Should not raise

    def test_validate_text_key_failure(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        data = {"key2": "value2"}

        with pytest.raises(ValueError, match="Text Key: 'key1' not found in the Data keys"):
            component.validate_text_key(data)
