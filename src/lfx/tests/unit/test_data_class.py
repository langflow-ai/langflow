import copy

import pytest
from langchain_core.documents import Document

from lfx.schema import Data


def test_data_initialization():
    record = Data(text_key="msg", data={"msg": "Hello, World!", "extra": "value"})
    assert record.msg == "Hello, World!"
    assert record.extra == "value"


def test_validate_data_with_extra_keys():
    record = Data(dummy_key="dummy", data={"key": "value"})
    assert record.data["dummy_key"] == "dummy"
    assert "dummy_key" in record.data
    assert record.key == "value"


def test_conversion_to_document():
    record = Data(data={"text": "Sample text", "meta": "data"})
    document = record.to_lc_document()
    assert document.page_content == "Sample text"
    assert document.metadata == {"meta": "data"}


def test_conversion_from_document():
    document = Document(page_content="Doc content", metadata={"meta": "info"})
    record = Data.from_document(document)
    assert record.text == "Doc content"
    assert record.meta == "info"


def test_add_method_for_strings():
    record1 = Data(data={"text": "Hello"})
    record2 = Data(data={"text": " World"})
    combined = record1 + record2
    assert combined.text == "Hello World"


def test_add_method_for_integers():
    record1 = Data(data={"number": 5})
    record2 = Data(data={"number": 10})
    combined = record1 + record2
    expected_number = 15
    assert combined.number == expected_number


def test_add_method_with_non_overlapping_keys():
    record1 = Data(data={"text": "Hello"})
    record2 = Data(data={"number": 10})
    combined = record1 + record2
    assert combined.text == "Hello"
    expected_number = 10
    assert combined.number == expected_number


def test_custom_attribute_get_set_del():
    record = Data()
    record.custom_attr = "custom_value"
    assert record.custom_attr == "custom_value"
    del record.custom_attr
    with pytest.raises(AttributeError):
        _ = record.custom_attr


def test_deep_copy():
    record1 = Data(data={"text": "Hello", "number": 10})
    record2 = copy.deepcopy(record1)
    assert record2.text == "Hello"
    expected_number = 10
    assert record2.number == expected_number
    record2.text = "World"
    assert record1.text == "Hello"  # Ensure original is unchanged


def test_custom_attribute_setting_and_getting():
    record = Data()
    record.dynamic_attribute = "Dynamic Value"
    assert record.dynamic_attribute == "Dynamic Value"


def test_str_and_dir_methods():
    record = Data(text_key="text", data={"text": "Test Text", "key": "value"})
    assert "Test Text" in str(record)
    assert "key" in dir(record)
    assert "data" in dir(record)


def test_dir_includes_data_keys():
    record = Data(data={"text": "Hello", "new_attr": "value"})
    dir_output = dir(record)

    # Check for standard attributes
    assert "data" in dir_output
    assert "text_key" in dir_output
    assert "__add__" in dir_output  # Checking for a method

    # Check for dynamic attributes from data
    assert "text" in dir_output
    assert "new_attr" in dir_output

    # Optionally, verify that dynamically added attributes are listed
    record.dynamic_attr = "dynamic"
    assert "dynamic_attr" in dir_output or "dynamic_attr" in dir(record)  # To account for the change


def test_dir_reflects_attribute_deletion():
    record = Data(data={"removable": "I can be removed"})
    assert "removable" in dir(record)

    # Delete the attribute and check again
    del record.removable
    assert "removable" not in dir(record)


def test_get_text_with_text_key():
    data = {"text": "Hello, World!"}
    schema = Data(data=data, text_key="text", default_value="default")
    result = schema.get_text()
    assert result == "Hello, World!"


def test_get_text_without_text_key():
    data = {"other_key": "Hello, World!"}
    schema = Data(data=data, text_key="text", default_value="default")
    result = schema.get_text()
    assert result == "default"


def test_get_text_with_empty_data():
    data = {}
    schema = Data(data=data, text_key="text", default_value="default")
    result = schema.get_text()
    assert result == "default"


def test_get_text_with_none_data():
    data = None
    schema = Data(data=data, text_key="text", default_value="default")
    result = schema.get_text()
    assert result == "default"
    assert schema.data == {}


def test_data_concatenation_different_fields():
    record1 = Data(data={"text": "Hello"})
    record2 = Data(data={"number": 10})
    combined = record1 + record2
    assert combined.text == "Hello"
    expected_number = 10
    assert combined.number == expected_number


def test_data_copy():
    record1 = Data(data={"text": "Hello", "number": 10})
    record2 = copy.deepcopy(record1)
    assert record2.text == "Hello"
    expected_number = 10
    assert record2.number == expected_number
    record2.text = "World"
    assert record1.text == "Hello"  # Ensure original is unchanged
    assert record2.text == "World"


def test_data_field_access():
    record = Data()
    record.name = "John"
    assert "name" in record.data
    assert record.data["name"] == "John"
