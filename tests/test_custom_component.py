import ast
import pytest
import types

from fastapi import HTTPException
from langflow.interface.custom.base import CustomComponent
from langflow.interface.custom.component import (
    Component,
    ComponentCodeNullError,
    ComponentFunctionEntrypointNameNullError,
)
from langflow.interface.custom.code_parser import CodeParser, CodeSyntaxError


code_default = """
from langflow import Prompt
from langflow.interface.custom.custom_component import CustomComponent

from langchain.llms.base import BaseLLM
from langchain.chains import LLMChain
from langchain import PromptTemplate
from langchain.schema import Document

import requests

class YourComponent(CustomComponent):
    langflow_display_name: str = "Your Component"
    langflow_description: str = "Your description"
    langflow_field_config = { "url": { "multiline": True, "required": True } }

    def build(self, url: str, llm: BaseLLM, template: Prompt) -> Document:
        response = requests.get(url)
        prompt = PromptTemplate.from_template(template)
        chain = LLMChain(llm=llm, prompt=prompt)
        result = chain.run(response.text[:300])
        return Document(page_content=str(result))
"""


def test_code_parser_init():
    """
    Test the initialization of the CodeParser class.
    """
    parser = CodeParser(code_default)
    assert parser.code == code_default


def test_code_parser_get_tree():
    """
    Test the __get_tree method of the CodeParser class.
    """
    parser = CodeParser(code_default)
    tree = parser._CodeParser__get_tree()
    assert isinstance(tree, ast.AST)


def test_code_parser_syntax_error():
    """
    Test the __get_tree method raises the CodeSyntaxError when given incorrect syntax.
    """
    code_syntax_error = "zzz import os"

    parser = CodeParser(code_syntax_error)
    with pytest.raises(CodeSyntaxError):
        parser._CodeParser__get_tree()


def test_component_init():
    """
    Test the initialization of the Component class.
    """
    component = Component(code=code_default, function_entrypoint_name="build")
    assert component.code == code_default
    assert component.function_entrypoint_name == "build"


def test_component_get_code_tree():
    """
    Test the get_code_tree method of the Component class.
    """
    component = Component(code=code_default, function_entrypoint_name="build")
    tree = component.get_code_tree(component.code)
    assert "imports" in tree


def test_component_code_null_error():
    """
    Test the get_function method raises the ComponentCodeNullError when the code is empty.
    """
    component = Component(code="", function_entrypoint_name="")
    with pytest.raises(ComponentCodeNullError):
        component.get_function()


def test_component_function_entrypoint_name_null_error():
    """
    Test the get_function method raises the ComponentFunctionEntrypointNameNullError
    when the function_entrypoint_name is empty.
    """
    component = Component(code=code_default, function_entrypoint_name="")
    with pytest.raises(ComponentFunctionEntrypointNameNullError):
        component.get_function()


def test_custom_component_init():
    """
    Test the initialization of the CustomComponent class.
    """
    function_entrypoint_name = "build"

    custom_component = CustomComponent(
        code=code_default, function_entrypoint_name=function_entrypoint_name
    )
    assert custom_component.code == code_default
    assert custom_component.function_entrypoint_name == function_entrypoint_name


def test_custom_component_build_template_config():
    """
    Test the build_template_config property of the CustomComponent class.
    """
    custom_component = CustomComponent(
        code=code_default, function_entrypoint_name="build"
    )
    config = custom_component.build_template_config
    assert isinstance(config, dict)


def test_custom_component_get_function():
    """
    Test the get_function property of the CustomComponent class.
    """
    custom_component = CustomComponent(
        code="def build(): pass", function_entrypoint_name="build"
    )
    my_function = custom_component.get_function
    assert isinstance(my_function, types.FunctionType)


def test_code_parser_parse_imports_import():
    """
    Test the parse_imports method of the CodeParser class with an import statement.
    """
    parser = CodeParser(code_default)
    tree = parser._CodeParser__get_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            parser.parse_imports(node)
    assert "requests" in parser.data["imports"]


def test_code_parser_parse_imports_importfrom():
    """
    Test the parse_imports method of the CodeParser class with an import from statement.
    """
    parser = CodeParser("from os import path")
    tree = parser._CodeParser__get_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            parser.parse_imports(node)
    assert ("os", "path") in parser.data["imports"]


