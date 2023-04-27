import importlib
from typing import Dict, List, Optional

import pytest
from langflow.utils.constants import CHAT_OPENAI_MODELS, OPENAI_MODELS
from langflow.utils.util import (
    build_template_from_class,
    build_template_from_function,
    format_dict,
    get_base_classes,
    get_default_factory,
)
from pydantic import BaseModel


# Dummy classes for testing purposes
class Parent(BaseModel):
    """Parent Class"""

    parent_field: str


class Child(Parent):
    """Child Class"""

    child_field: int


class ExampleClass1(BaseModel):
    """Example class 1."""

    def __init__(self, data: Optional[List[int]] = None):
        self.data = data or [1, 2, 3]


class ExampleClass2(BaseModel):
    """Example class 2."""

    def __init__(self, data: Optional[Dict[str, int]] = None):
        self.data = data or {"a": 1, "b": 2, "c": 3}


def example_loader_1() -> ExampleClass1:
    """Example loader function 1."""
    return ExampleClass1()


def example_loader_2() -> ExampleClass2:
    """Example loader function 2."""
    return ExampleClass2()


def test_build_template_from_function():
    type_to_loader_dict = {
        "example1": example_loader_1,
        "example2": example_loader_2,
    }

    # Test with valid name
    result = build_template_from_function("ExampleClass1", type_to_loader_dict)

    assert "template" in result
    assert "description" in result
    assert "base_classes" in result

    # Test with add_function=True
    result_with_function = build_template_from_function(
        "ExampleClass1", type_to_loader_dict, add_function=True
    )
    assert "function" in result_with_function["base_classes"]

    # Test with invalid name
    with pytest.raises(ValueError, match=r".* not found"):
        build_template_from_function("NonExistent", type_to_loader_dict)


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

    # Test 7: Check class name-specific cases (OpenAI, ChatOpenAI)
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
    assert format_dict(input_dict, "ChatOpenAI") == expected_output_openai_chat

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
