import re

import pytest
from langflow.components.processing import UpdateDataComponent
from langflow.schema import Data


@pytest.fixture
def update_data_component():
    return UpdateDataComponent()


def test_update_build_config(update_data_component):
    build_config = {
        "number_of_fields": {
            "type": "int",
            "value": 2,
        },
        "text_key": {
            "type": "str",
            "value": "",
        },
        "text_key_validator": {
            "type": "bool",
            "value": False,
        },
    }
    updated_config = update_data_component.update_build_config(
        build_config=build_config, field_value=3, field_name="number_of_fields"
    )

    assert "field_1_key" in updated_config
    assert "field_2_key" in updated_config
    assert "field_3_key" in updated_config
    assert updated_config["number_of_fields"]["value"] == 3


def test_update_build_config_exceed_limit(update_data_component):
    build_config = {
        "number_of_fields": {
            "type": "int",
            "value": 2,
        },
        "text_key": {
            "type": "str",
            "value": "",
        },
        "text_key_validator": {
            "type": "bool",
            "value": False,
        },
    }
    with pytest.raises(ValueError, match=re.escape("Number of fields cannot exceed 15.")):
        update_data_component.update_build_config(build_config, 16, "number_of_fields")


async def test_build_data(update_data_component):
    update_data_component._attributes = {
        "field_1_key": {"key1": "new_value1"},
        "field_2_key": {"key3": "value3"},
    }
    update_data_component.text_key = "key1"
    update_data_component.text_key_validator = False
    update_data_component.old_data = Data(data={"key1": "old_value1", "key2": "value2"}, text_key="key2")

    result = await update_data_component.build_data()

    assert isinstance(result, Data)
    assert result.data == {"key1": "new_value1", "key2": "value2", "key3": "value3"}
    assert result.text_key == "key1"


def test_get_data(update_data_component):
    update_data_component._attributes = {
        "field_1_key": {"key1": "value1"},
        "field_2_key": {"key2": "value2"},
    }

    result = update_data_component.get_data()

    assert result == {"key1": "value1", "key2": "value2"}


def test_validate_text_key_valid(update_data_component):
    data = Data(data={"key1": "value1", "key2": "value2"}, text_key="key1")
    update_data_component.text_key = "key1"

    try:
        update_data_component.validate_text_key(data)
    except ValueError:
        pytest.fail("validate_text_key() raised ValueError unexpectedly!")


def test_validate_text_key_invalid(update_data_component):
    data = Data(data={"key1": "value1", "key2": "value2"}, text_key="key1")
    update_data_component.text_key = "invalid_key"
    with pytest.raises(ValueError) as exc_info:  # noqa: PT011
        update_data_component.validate_text_key(data)
    expected_error_message = (
        f"Text Key: '{update_data_component.text_key}' not found in the Data keys: {', '.join(data.data.keys())}"
    )
    assert str(exc_info.value) == expected_error_message