def test_code_parser_parse_functions():
    """
    Test the parse_functions method of the CodeParser class.
    """
    parser = CodeParser("def test(): pass")
    tree = parser._CodeParser__get_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            parser.parse_functions(node)
    assert len(parser.data["functions"]) == 1
    assert parser.data["functions"][0]["name"] == "test"


def test_code_parser_parse_classes():
    """
    Test the parse_classes method of the CodeParser class.
    """
    parser = CodeParser("class Test: pass")
    tree = parser._CodeParser__get_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            parser.parse_classes(node)
    assert len(parser.data["classes"]) == 1
    assert parser.data["classes"][0]["name"] == "Test"


def test_code_parser_parse_global_vars():
    """
    Test the parse_global_vars method of the CodeParser class.
    """
    parser = CodeParser("x = 1")
    tree = parser._CodeParser__get_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            parser.parse_global_vars(node)
    assert len(parser.data["global_vars"]) == 1
    assert parser.data["global_vars"][0]["targets"] == ["x"]


def test_component_get_function_valid():
    """
    Test the get_function method of the Component class with valid code and function_entrypoint_name.
    """
    component = Component(code="def build(): pass", function_entrypoint_name="build")
    function = component.get_function()
    assert callable(function)


def test_custom_component_get_function_entrypoint_args():
    """
    Test the get_function_entrypoint_args property of the CustomComponent class.
    """
    custom_component = CustomComponent(
        code=code_default, function_entrypoint_name="build"
    )
    args = custom_component.get_function_entrypoint_args
    assert len(args) == 4
    assert args[0]["name"] == "self"
    assert args[1]["name"] == "url"
    assert args[2]["name"] == "llm"


def test_custom_component_get_function_entrypoint_return_type():
    """
    Test the get_function_entrypoint_return_type property of the CustomComponent class.
    """
    custom_component = CustomComponent(
        code=code_default, function_entrypoint_name="build"
    )
    return_type = custom_component.get_function_entrypoint_return_type
    assert return_type == "Document"


def test_custom_component_get_main_class_name():
    """
    Test the get_main_class_name property of the CustomComponent class.
    """
    custom_component = CustomComponent(
        code=code_default, function_entrypoint_name="build"
    )
    class_name = custom_component.get_main_class_name
    assert class_name == "YourComponent"


def test_custom_component_get_function_valid():
    """
    Test the get_function property of the CustomComponent class with valid code and function_entrypoint_name.
    """
    custom_component = CustomComponent(
        code="def build(): pass", function_entrypoint_name="build"
    )
    my_function = custom_component.get_function
    assert callable(my_function)


def test_code_parser_parse_arg_no_annotation():
    """
    Test the parse_arg method of the CodeParser class without an annotation.
    """
    parser = CodeParser("")
    arg = ast.arg(arg="x", annotation=None)
    result = parser.parse_arg(arg, None)
    assert result["name"] == "x"
    assert "type" not in result


def test_code_parser_parse_arg_with_annotation():
    """
    Test the parse_arg method of the CodeParser class with an annotation.
    """
    parser = CodeParser("")
    arg = ast.arg(arg="x", annotation=ast.Name(id="int", ctx=ast.Load()))
    result = parser.parse_arg(arg, None)
    assert result["name"] == "x"
    assert result["type"] == "int"


def test_code_parser_parse_callable_details_no_args():
    """
    Test the parse_callable_details method of the CodeParser class with a function with no arguments.
    """
    parser = CodeParser("")
    node = ast.FunctionDef(
        name="test",
        args=ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        ),
        body=[],
        decorator_list=[],
        returns=None,
    )
    result = parser.parse_callable_details(node)
    assert result["name"] == "test"
    assert len(result["args"]) == 0


def test_code_parser_parse_assign():
    """
    Test the parse_assign method of the CodeParser class.
    """
    parser = CodeParser("")
    stmt = ast.Assign(targets=[ast.Name(id="x", ctx=ast.Store())], value=ast.Num(n=1))
    result = parser.parse_assign(stmt)
    assert result["name"] == "x"
    assert result["value"] == "1"


