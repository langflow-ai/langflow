import ast
import types
from pathlib import Path
from textwrap import dedent

import pytest
from langchain_core.documents import Document

from lfx.custom import Component, CustomComponent
from lfx.custom.code_parser.code_parser import CodeParser, CodeSyntaxError
from lfx.custom.custom_component.base_component import BaseComponent, ComponentCodeNullError
from lfx.custom.utils import build_custom_component_template


@pytest.fixture
def code_component_with_multiple_outputs():
    path = Path(__file__).parent.parent / "data" / "component_multiple_outputs.py"
    code = path.read_text(encoding="utf-8")
    return Component(_code=code)


code_default = """
from langflow.custom import CustomComponent

from langflow.field_typing import BaseLanguageModel
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_core.documents import Document

import requests

class YourComponent(CustomComponent):
    display_name: str = "Your Component"
    description: str = "Your description"
    field_config = { "url": { "multiline": True, "required": True } }

    def build(self, url: str, llm: BaseLanguageModel) -> Document:
        return Document(page_content="Hello World")
"""


def test_code_parser_init():
    """Test the initialization of the CodeParser class."""
    parser = CodeParser(code_default)
    assert parser.code == code_default


def test_code_parser_get_tree():
    """Test the __get_tree method of the CodeParser class."""
    parser = CodeParser(code_default)
    tree = parser.get_tree()
    assert isinstance(tree, ast.AST)


def test_code_parser_syntax_error():
    """Test the __get_tree method raises the CodeSyntaxError when given incorrect syntax."""
    code_syntax_error = "zzz import os"

    parser = CodeParser(code_syntax_error)
    with pytest.raises(CodeSyntaxError):
        parser.get_tree()


def test_component_init():
    """Test the initialization of the Component class."""
    component = BaseComponent(_code=code_default, _function_entrypoint_name="build")
    assert component._code == code_default
    assert component._function_entrypoint_name == "build"


def test_component_get_code_tree():
    """Test the get_code_tree method of the Component class."""
    component = BaseComponent(_code=code_default, _function_entrypoint_name="build")
    tree = component.get_code_tree(component._code)
    assert "imports" in tree


def test_component_code_null_error():
    """Test the get_function method raises the ComponentCodeNullError when the code is empty."""
    component = BaseComponent(_code="", _function_entrypoint_name="")
    with pytest.raises(ComponentCodeNullError):
        component.get_function()


def test_custom_component_init():
    """Test the initialization of the CustomComponent class."""
    function_entrypoint_name = "build"

    custom_component = CustomComponent(_code=code_default, _function_entrypoint_name=function_entrypoint_name)
    assert custom_component._code == code_default
    assert custom_component._function_entrypoint_name == function_entrypoint_name


def test_custom_component_build_template_config():
    """Test the build_template_config property of the CustomComponent class."""
    custom_component = CustomComponent(_code=code_default, _function_entrypoint_name="build")
    config = custom_component.build_template_config()
    assert isinstance(config, dict)


def test_custom_component_get_function():
    """Test the get_function property of the CustomComponent class."""
    custom_component = CustomComponent(_code="def build(): pass", _function_entrypoint_name="build")
    my_function = custom_component.get_function()
    assert isinstance(my_function, types.FunctionType)


def test_code_parser_parse_imports_import():
    """Test the parse_imports method of the CodeParser class with an import statement."""
    parser = CodeParser(code_default)
    tree = parser.get_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            parser.parse_imports(node)
    assert "requests" in parser.data["imports"]


def test_code_parser_parse_imports_importfrom():
    """Test the parse_imports method of the CodeParser class with an import from statement."""
    parser = CodeParser("from os import path")
    tree = parser.get_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            parser.parse_imports(node)
    assert ("os", "path") in parser.data["imports"]


def test_code_parser_parse_functions():
    """Test the parse_functions method of the CodeParser class."""
    parser = CodeParser("def test(): pass")
    tree = parser.get_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            parser.parse_functions(node)
    assert len(parser.data["functions"]) == 1
    assert parser.data["functions"][0]["name"] == "test"


def test_code_parser_parse_classes():
    """Test the parse_classes method of the CodeParser class."""
    parser = CodeParser("from langflow.custom import Component\n\nclass Test(Component): pass")
    tree = parser.get_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            parser.parse_classes(node)
    assert len(parser.data["classes"]) == 1
    assert parser.data["classes"][0]["name"] == "Test"


def test_code_parser_parse_classes_raises():
    """Test the parse_classes method of the CodeParser class."""
    parser = CodeParser("class Test: pass")
    tree = parser.get_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            with pytest.raises(TypeError):
                parser.parse_classes(node)


