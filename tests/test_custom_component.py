import ast
import pytest
from fastapi import HTTPException
from langflow.interface.custom.custom_component import CustomComponent
from langflow.interface.custom.constants import DEFAULT_CUSTOM_COMPONENT_CODE


# Test the __init__ method
def test_init():
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)
    assert isinstance(component, CustomComponent)
    assert component.code == DEFAULT_CUSTOM_COMPONENT_CODE


# Test the _handle_import method
def test_handle_import():
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)
    node = ast.parse("import math").body[0]
    component._handle_import(node)
    assert "math" in component.class_template["imports"]


# Test the _handle_class method
def test_handle_class():
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)
    node = ast.parse("class Test: pass").body[0]
    component._handle_class(node)
    assert component.class_template["class"]["name"] == "Test"


# Test the _handle_function method
def test_handle_function():
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)
    node = ast.parse("def func(): pass").body[0]
    component._handle_function(node)
    function_data = {"name": "func", "arguments": [], "return_type": "None"}
    assert function_data in component.class_template["functions"]


# Test the transform_list method
def test_transform_list():
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)
    input_list = ["var1: int", "var2: str", "var3"]
    output_list = [["var1", "int"], ["var2", "str"], ["var3", None]]
    assert component.transform_list(input_list) == output_list


# Test the extract_class_info method with valid code
def test_extract_class_info():
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)
    class_info = component.extract_class_info()
    assert "requests" in class_info["imports"]
    assert class_info["class"]["name"] == "YourComponent"
    function_data = {
        "name": "build",
        "arguments": ["self", "url: str", "llm: BaseLLM", "template: Prompt"],
        "return_type": "Document",
    }
    assert function_data in class_info["functions"]


# Test the extract_class_info method with invalid code
def test_extract_class_info_invalid_code():
    component = CustomComponent(field_config={}, code="invalid code")
    with pytest.raises(HTTPException) as e:
        component.extract_class_info()

    exception = e.value
    assert exception.status_code == 400
    assert exception.detail["error"] == "invalid syntax"


# Test the get_entrypoint_function_args_and_return_type method
def test_get_entrypoint_function_args_and_return_type():
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)
    (
        function_args,
        return_type,
        template_config,
    ) = component.get_entrypoint_function_args_and_return_type()
    assert function_args == [
        ["self", None],
        ["url", "str"],
        ["llm", "BaseLLM"],
        ["template", "Prompt"],
    ]
    assert return_type == "Document"
    assert template_config == {
        "description": "Your description",
        "display_name": "Your Component",
        "field_config": {"url": {"multiline": True, "required": True}},
    }


# Test the _build_template_config method
def test__build_template_config():
    attributes = {
        "field_config": "'field_config_value'",
        "display_name": "'display_name_value'",
        "description": "'description_value'",
    }
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)
    template_config = component._build_template_config(attributes)

    assert template_config == {
        "field_config": "field_config_value",
        "display_name": "display_name_value",
        "description": "description_value",
    }


# Test the _class_template_validation method with a valid class template
def test__class_template_validation_valid():
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)
    assert component._class_template_validation(code=component.data) is True


# Test the _class_template_validation method with an invalid class template
def test__class_template_validation_invalid():
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)
    class_template = {}

    with pytest.raises(Exception) as e:
        component._class_template_validation(class_template)

    exception = e.value
    assert exception.status_code == 400
    assert exception.detail["error"] == "The main class must have a valid name."


# Test the build method
def test_build():
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)
    with pytest.raises(Exception) as e:
        component.build()

    assert e.type == NotImplementedError


# Test the data property
def test_data():
    code = DEFAULT_CUSTOM_COMPONENT_CODE
    component = CustomComponent(field_config={}, code=code)
    class_info = component.data
    assert "requests" in class_info["imports"]
    assert class_info["class"]["name"] == "YourComponent"
    function_data = {
        "name": "build",
        "arguments": ["self", "url: str", "llm: BaseLLM", "template: Prompt"],
        "return_type": "Document",
    }
    assert function_data in class_info["functions"]


# Test the is_check_valid method
def test_is_check_valid():
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)

    assert component.is_check_valid() is True


# Test the args_and_return_type property
def test_args_and_return_type():
    component = CustomComponent(field_config={}, code=DEFAULT_CUSTOM_COMPONENT_CODE)

    function_args, return_type, template_config = component.args_and_return_type

    assert function_args == [
        ["self", None],
        ["url", "str"],
        ["llm", "BaseLLM"],
        ["template", "Prompt"],
    ]

    assert return_type == "Document"
    assert template_config == {
        "description": "Your description",
        "display_name": "Your Component",
        "field_config": {"url": {"multiline": True, "required": True}},
    }