def test_code_parser_parse_ann_assign():
    """
    Test the parse_ann_assign method of the CodeParser class.
    """
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
    """
    Test the parse_function_def method of the CodeParser class with a function that is not __init__.
    """
    parser = CodeParser("")
    stmt = ast.FunctionDef(
        name="test",
        args=ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        ),
        body=[],
        decorator_list=[],
        returns=None,
    )
    result, is_init = parser.parse_function_def(stmt)
    assert result["name"] == "test"
    assert not is_init


def test_code_parser_parse_function_def_init():
    """
    Test the parse_function_def method of the CodeParser class with an __init__ function.
    """
    parser = CodeParser("")
    stmt = ast.FunctionDef(
        name="__init__",
        args=ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        ),
        body=[],
        decorator_list=[],
        returns=None,
    )
    result, is_init = parser.parse_function_def(stmt)
    assert result["name"] == "__init__"
    assert is_init


def test_component_get_code_tree_syntax_error():
    """
    Test the get_code_tree method of the Component class
    raises the CodeSyntaxError when given incorrect syntax.
    """
    component = Component(code="import os as", function_entrypoint_name="build")
    with pytest.raises(CodeSyntaxError):
        component.get_code_tree(component.code)


def test_custom_component_class_template_validation_no_code():
    """
    Test the _class_template_validation method of the CustomComponent class
    raises the HTTPException when the code is None.
    """
    custom_component = CustomComponent(code=None, function_entrypoint_name="build")
    with pytest.raises(HTTPException):
        custom_component._class_template_validation(custom_component.code)


def test_custom_component_get_code_tree_syntax_error():
    """
    Test the get_code_tree method of the CustomComponent class raises the CodeSyntaxError when given incorrect syntax.
    """
    custom_component = CustomComponent(
        code="import os as", function_entrypoint_name="build"
    )
    with pytest.raises(CodeSyntaxError):
        custom_component.get_code_tree(custom_component.code)


def test_custom_component_get_function_entrypoint_args_no_args():
    """
    Test the get_function_entrypoint_args property of the CustomComponent class with a build method with no arguments.
    """
    my_code = """
class MyMainClass(CustomComponent):
    def build():
        pass"""

    custom_component = CustomComponent(code=my_code, function_entrypoint_name="build")
    args = custom_component.get_function_entrypoint_args
    assert len(args) == 0


def test_custom_component_get_function_entrypoint_return_type_no_return_type():
    """
    Test the get_function_entrypoint_return_type property of the
    CustomComponent class with a build method with no return type.
    """
    my_code = """
class MyClass(CustomComponent):
    def build():
        pass"""

    custom_component = CustomComponent(code=my_code, function_entrypoint_name="build")
    return_type = custom_component.get_function_entrypoint_return_type
    assert return_type is None


def test_custom_component_get_main_class_name_no_main_class():
    """
    Test the get_main_class_name property of the CustomComponent class when there is no main class.
    """
    my_code = """
def build():
    pass"""

    custom_component = CustomComponent(code=my_code, function_entrypoint_name="build")
    class_name = custom_component.get_main_class_name
    assert class_name == ""


def test_custom_component_build_not_implemented():
    """
    Test the build method of the CustomComponent class raises the NotImplementedError.
    """
    custom_component = CustomComponent(
        code="def build(): pass", function_entrypoint_name="build"
    )
    with pytest.raises(NotImplementedError):
        custom_component.build()


# -------------------------------------------------------
# @pytest.fixture
# def custom_chain():
#     return '''
# from __future__ import annotations
# from typing import Any, Dict, List, Optional

# from pydantic import Extra

# from langchain.schema import BaseLanguageModel, Document
# from langchain.callbacks.manager import (
#     AsyncCallbackManagerForChainRun,
#     CallbackManagerForChainRun,
# )
# from langchain.chains.base import Chain
# from langchain.prompts import StringPromptTemplate
# from langflow.interface.custom.base import CustomComponent

# class MyCustomChain(Chain):
#     """
#     An example of a custom chain.
#     """

# from typing import Any, Dict, List, Optional

# from pydantic import Extra

# from langchain.schema import BaseLanguageModel, Document
# from langchain.callbacks.manager import (
#     AsyncCallbackManagerForChainRun,
#     CallbackManagerForChainRun,
# )
# from langchain.chains.base import Chain
# from langchain.prompts import StringPromptTemplate
# from langflow.interface.custom.base import CustomComponent

# class MyCustomChain(Chain):
#     """
#     An example of a custom chain.
#     """

