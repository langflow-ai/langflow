from langchain_core.tools import BaseTool
from lfx.base.agents.altk_tool_wrappers import PreToolValidationWrapper
from lfx.log.logger import logger
from pydantic import BaseModel, Field


class CustomSchemaExceptionError(Exception):
    """Custom exception for schema errors."""


class MockBasicTool(BaseTool):
    name: str = "test_tool"
    description: str = "A test tool"

    def _run(self, query: str):
        return f"Running with {query}"

    def _arun(self, query: str):
        error_message = "async not implemented"
        raise NotImplementedError(error_message)


class MockNoParamTool(BaseTool):
    name: str = "no_param_tool"
    description: str = "A tool with no parameters"

    def _run(self):
        return "Running with no params"

    def _arun(self):
        error_message = "async not implemented"
        raise NotImplementedError(error_message)


class UrlSchema(BaseModel):
    """Schema for the fetch_content tool's parameters."""

    urls: list[str] | None = Field(
        default=None, description="Enter one or more URLs to crawl recursively, by clicking the '+' button."
    )


class MockToolWithSchema(BaseTool):
    name: str = "fetch_content"
    description: str = "Fetch content from one or more web pages, following links recursively."
    args_schema: type[BaseModel] = UrlSchema

    def _run(self, _urls: list[str] | None = None):
        return "Fetched content"

    def _arun(self, urls: list[str] | None = None):
        error_message = "async not implemented"
        raise NotImplementedError(error_message)


def test_basic_tool_conversion():
    """Test conversion of a basic tool without explicit schema but with method parameters."""
    tool = MockBasicTool()
    result = PreToolValidationWrapper.convert_langchain_tools_to_sparc_tool_specs_format([tool])

    assert len(result) == 1
    tool_spec = result[0]
    assert tool_spec["type"] == "function"
    assert tool_spec["function"]["name"] == "test_tool"
    assert tool_spec["function"]["description"] == "A test tool"
    # LangChain automatically extracts parameters from _run method signature
    assert tool_spec["function"]["parameters"] == {
        "type": "object",
        "properties": {"query": {"type": "string", "description": ""}},
        "required": [],
    }


def test_no_param_tool_conversion():
    """Test conversion of a tool with no parameters."""
    tool = MockNoParamTool()
    result = PreToolValidationWrapper.convert_langchain_tools_to_sparc_tool_specs_format([tool])

    assert len(result) == 1
    tool_spec = result[0]
    assert tool_spec["type"] == "function"
    assert tool_spec["function"]["name"] == "no_param_tool"
    assert tool_spec["function"]["description"] == "A tool with no parameters"
    # Tool with no parameters should have empty properties
    assert tool_spec["function"]["parameters"] == {"type": "object", "properties": {}, "required": []}


def test_tool_with_list_parameter():
    """Test conversion of a tool with list parameter type."""
    tool = MockToolWithSchema()

    # First validate that the tool has the correct schema before conversion
    assert hasattr(tool, "args_schema"), "Tool should have args_schema"
    schema_model = tool.args_schema
    assert issubclass(schema_model, BaseModel), "Schema should be a Pydantic model"

    # Check the schema field using Pydantic v2 model_fields
    schema_fields = schema_model.model_fields
    assert "urls" in schema_fields, "Schema should have urls field"
    urls_field = schema_fields["urls"]

    # Check that the field is properly configured
    assert not urls_field.is_required(), "urls field should be optional"
    assert urls_field.description == "Enter one or more URLs to crawl recursively, by clicking the '+' button."

    # Now test the conversion
    result = PreToolValidationWrapper.convert_langchain_tools_to_sparc_tool_specs_format([tool])

    assert len(result) == 1
    tool_spec = result[0]

    # Check basic structure
    assert tool_spec["type"] == "function", "Incorrect type"
    assert tool_spec["function"]["name"] == "fetch_content", "Incorrect name"
    assert (
        tool_spec["function"]["description"] == "Fetch content from one or more web pages, following links recursively."
    ), "Incorrect description"

    # Check parameters structure
    params = tool_spec["function"]["parameters"]
    assert params["type"] == "object", "Parameters should be an object"
    assert "properties" in params, "Parameters should have properties"
    assert isinstance(params["properties"], dict), "Properties should be a dictionary"

    # Check the urls parameter specifically
    assert "urls" in params["properties"], "urls parameter is missing"
    urls_spec = params["properties"]["urls"]
    logger.debug("Generated URLs spec: %s", urls_spec)  # Debug print

    # Now it should correctly identify as array type
    assert urls_spec["type"] == "array", "urls type should be array"
    assert urls_spec["description"] == "Enter one or more URLs to crawl recursively, by clicking the '+' button.", (
        "Incorrect urls description"
    )

    # Should have items specification
    assert "items" in urls_spec, "Array should have items specification"
    assert urls_spec["items"]["type"] == "string", "Array items should be strings"

    # Should have default value since it's optional
    assert urls_spec.get("default") is None, "Should have default None value"

    # Since urls is optional, it should not be in required list
    assert "required" in params, "Parameters should have required field"
    assert isinstance(params["required"], list), "Required should be a list"
    assert "urls" not in params["required"], "urls should not be in required list"


