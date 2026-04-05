"""Tests for langflow.helpers.custom module."""

from langflow.helpers.custom import format_type


class TestFormatType:
    def test_str_type(self):
        assert format_type(str) == "Text"

    def test_named_type(self):
        assert format_type(int) == "int"

    def test_class_instance(self):
        class MyClass:
            pass

        obj = MyClass()
        assert format_type(obj) == "MyClass"

    def test_string_value(self):
        # str instance has __class__ so goes through that branch
        result = format_type("hello")
        assert result == "str"

    def test_list_type(self):
        assert format_type(list) == "list"

    def test_dict_type(self):
        assert format_type(dict) == "dict"