#     prompt: StringPromptTemplate
#     """Prompt object to use."""
#     llm: BaseLanguageModel
#     output_key: str = "text"  #: :meta private:

#     class Config:
#         """Configuration for this pydantic object."""

#         extra = Extra.forbid
#         arbitrary_types_allowed = True

#     @property
#     def input_keys(self) -> List[str]:
#         """Will be whatever keys the prompt expects.

#         :meta private:
#         """
#         return self.prompt.input_variables

#     @property
#     def output_keys(self) -> List[str]:
#         """Will always return text key.

#         :meta private:
#         """
#         return [self.output_key]

#     def _call(
#         self,
#         inputs: Dict[str, Any],
#         run_manager: Optional[CallbackManagerForChainRun] = None,
#     ) -> Dict[str, str]:
#         # Your custom chain logic goes here
#         # This is just an example that mimics LLMChain
#         prompt_value = self.prompt.format_prompt(**inputs)

#         # Whenever you call a language model, or another chain, you should pass
#         # a callback manager to it. This allows the inner run to be tracked by
#         # any callbacks that are registered on the outer run.
#         # You can always obtain a callback manager for this by calling
#         # `run_manager.get_child()` as shown below.
#         response = self.llm.generate_prompt(
#             [prompt_value],
#             callbacks=run_manager.get_child() if run_manager else None,
#         )

#         # If you want to log something about this run, you can do so by calling
#         # methods on the `run_manager`, as shown below. This will trigger any
#         # callbacks that are registered for that event.
#         if run_manager:
#             run_manager.on_text("Log something about this run")

#         return {self.output_key: response.generations[0][0].text}

#     async def _acall(
#         self,
#         inputs: Dict[str, Any],
#         run_manager: Optional[AsyncCallbackManagerForChainRun] = None,
#     ) -> Dict[str, str]:
#         # Your custom chain logic goes here
#         # This is just an example that mimics LLMChain
#         prompt_value = self.prompt.format_prompt(**inputs)

#         # Whenever you call a language model, or another chain, you should pass
#         # a callback manager to it. This allows the inner run to be tracked by
#         # any callbacks that are registered on the outer run.
#         # You can always obtain a callback manager for this by calling
#         # `run_manager.get_child()` as shown below.
#         response = await self.llm.agenerate_prompt(
#             [prompt_value],
#             callbacks=run_manager.get_child() if run_manager else None,
#         )

#         # If you want to log something about this run, you can do so by calling
#         # methods on the `run_manager`, as shown below. This will trigger any
#         # callbacks that are registered for that event.
#         if run_manager:
#             await run_manager.on_text("Log something about this run")

#         return {self.output_key: response.generations[0][0].text}

#     @property
#     def _chain_type(self) -> str:
#         return "my_custom_chain"

# class CustomChain(CustomComponent):
#     display_name: str = "Custom Chain"
#     field_config = {
#         "prompt": {"field_type": "prompt"},
#         "llm": {"field_type": "BaseLanguageModel"},
#     }

#     def build(self, prompt, llm, input: str) -> Document:
#         chain = MyCustomChain(prompt=prompt, llm=llm)
#         return chain(input)
# '''


# @pytest.fixture
# def data_processing():
#     return """
# import pandas as pd
# from langchain.schema import Document
# from langflow.interface.custom.base import CustomComponent

# class CSVLoaderComponent(CustomComponent):
#     display_name: str = "CSV Loader"
#     field_config = {
#         "filename": {"field_type": "str", "required": True},
#         "column_name": {"field_type": "str", "required": True},
#     }

#     def build(self, filename: str, column_name: str) -> Document:
#         # Load the CSV file
#         df = pd.read_csv(filename)

#         # Verify the column exists
#         if column_name not in df.columns:
#             raise ValueError(f"Column '{column_name}' not found in the CSV file")

#         # Convert each row of the specified column to a document object
#         documents = []
#         for content in df[column_name]:
#             metadata = {"filename": filename}
#             documents.append(Document(page_content=str(content), metadata=metadata))

#         return documents
# """


# @pytest.fixture
# def filter_docs():
#     return """
# from langchain.schema import Document
# from langflow.interface.custom.base import CustomComponent
# from typing import List

# class DocumentFilterByLengthComponent(CustomComponent):
#     display_name: str = "Document Filter By Length"
#     field_config = {
#         "documents": {"field_type": "Document", "required": True},
#         "max_length": {"field_type": "int", "required": True},
#     }