def test_code_parser_parse_global_vars():
    """Test the parse_global_vars method of the CodeParser class."""
    parser = CodeParser("x = 1")
    tree = parser.get_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            parser.parse_global_vars(node)
    assert len(parser.data["global_vars"]) == 1
    assert parser.data["global_vars"][0]["targets"] == ["x"]


def test_component_get_function_valid():
    """Test the get_function method of the Component class with valid code and function_entrypoint_name."""
    component = BaseComponent(_code="def build(): pass", _function_entrypoint_name="build")
    my_function = component.get_function()
    assert callable(my_function)


def test_custom_component_get_function_entrypoint_args():
    """Test the get_function_entrypoint_args property of the CustomComponent class."""
    custom_component = CustomComponent(_code=code_default, _function_entrypoint_name="build")
    args = custom_component.get_function_entrypoint_args
    assert len(args) == 3
    assert args[0]["name"] == "self"
    assert args[1]["name"] == "url"
    assert args[2]["name"] == "llm"


def test_custom_component_get_function_entrypoint_return_type():
    """Test the get_function_entrypoint_return_type property of the CustomComponent class."""
    custom_component = CustomComponent(_code=code_default, _function_entrypoint_name="build")
    return_type = custom_component._get_function_entrypoint_return_type
    assert return_type == [Document]


def test_custom_component_get_main_class_name():
    """Test the get_main_class_name property of the CustomComponent class."""
    custom_component = CustomComponent(_code=code_default, _function_entrypoint_name="build")
    class_name = custom_component.get_main_class_name
    assert class_name == "YourComponent"


def test_custom_component_get_function_valid():
    """Test the get_function property of the CustomComponent class with valid code and function_entrypoint_name."""
    custom_component = CustomComponent(_code="def build(): pass", _function_entrypoint_name="build")
    my_function = custom_component.get_function
    assert callable(my_function)


def test_code_parser_parse_arg_no_annotation():
    """Test the parse_arg method of the CodeParser class without an annotation."""
    parser = CodeParser("")
    arg = ast.arg(arg="x", annotation=None)
    result = parser.parse_arg(arg, None)
    assert result["name"] == "x"
    assert "type" not in result


def test_code_parser_parse_arg_with_annotation():
    """Test the parse_arg method of the CodeParser class with an annotation."""
    parser = CodeParser("")
    arg = ast.arg(arg="x", annotation=ast.Name(id="int", ctx=ast.Load()))
    result = parser.parse_arg(arg, None)
    assert result["name"] == "x"
    assert result["type"] == "int"


