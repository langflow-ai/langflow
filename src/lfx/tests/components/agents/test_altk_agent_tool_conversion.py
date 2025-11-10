from langchain_core.tools import BaseTool, Tool
from lfx.components.agents.altk_tool_wrappers import PreToolValidationWrapper
from typing import List, Optional


class MockBasicTool(BaseTool):
    name: str = "test_tool"
    description: str = "A test tool"
    
    def _run(self, query: str):
        return f"Running with {query}"

    def _arun(self, query: str):
        raise NotImplementedError("async not implemented")


from pydantic import BaseModel, Field

class UrlSchema(BaseModel):
    """Schema for the fetch_content tool's parameters."""
    urls: Optional[List[str]] = Field(
        default=None,
        description="Enter one or more URLs to crawl recursively, by clicking the '+' button."
    )

class MockToolWithSchema(BaseTool):
    name: str = "fetch_content"
    description: str = "Fetch content from one or more web pages, following links recursively."
    args_schema: type[BaseModel] = UrlSchema

    def _run(self, urls: Optional[List[str]] = None):
        return "Fetched content"

    def _arun(self, urls: Optional[List[str]] = None):
        raise NotImplementedError("async not implemented")


def test_basic_tool_conversion():
    """Test conversion of a basic tool without schema"""
    tool = MockBasicTool()
    result = PreToolValidationWrapper.convert_langchain_tools_to_sparc_tool_specs_format([tool])
    
    assert len(result) == 1
    tool_spec = result[0]
    assert tool_spec["type"] == "function"
    assert tool_spec["function"]["name"] == "test_tool"
    assert tool_spec["function"]["description"] == "A test tool"
    assert tool_spec["function"]["parameters"] == {
        "type": "object",
        "properties": {},
        "required": []
    }


def test_tool_with_list_parameter():
    """Test conversion of a tool with list parameter type"""
    tool = MockToolWithSchema()
    
    # First validate that the tool has the correct schema before conversion
    assert hasattr(tool, 'args_schema'), "Tool should have args_schema"
    schema_model = tool.args_schema
    assert issubclass(schema_model, BaseModel), "Schema should be a Pydantic model"
    
    # Check the schema field
    schema_fields = schema_model.__fields__
    assert 'urls' in schema_fields, "Schema should have urls field"
    urls_field = schema_fields['urls']
    
    # In Pydantic models, the field type is stored differently
    assert urls_field.type_ == List[str], "urls should be List[str]"
    assert urls_field.field_info.description == "Enter one or more URLs to crawl recursively, by clicking the '+' button."
    assert not urls_field.required, "urls field should be optional"
    
    # Now test the conversion
    result = PreToolValidationWrapper.convert_langchain_tools_to_sparc_tool_specs_format([tool])
    
    assert len(result) == 1
    tool_spec = result[0]
    
    # Check basic structure
    assert tool_spec["type"] == "function", "Incorrect type"
    assert tool_spec["function"]["name"] == "fetch_content", "Incorrect name"
    assert tool_spec["function"]["description"] == "Fetch content from one or more web pages, following links recursively.", "Incorrect description"
    
    # Check parameters structure
    params = tool_spec["function"]["parameters"]
    assert params["type"] == "object", "Parameters should be an object"
    assert "properties" in params, "Parameters should have properties"
    assert isinstance(params["properties"], dict), "Properties should be a dictionary"
    
    # Check the urls parameter specifically
    assert "urls" in params["properties"], "urls parameter is missing"
    urls_spec = params["properties"]["urls"]
    print("Generated URLs spec:", urls_spec)  # Debug print
    assert urls_spec["type"] == "array", "urls type should be array"
    assert urls_spec["description"] == "Enter one or more URLs to crawl recursively, by clicking the '+' button.", "Incorrect urls description"
    
    # Since urls is optional, it should not be in required list
    assert "required" in params, "Parameters should have required field"
    assert isinstance(params["required"], list), "Required should be a list"
    assert "urls" not in params["required"], "urls should not be in required list"


def test_multiple_tools_conversion():
    """Test conversion of multiple tools at once"""
    tools = [MockBasicTool(), MockToolWithSchema()]
    result = PreToolValidationWrapper.convert_langchain_tools_to_sparc_tool_specs_format(tools)
    
    assert len(result) == 2
    
    # Check first tool (basic)
    basic_spec = result[0]
    assert basic_spec["function"]["name"] == "test_tool"
    
    # Check second tool (with schema)
    schema_spec = result[1]
    assert schema_spec["function"]["name"] == "fetch_content"
    assert "urls" in schema_spec["function"]["parameters"]["properties"]
    assert schema_spec["function"]["parameters"]["properties"]["urls"]["type"] == "array"


class BrokenTool(BaseTool):
    name: str = "broken_tool"
    description: str = "A tool that will cause conversion errors"
    
    @property
    def args_schema(self):
        raise Exception("Schema error")
    
    def _run(self):
        pass


def test_error_handling():
    """Test handling of errors during conversion"""
    tool = BrokenTool()
    result = PreToolValidationWrapper.convert_langchain_tools_to_sparc_tool_specs_format([tool])
    
    assert len(result) == 1
    tool_spec = result[0]
    
    # Should create minimal spec when error occurs
    assert tool_spec["type"] == "function"
    assert tool_spec["function"]["name"] == "broken_tool"
    assert "parameters" in tool_spec["function"]
    assert tool_spec["function"]["parameters"] == {
        "type": "object",
        "properties": {},
        "required": []
    }