#     def build(self, documents: List[Document], max_length: int) -> List[Document]:
#         # Filter the documents by length
#         filtered_documents = [doc for doc in documents if len(doc.page_content) <= max_length]

#         return filtered_documents
# """


# @pytest.fixture
# def get_request():
#     return """
# import requests
# from typing import Dict, Union
# from langchain.schema import Document
# from langflow.interface.custom.base import CustomComponent

# class GetRequestComponent(CustomComponent):
#     display_name: str = "GET Request"
#     field_config = {
#         "url": {"field_type": "str", "required": True},
#     }

#     def build(self, url: str) -> Document:
#         # Send a GET request to the URL
#         response = requests.get(url)

#         # Raise an exception if the request was not successful
#         if response.status_code != 200:
#             raise ValueError(f"GET request failed: {response.status_code} status code")

#         # Create a document with the response text and the URL as metadata
#         document = Document(page_content=response.text, metadata={"url": url})

#         return document
# """


# @pytest.fixture
# def post_request():
#     return """
# import requests
# from typing import Dict, Union
# from langchain.schema import Document
# from langflow.interface.custom.base import CustomComponent

# class PostRequestComponent(CustomComponent):
#     display_name: str = "POST Request"
#     field_config = {
#         "url": {"field_type": "str", "required": True},
#         "data": {"field_type": "dict", "required": True},
#     }

#     def build(self, url: str, data: Dict[str, Union[str, int]]) -> Document:
#         # Send a POST request to the URL
#         response = requests.post(url, data=data)

#         # Raise an exception if the request was not successful
#         if response.status_code != 200:
#             raise ValueError(f"POST request failed: {response.status_code} status code")

#         # Create a document with the response text and the URL and data as metadata
#         document = Document(page_content=response.text, metadata={"url": url, "data": data})

#         return document
# """


# @pytest.fixture
# def code_default():
#     return """
# from langflow import Prompt
# from langflow.interface.custom.custom_component import CustomComponent

# from langchain.llms.base import BaseLLM
# from langchain.chains import LLMChain
# from langchain import PromptTemplate
# from langchain.schema import Document

# import requests

# class YourComponent(CustomComponent):
#     #display_name: str = "Your Component"
#     #description: str = "Your description"
#     #field_config = { "url": { "multiline": True, "required": True } }

#     def build(self, url: str, llm: BaseLLM, template: Prompt) -> Document:
#         response = requests.get(url)
#         prompt = PromptTemplate.from_template(template)
#         chain = LLMChain(llm=llm, prompt=prompt)
#         result = chain.run(response.text[:300])
#         return Document(page_content=str(result))
# """


# @pytest.fixture(params=[
#     'code_default', 'custom_chain', 'data_processing',
#     'filter_docs', 'get_request', 'post_request'])
# def component_code(
#         request, code_default, custom_chain, data_processing,
#         filter_docs, get_request, post_request):
#     return locals()[request.param]


# def test_empty_code_tree(component_code):
#     """
#     Test the situation when the code tree is empty.
#     """
#     cc = CustomComponent(code=component_code)
#     with patch.object(cc, 'get_code_tree') as mocked_get_code_tree:
#         mocked_get_code_tree.return_value = {}
#         assert cc.get_function_entrypoint_args == ''
#         assert cc.get_function_entrypoint_return_type == ''
#         assert cc.get_main_class_name == ''
#         assert cc.build_template_config == {}


# def test_class_template_validation(component_code):
#     """
#     Test the _class_template_validation method.
#     """
#     cc = CustomComponent(code=component_code)
#     assert cc._class_template_validation(component_code) == True
#     with pytest.raises(HTTPException):
#         cc._class_template_validation(None)


# def test_get_code_tree(component_code):
#     """
#     Test the get_code_tree method.
#     """
#     cc = CustomComponent(code=component_code)
#     with patch.object(cc, 'get_code_tree') as mocked_get_code_tree:
#         mocked_get_code_tree.return_value = {'classes': []}
#         assert cc.get_code_tree(component_code) == {'classes': []}


