from langflow.utils.constants import CHAT_OPENAI_MODELS, OPENAI_MODELS
from pydantic import BaseModel
import pytest
import re
import importlib
from typing import Dict
from langflow.utils.util import (
    build_template_from_class,
    format_dict,
    get_base_classes,
    get_default_factory,
    get_class_doc,
)


# Dummy classes for testing purposes
class Parent(BaseModel):
    """Parent Class"""

    parent_field: str


class Child(Parent):
    """Child Class"""

    child_field: int


# Test build_template_from_class
def test_build_template_from_class():
    type_to_cls_dict: Dict[str, type] = {"parent": Parent, "child": Child}

    # Test valid input
    result = build_template_from_class("Child", type_to_cls_dict)
    assert "template" in result
    assert "description" in result
    assert "base_classes" in result
    assert "Child" in result["base_classes"]
    assert "Parent" in result["base_classes"]
    assert result["description"] == "Child Class"

    # Test invalid input
    with pytest.raises(ValueError, match="InvalidClass not found."):
        build_template_from_class("InvalidClass", type_to_cls_dict)


# Test format_dict
def test_format_dict():
    # Test 1: Optional type removal
    input_dict = {
        "field1": {"type": "Optional[str]", "required": False},
    }
    expected_output = {
        "field1": {
            "type": "str",
            "required": False,
            "list": False,
            "show": False,
            "password": False,
            "multiline": False,
        },
    }
    assert format_dict(input_dict) == expected_output

    # Test 2: List type processing
    input_dict = {
        "field1": {"type": "List[str]", "required": False},
    }
    expected_output = {
        "field1": {
            "type": "str",
            "required": False,
            "list": True,
            "show": False,
            "password": False,
            "multiline": False,
        },
    }
    assert format_dict(input_dict) == expected_output

    # Test 3: Mapping type replacement
    input_dict = {
        "field1": {"type": "Mapping[str, int]", "required": False},
    }
    expected_output = {
        "field1": {
            "type": "code",  # Mapping type is replaced with dict which is replaced with code
            "required": False,
            "list": False,
            "show": False,
            "password": False,
            "multiline": False,
        },
    }
    assert format_dict(input_dict) == expected_output

    # Test 4: Replace default value with actual value
    input_dict = {
        "field1": {"type": "str", "required": False, "default": "test"},
    }
    expected_output = {
        "field1": {
            "type": "str",
            "required": False,
            "list": False,
            "show": False,
            "password": False,
            "multiline": False,
            "value": "test",
        },
    }
    assert format_dict(input_dict) == expected_output

    # Test 5: Add password field
    input_dict = {
        "field1": {"type": "str", "required": False},
        "api_key": {"type": "str", "required": False},
    }
    expected_output = {
        "field1": {
            "type": "str",
            "required": False,
            "list": False,
            "show": False,
            "password": False,
            "multiline": False,
        },
        "api_key": {
            "type": "str",
            "required": False,
            "list": False,
            "show": True,
            "password": True,
            "multiline": False,
        },
    }
    assert format_dict(input_dict) == expected_output

    # Test 6: Add multiline
    input_dict = {
        "field1": {"type": "str", "required": False},
        "prefix": {"type": "str", "required": False},
    }
    expected_output = {
        "field1": {
            "type": "str",
            "required": False,
            "list": False,
            "show": False,
            "password": False,
            "multiline": False,
        },
        "prefix": {
            "type": "str",
            "required": False,
            "list": False,
            "show": True,
            "password": False,
            "multiline": True,
        },
    }
    assert format_dict(input_dict) == expected_output

    # Test 7: Check class name-specific cases (OpenAI, OpenAIChat)
    input_dict = {
        "model_name": {"type": "str", "required": False},
    }
    expected_output_openai = {
        "model_name": {
            "type": "str",
            "required": False,
            "list": True,
            "show": True,
            "password": False,
            "multiline": False,
            "options": OPENAI_MODELS,
        },
    }
    expected_output_openai_chat = {
        "model_name": {
            "type": "str",
            "required": False,
            "list": True,
            "show": True,
            "password": False,
            "multiline": False,
            "options": CHAT_OPENAI_MODELS,
        },
    }
    assert format_dict(input_dict, "OpenAI") == expected_output_openai
    assert format_dict(input_dict, "OpenAIChat") == expected_output_openai_chat

    # Test 8: Replace dict type with str
    input_dict = {
        "field1": {"type": "Dict[str, int]", "required": False},
    }
    expected_output = {
        "field1": {
            "type": "code",
            "required": False,
            "list": False,
            "show": False,
            "password": False,
            "multiline": False,
        },
    }
    assert format_dict(input_dict) == expected_output


# Test get_base_classes
def test_get_base_classes():
    base_classes_parent = get_base_classes(Parent)
    base_classes_child = get_base_classes(Child)

    assert "Parent" in base_classes_parent
    assert "Child" in base_classes_child
    assert "Parent" in base_classes_child


# Test get_default_factory
def test_get_default_factory():
    module_name = "langflow.utils.util"
    function_repr = "<function dummy_function>"

    def dummy_function():
        return "default_value"

    # Add dummy_function to your_module
    setattr(importlib.import_module(module_name), "dummy_function", dummy_function)

    default_value = get_default_factory(module_name, function_repr)

    assert default_value == "default_value"


# Test get_class_doc
def test_get_class_doc():
    class_doc_parent = get_class_doc(Parent)
    class_doc_child = get_class_doc(Child)

    assert class_doc_parent["Description"] == "Parent Class"
    assert class_doc_child["Description"] == "Child Class"