def test_code_parser_parse_callable_details_no_args():
    """Test the parse_callable_details method of the CodeParser class with a function with no arguments."""
    parser = CodeParser("")
    node = ast.FunctionDef(
        name="test",
        args=ast.arguments(args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=[],
        decorator_list=[],
        returns=None,
    )
    result = parser.parse_callable_details(node)
    assert result["name"] == "test"
    assert len(result["args"]) == 0


def test_code_parser_parse_assign():
    """Test the parse_assign method of the CodeParser class."""
    parser = CodeParser("")
    stmt = ast.Assign(targets=[ast.Name(id="x", ctx=ast.Store())], value=ast.Num(n=1))
    result = parser.parse_assign(stmt)
    assert result["name"] == "x"
    assert result["value"] == "1"


def test_code_parser_parse_ann_assign():
    """Test the parse_ann_assign method of the CodeParser class."""
    parser = CodeParser("")
    stmt = ast.AnnAssign(
        target=ast.Name(id="x", ctx=ast.Store()),
        annotation=ast.Name(id="int", ctx=ast.Load()),
        value=ast.Num(n=1),
        simple=1,
    )
    result = parser.parse_ann_assign(stmt)
    assert result["name"] == "x"
    assert result["value"] == "1"
    assert result["annotation"] == "int"


def test_code_parser_parse_function_def_not_init():
    """Test the parse_function_def method of the CodeParser class with a function that is not __init__."""
    parser = CodeParser("")
    stmt = ast.FunctionDef(
        name="test",
        args=ast.arguments(args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=[],
        decorator_list=[],
        returns=None,
    )
    result, is_init = parser.parse_function_def(stmt)
    assert result["name"] == "test"
    assert not is_init


def test_code_parser_parse_function_def_init():
    """Test the parse_function_def method of the CodeParser class with an __init__ function."""
    parser = CodeParser("")
    stmt = ast.FunctionDef(
        name="__init__",
        args=ast.arguments(args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=[],
        decorator_list=[],
        returns=None,
    )
    result, is_init = parser.parse_function_def(stmt)
    assert result["name"] == "__init__"
    assert is_init


def test_component_get_code_tree_syntax_error():
    """Test the get_code_tree method of the Component class raises the CodeSyntaxError when given incorrect syntax."""
    component = BaseComponent(_code="import os as", _function_entrypoint_name="build")
    with pytest.raises(CodeSyntaxError):
        component.get_code_tree(component._code)


def test_custom_component_class_template_validation_no_code():
    """Test CustomComponent._class_template_validation raises the HTTPException when the code is None."""
    custom_component = CustomComponent(_code=None, _function_entrypoint_name="build")
    with pytest.raises(TypeError):
        custom_component.get_function()


def test_custom_component_get_code_tree_syntax_error():
    """Test CustomComponent.get_code_tree raises the CodeSyntaxError when given incorrect syntax."""
    custom_component = CustomComponent(_code="import os as", _function_entrypoint_name="build")
    with pytest.raises(CodeSyntaxError):
        custom_component.get_code_tree(custom_component._code)


def test_custom_component_get_function_entrypoint_args_no_args():
    """Test CustomComponent.get_function_entrypoint_args with a build method with no arguments."""
    my_code = """
from langflow.custom import CustomComponent
class MyMainClass(CustomComponent):
    def build():
        pass"""

    custom_component = CustomComponent(_code=my_code, _function_entrypoint_name="build")
    args = custom_component.get_function_entrypoint_args
    assert len(args) == 0


def test_custom_component_get_function_entrypoint_return_type_no_return_type():
    """Test CustomComponent.get_function_entrypoint_return_type with a build method with no return type."""
    my_code = """
from langflow.custom import CustomComponent
class MyClass(CustomComponent):
    def build():
        pass"""

    custom_component = CustomComponent(_code=my_code, _function_entrypoint_name="build")
    return_type = custom_component._get_function_entrypoint_return_type
    assert return_type == []


def test_custom_component_get_main_class_name_no_main_class():
    """Test the get_main_class_name property of the CustomComponent class when there is no main class."""
    my_code = """
def build():
    pass"""

    custom_component = CustomComponent(_code=my_code, _function_entrypoint_name="build")
    class_name = custom_component.get_main_class_name
    assert class_name == ""


def test_custom_component_build_not_implemented():
    """Test the build method of the CustomComponent class raises the NotImplementedError."""
    custom_component = CustomComponent(_code="def build(): pass", _function_entrypoint_name="build")
    with pytest.raises(NotImplementedError):
        custom_component.build()


def test_build_config_no_code():
    component = CustomComponent(_code=None)

    assert component.get_function_entrypoint_args == []
    assert component._get_function_entrypoint_return_type == []


@pytest.fixture
def component():
    return CustomComponent(
        field_config={
            "fields": {
                "llm": {"type": "str"},
                "url": {"type": "str"},
                "year": {"type": "int"},
            }
        },
    )


def test_build_config_return_type(component):
    config = component.build_config()
    assert isinstance(config, dict)


def test_build_config_has_fields(component):
    config = component.build_config()
    assert "fields" in config


def test_build_config_fields_dict(component):
    config = component.build_config()
    assert isinstance(config["fields"], dict)


def test_build_config_field_keys(component):
    config = component.build_config()
    assert all(isinstance(key, str) for key in config["fields"])


def test_build_config_field_values_dict(component):
    config = component.build_config()
    assert all(isinstance(value, dict) for value in config["fields"].values())


def test_build_config_field_value_keys(component):
    config = component.build_config()
    field_values = config["fields"].values()
    assert all("type" in value for value in field_values)


def test_custom_component_multiple_outputs(code_component_with_multiple_outputs):
    frontnd_node_dict, _ = build_custom_component_template(code_component_with_multiple_outputs)
    assert frontnd_node_dict["outputs"][0]["types"] == ["Text"]


def test_custom_component_subclass_from_lctoolcomponent():
    # Import LCToolComponent and create a subclass
    code = dedent("""
    from lfx.base.langchain_utilities.model import LCToolComponent
    from langchain_core.tools import Tool
    class MyComponent(LCToolComponent):
        name: str = "MyComponent"
        description: str = "MyComponent"

        def build_tool(self) -> Tool:
            return Tool(name="MyTool", description="MyTool")

        def run_model(self)-> Data:
            return Data(data="Hello World")
    """)
    component = Component(_code=code)
    frontend_node, _ = build_custom_component_template(component)
    assert "outputs" in frontend_node
    assert frontend_node["outputs"][0]["types"] != []
    assert frontend_node["outputs"][1]["types"] != []