# def test_get_function_entrypoint_args(component_code):
#     """
#     Test the get_function_entrypoint_args method.
#     """
#     cc = CustomComponent(code=component_code)
#     with patch.object(cc, 'get_code_tree') as mocked_get_code_tree:
#         mocked_get_code_tree.return_value = {'classes': []}
#         assert cc.get_function_entrypoint_args == ''


# def test_get_function_entrypoint_return_type(component_code):
#     """
#     Test the get_function_entrypoint_return_type method.
#     """
#     cc = CustomComponent(code=component_code)
#     with patch.object(cc, 'get_code_tree') as mocked_get_code_tree:
#         mocked_get_code_tree.return_value = {'classes': []}
#         assert cc.get_function_entrypoint_return_type == ''


# def test_get_main_class_name(component_code):
#     """
#     Test the get_main_class_name method.
#     """
#     cc = CustomComponent(code=component_code)
#     with patch.object(cc, 'get_code_tree') as mocked_get_code_tree:
#         mocked_get_code_tree.return_value = {'classes': []}
#         assert cc.get_main_class_name == ''


# def test_build_template_config(component_code):
#     """
#     Test the build_template_config method.
#     """
#     cc = CustomComponent(code=component_code)
#     with patch.object(cc, 'get_code_tree') as mocked_get_code_tree:
#         mocked_get_code_tree.return_value = {
#             'classes': [{'name': '', 'attributes': []}]}
#         assert cc.build_template_config == {}


# def test_get_function(component_code):
#     """
#     Test the get_function method.
#     """
#     cc = CustomComponent(code=component_code, function_entrypoint_name='build')
#     assert callable(cc.get_function)


# def test_build(component_code):
#     """
#     Test the build method.
#     """
#     cc = CustomComponent(code=component_code)
#     with pytest.raises(NotImplementedError):
#         cc.build()


# @pytest.mark.parametrize("entrypoint_name", ["build", "non_exist_method"])
# def test_set_non_existing_function_entrypoint_name(component_code, entrypoint_name):
#     """
#     Test setting a non-existing function entrypoint name.
#     """
#     cc = CustomComponent(
#         code=component_code,
#         function_entrypoint_name=entrypoint_name
#     )
#     with pytest.raises(AttributeError):
#         cc.get_function


# @pytest.mark.parametrize("base_class", ["CustomComponent", "NonExistingClass"])
# def test_set_non_existing_base_class(component_code, base_class):
#     """
#     Test setting a non-existing base class.
#     """
#     cc = CustomComponent(code=component_code)
#     cc.code_class_base_inheritance = base_class
#     with pytest.raises(AttributeError):
#         cc.get_main_class_name


# def test_class_with_no_methods(component_code):
#     """
#     Test a component class with no methods.
#     """
#     cc = CustomComponent(code=component_code)
#     with patch.object(cc, 'get_code_tree') as mocked_get_code_tree:
#         mocked_get_code_tree.return_value = {
#             'classes': [
#                 {
#                     'name': 'CustomComponent',
#                     'methods': [],
#                     'bases': ['CustomComponent']
#                 }
#             ]
#         }
#         assert cc.get_function_entrypoint_args == ''
#         assert cc.get_function_entrypoint_return_type == ''


# def test_class_with_no_bases(component_code):
#     """
#     Test a component class with no bases.
#     """
#     cc = CustomComponent(code=component_code)
#     with patch.object(cc, 'get_code_tree') as mocked_get_code_tree:
#         mocked_get_code_tree.return_value = {
#             'classes': [
#                 {
#                     'name': 'CustomComponent',
#                     'methods': [],
#                     'bases': []
#                 }
#             ]
#         }
#         assert cc.get_function_entrypoint_args == ''
#         assert cc.get_function_entrypoint_return_type == ''


# def test_class_with_no_name(component_code):
#     """
#     Test a component class with no name.
#     """
#     cc = CustomComponent(code=component_code)
#     with patch.object(cc, 'get_code_tree') as mocked_get_code_tree:
#         mocked_get_code_tree.return_value = {'classes': [
#             {'name': '', 'methods': [], 'bases': ['CustomComponent']}]}
#         assert cc.get_main_class_name == ''


# @pytest.mark.parametrize("input_code", ["", "not a valid python code"])
# def test_invalid_input_code(input_code):
#     """
#     Test inputting an invalid Python code.
#     """
#     with pytest.raises(SyntaxError):
#         cc = CustomComponent(code=input_code)
