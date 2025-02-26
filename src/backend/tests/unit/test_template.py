import importlib

import pytest
from langflow.utils.util import build_template_from_function, get_base_classes, get_default_factory

from pydantic import BaseModel


# Dummy classes for testing purposes
class Parent(BaseModel):
    """Parent Class."""

    parent_field: str


class Child(Parent):
    """Child Class."""

    child_field: int


class ExampleClass1(BaseModel):
    """Example class 1."""

    def __init__(self, data: list[int] | None = None):
        self.data = data or [1, 2, 3]


class ExampleClass2(BaseModel):
    """Example class 2."""

    def __init__(self, data: dict[str, int] | None = None):
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

    assert result is not None
    assert "template" in result
    assert "description" in result
    assert "base_classes" in result

    # Test with add_function=True
    result_with_function = build_template_from_function("ExampleClass1", type_to_loader_dict, add_function=True)
    assert result_with_function is not None
    assert "Callable" in result_with_function["base_classes"]

    # Test with invalid name
    with pytest.raises(ValueError, match=r".* not found"):
        build_template_from_function("NonExistent", type_to_loader_dict)


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
    importlib.import_module(module_name).dummy_function = dummy_function

    default_value = get_default_factory(module_name, function_repr)

    assert default_value == "default_value"