def test_multiple_tools_conversion():
    """Test conversion of multiple tools at once."""
    tools = [MockBasicTool(), MockToolWithSchema()]
    result = PreToolValidationWrapper.convert_langchain_tools_to_sparc_tool_specs_format(tools)

    assert len(result) == 2

    # Check first tool (basic)
    basic_spec = result[0]
    assert basic_spec["function"]["name"] == "test_tool"
    # Basic tool should have query parameter as string
    assert "query" in basic_spec["function"]["parameters"]["properties"]
    assert basic_spec["function"]["parameters"]["properties"]["query"]["type"] == "string"

    # Check second tool (with schema)
    schema_spec = result[1]
    assert schema_spec["function"]["name"] == "fetch_content"
    assert "urls" in schema_spec["function"]["parameters"]["properties"]
    # Now correctly identifies as array
    assert schema_spec["function"]["parameters"]["properties"]["urls"]["type"] == "array"
    assert schema_spec["function"]["parameters"]["properties"]["urls"]["items"]["type"] == "string"


class BrokenTool(BaseTool):
    name: str = "broken_tool"
    description: str = "A tool that will cause conversion errors"

    @property
    def args_schema(self):
        error_message = "Schema Error"
        raise CustomSchemaExceptionError(error_message)

    def _run(self):
        pass


def test_error_handling():
    """Test handling of errors during conversion."""
    tool = BrokenTool()
    result = PreToolValidationWrapper.convert_langchain_tools_to_sparc_tool_specs_format([tool])

    assert len(result) == 1
    tool_spec = result[0]

    # Should create minimal spec when error occurs
    assert tool_spec["type"] == "function"
    assert tool_spec["function"]["name"] == "broken_tool"
    assert "parameters" in tool_spec["function"]
    assert tool_spec["function"]["parameters"] == {"type": "object", "properties": {}, "required": []}


def test_complex_schema_conversion():
    """Test conversion of tools with complex parameter schemas."""
    from pydantic import BaseModel, Field

    class ComplexSchema(BaseModel):
        required_str: str = Field(description="A required string parameter")
        optional_int: int | None = Field(default=None, description="An optional integer")
        str_list: list[str] = Field(default_factory=list, description="A list of strings")

    class ComplexTool(BaseTool):
        name: str = "complex_tool"
        description: str = "A tool with complex parameters"
        args_schema: type[BaseModel] = ComplexSchema

        def _run(self, **kwargs):
            logger.debug(f"ComplexTool called with kwargs: {kwargs}")
            return "complex result"

    tool = ComplexTool()
    result = PreToolValidationWrapper.convert_langchain_tools_to_sparc_tool_specs_format([tool])

    assert len(result) == 1
    tool_spec = result[0]

    # Check that all parameters are properly converted
    props = tool_spec["function"]["parameters"]["properties"]

    # Required string parameter
    assert "required_str" in props
    assert props["required_str"]["type"] == "string"
    assert props["required_str"]["description"] == "A required string parameter"

    # Optional integer parameter
    assert "optional_int" in props
    # Should handle the Union[int, None] properly
    assert props["optional_int"]["type"] == "integer"
    assert props["optional_int"]["description"] == "An optional integer"

    # List parameter
    assert "str_list" in props
    assert props["str_list"]["type"] == "array"
    assert props["str_list"]["description"] == "A list of strings"
    assert props["str_list"]["items"]["type"] == "string"

    # Check required fields
    required = tool_spec["function"]["parameters"]["required"]
    assert "required_str" in required
    assert "optional_int" not in required  # Should not be required
    assert "str_list" not in required  # Should not be required
