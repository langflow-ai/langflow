import pytest

from langflow.components.processing import CreateDataComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCreateDataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CreateDataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "number_of_fields": 1,
            "text_key": "field_1_key",
            "text_key_validator": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "data", "file_name": "CreateData"},
        ]

    def test_update_build_config_with_valid_fields(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, 3, "number_of_fields")

        assert updated_config["number_of_fields"]["value"] == 3
        assert "field_1_key" in updated_config
        assert "field_2_key" in updated_config
        assert "field_3_key" in updated_config

    def test_update_build_config_exceeds_max_fields(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}

        with pytest.raises(ValueError, match="Number of fields cannot exceed 15"):
            component.update_build_config(build_config, 20, "number_of_fields")

    async def test_build_data_without_validation(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build_data()

        assert result is not None
        assert isinstance(result, Data)
        assert result.text_key == "field_1_key"

    async def test_build_data_with_validation(self, component_class):
        default_kwargs = {
            "number_of_fields": 1,
            "text_key": "field_1_key",
            "text_key_validator": True,
        }
        component = component_class(**default_kwargs)
        component.update_build_config({}, 1, "number_of_fields")

        result = await component.build_data()

        assert result is not None
        assert isinstance(result, Data)

    def test_validate_text_key_success(self, component_class):
        default_kwargs = {
            "number_of_fields": 1,
            "text_key": "field_1_key",
            "text_key_validator": True,
        }
        component = component_class(**default_kwargs)
        component.update_build_config({}, 1, "number_of_fields")

        try:
            component.validate_text_key()
        except ValueError:
            pytest.fail("validate_text_key raised ValueError unexpectedly!")

    def test_validate_text_key_failure(self, component_class):
        default_kwargs = {
            "number_of_fields": 1,
            "text_key": "invalid_key",
            "text_key_validator": True,
        }
        component = component_class(**default_kwargs)
        component.update_build_config({}, 1, "number_of_fields")

        with pytest.raises(ValueError, match="Text Key: 'invalid_key' not found in the Data keys"):
            component.validate_text_key()
