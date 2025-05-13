import os
import re
from unittest.mock import patch

import openai
import pytest
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_openai import ChatOpenAI
from langflow.components.helpers.structured_output import StructuredOutputComponent
from langflow.helpers.base_model import build_model_from_schema
from langflow.inputs.inputs import TableInput
from pydantic import BaseModel

from tests.base import ComponentTestBaseWithoutClient
from tests.unit.mock_language_model import MockLanguageModel


class TestStructuredOutputComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return StructuredOutputComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "llm": MockLanguageModel(),
            "input_value": "Test input",
            "schema_name": "TestSchema",
            "output_schema": [{"name": "field", "type": "str", "description": "A test field"}],
            "multiple": False,
            "system_prompt": "Test system prompt",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for version-specific files."""

    def test_successful_structured_output_generation_with_patch_with_config(self):
        def mock_get_chat_result(runnable, system_message, input_value, config):  # noqa: ARG001
            class MockBaseModel(BaseModel):
                def model_dump(self, **__):
                    return {"objects": [{"field": "value"}]}

            return MockBaseModel()

        component = StructuredOutputComponent(
            llm=MockLanguageModel(),
            input_value="Test input",
            schema_name="TestSchema",
            output_schema=[{"name": "field", "type": "str", "description": "A test field"}],
            multiple=False,
            system_prompt="Test system prompt",
        )

        with patch("langflow.components.helpers.structured_output.get_chat_result", mock_get_chat_result):
            result = component.build_structured_output_base()
            assert isinstance(result, list)
            assert result == [{"field": "value"}]

    def test_raises_value_error_for_unsupported_language_model(self):
        # Mocking an incompatible language model
        class MockLanguageModel:
            pass

        # Creating an instance of StructuredOutputComponent
        component = StructuredOutputComponent(
            llm=MockLanguageModel(),
            input_value="Test input",
            schema_name="TestSchema",
            output_schema=[{"name": "field", "type": "str", "description": "A test field"}],
            multiple=False,
        )

        with pytest.raises(TypeError, match=re.escape("Language model does not support structured output.")):
            component.build_structured_output()

    def test_correctly_builds_output_model(self):
        # Setup
        component = StructuredOutputComponent()
        schema = [
            {
                "name": "name",
                "display_name": "Name",
                "type": "str",
                "description": "Specify the name of the output field.",
            },
            {
                "name": "description",
                "display_name": "Description",
                "type": "str",
                "description": "Describe the purpose of the output field.",
            },
            {
                "name": "type",
                "display_name": "Type",
                "type": "str",
                "description": (
                    "Indicate the data type of the output field (e.g., str, int, float, bool, list, dict)."
                ),
            },
            {
                "name": "multiple",
                "display_name": "Multiple",
                "type": "boolean",
                "description": "Set to True if this output field should be a list of the specified type.",
            },
        ]
        component.output_schema = TableInput(name="output_schema", display_name="Output Schema", table_schema=schema)

        # Assertion
        output_model = build_model_from_schema(schema)
        assert isinstance(output_model, type)

    def test_handles_multiple_outputs(self):
        # Setup
        component = StructuredOutputComponent()
        schema = [
            {
                "name": "name",
                "display_name": "Name",
                "type": "str",
                "description": "Specify the name of the output field.",
            },
            {
                "name": "description",
                "display_name": "Description",
                "type": "str",
                "description": "Describe the purpose of the output field.",
            },
            {
                "name": "type",
                "display_name": "Type",
                "type": "str",
                "description": (
                    "Indicate the data type of the output field (e.g., str, int, float, bool, list, dict)."
                ),
            },
            {
                "name": "multiple",
                "display_name": "Multiple",
                "type": "boolean",
                "description": "Set to True if this output field should be a list of the specified type.",
            },
        ]
        component.output_schema = TableInput(name="output_schema", display_name="Output Schema", table_schema=schema)
        component.multiple = True

        # Assertion
        output_model = build_model_from_schema(schema)
        assert isinstance(output_model, type)

    def test_empty_output_schema(self):
        component = StructuredOutputComponent(
            llm=MockLanguageModel(),
            input_value="Test input",
            schema_name="EmptySchema",
            output_schema=[],
            multiple=False,
        )

        with pytest.raises(ValueError, match="Output schema cannot be empty"):
            component.build_structured_output()

    def test_invalid_output_schema_type(self):
        component = StructuredOutputComponent(
            llm=MockLanguageModel(),
            input_value="Test input",
            schema_name="InvalidSchema",
            output_schema=[{"name": "field", "type": "invalid_type", "description": "Invalid field"}],
            multiple=False,
        )

        with pytest.raises(ValueError, match="Invalid type: invalid_type"):
            component.build_structured_output()

    @patch("langflow.components.helpers.structured_output.get_chat_result")
    def test_nested_output_schema(self, mock_get_chat_result):
        class ChildModel(BaseModel):
            child: str = "value"

        class ParentModel(BaseModel):
            objects: list[dict] = [{"parent": {"child": "value"}}]

            def model_dump(self, **__):
                return {"objects": self.objects}

        mock_llm = MockLanguageModel()
        mock_get_chat_result.return_value = ParentModel()

        component = StructuredOutputComponent(
            llm=mock_llm,
            input_value="Test input",
            schema_name="NestedSchema",
            output_schema=[
                {
                    "name": "parent",
                    "type": "dict",
                    "description": "Parent field",
                    "fields": [{"name": "child", "type": "str", "description": "Child field"}],
                }
            ],
            multiple=False,
            system_prompt="Test system prompt",
        )

        result = component.build_structured_output_base()
        assert isinstance(result, list)
        assert result == [{"parent": {"child": "value"}}]

    @patch("langflow.components.helpers.structured_output.get_chat_result")
    def test_large_input_value(self, mock_get_chat_result):
        large_input = "Test input " * 1000

        class MockBaseModel(BaseModel):
            objects: list[dict] = [{"field": "value"}]

            def model_dump(self, **__):
                return {"objects": self.objects}

        mock_get_chat_result.return_value = MockBaseModel()

        component = StructuredOutputComponent(
            llm=MockLanguageModel(),
            input_value=large_input,
            schema_name="LargeInputSchema",
            output_schema=[{"name": "field", "type": "str", "description": "A test field"}],
            multiple=False,
            system_prompt="Test system prompt",
        )

        result = component.build_structured_output_base()
        assert isinstance(result, list)
        assert result == [{"field": "value"}]
        mock_get_chat_result.assert_called_once()

    @pytest.mark.skipif(
        "OPENAI_API_KEY" not in os.environ,
        reason="OPENAI_API_KEY environment variable not set",
    )
    def test_with_real_openai_model_simple_schema(self):
        # Create a real OpenAI model
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        # Create a component with a simple schema
        component = StructuredOutputComponent(
            llm=llm,
            input_value="Extract the name and age from this text: John Doe is 30 years old.",
            schema_name="PersonInfo",
            output_schema=[
                {"name": "name", "type": "str", "description": "The person's name"},
                {"name": "age", "type": "int", "description": "The person's age"},
            ],
            multiple=False,
            system_prompt="Extract structured information from the input text.",
        )

        # Get the structured output
        result = component.build_structured_output_base()

        # Verify the result
        assert isinstance(result, list)
        assert len(result) > 0
        assert "name" in result[0]
        assert "age" in result[0]
        assert result[0]["name"] == "John Doe"
        assert result[0]["age"] == 30

    @pytest.mark.skipif(
        "OPENAI_API_KEY" not in os.environ,
        reason="OPENAI_API_KEY environment variable not set",
    )
    def test_with_real_openai_model_simple_schema_fail(self):
        # Create a real OpenAI model with very low max_tokens to force truncation
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=1)

        # Create a component with a simple schema
        component = StructuredOutputComponent(
            llm=llm,
            input_value="Extract the name and age from this text: John Doe is 30 years old.",
            schema_name="PersonInfo",
            output_schema=[
                {"name": "name", "type": "str", "description": "The person's name"},
                {"name": "age", "type": "int", "description": "The person's age"},
            ],
            multiple=False,
            system_prompt="Extract structured information from the input text.",
        )

        # Expect BadRequestError due to max_tokens being reached
        with pytest.raises(openai.BadRequestError) as exc_info:
            component.build_structured_output_base()

        # Verify the error message contains expected content
        assert "max_tokens was reached" in str(exc_info.value)

    @pytest.mark.skipif(
        "OPENAI_API_KEY" not in os.environ,
        reason="OPENAI_API_KEY environment variable not set",
    )
    def test_with_real_openai_model_complex_schema(self):
        from langchain_openai import ChatOpenAI

        # Create a real OpenAI model
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        # Create a component with a more complex schema
        component = StructuredOutputComponent(
            llm=llm,
            input_value="""
            Product Review:
            I purchased the XYZ Wireless Headphones last month. The sound quality is excellent,
            and the battery lasts about 8 hours. However, they're a bit uncomfortable after
            wearing them for a long time. The price was $129.99, which I think is reasonable
            for the quality. Overall rating: 4/5.
            """,
            schema_name="ProductReview",
            output_schema=[
                {"name": "product_name", "type": "str", "description": "The name of the product"},
                {"name": "sound_quality", "type": "str", "description": "Description of sound quality"},
                {"name": "comfort", "type": "str", "description": "Description of comfort"},
                {"name": "battery_life", "type": "str", "description": "Description of battery life"},
                {"name": "price", "type": "float", "description": "The price of the product"},
                {"name": "rating", "type": "float", "description": "The overall rating out of 5"},
            ],
            multiple=False,
            system_prompt="Extract detailed product review information from the input text.",
        )

        # Get the structured output
        result = component.build_structured_output_base()

        # Verify the result
        assert isinstance(result, list)
        assert len(result) > 0
        assert "product_name" in result[0]
        assert "sound_quality" in result[0]
        assert "comfort" in result[0]
        assert "battery_life" in result[0]
        assert "price" in result[0]
        assert "rating" in result[0]
        assert result[0]["product_name"] == "XYZ Wireless Headphones"
        assert result[0]["price"] == 129.99
        assert result[0]["rating"] == 4.0

    @pytest.mark.skipif(
        "OPENAI_API_KEY" not in os.environ,
        reason="OPENAI_API_KEY environment variable not set",
    )
    def test_with_real_openai_model_nested_schema(self):
        from langchain_openai import ChatOpenAI

        # Create a real OpenAI model
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        # Create a component with a flattened schema (no nested structures)
        component = StructuredOutputComponent(
            llm=llm,
            input_value="""
            Restaurant: Bella Italia
            Address: 123 Main St, Anytown, CA 12345
            Visited: June 15, 2023

            Ordered:
            - Margherita Pizza ($14.99) - Delicious with fresh basil
            - Tiramisu ($8.50) - Perfect sweetness

            Service was excellent, atmosphere was cozy.
            Total bill: $35.49 including tip.
            Would definitely visit again!
            """,
            schema_name="RestaurantReview",
            output_schema=[
                {"name": "restaurant_name", "type": "str", "description": "The name of the restaurant"},
                {"name": "street", "type": "str", "description": "Street address"},
                {"name": "city", "type": "str", "description": "City"},
                {"name": "state", "type": "str", "description": "State"},
                {"name": "zip", "type": "str", "description": "ZIP code"},
                {"name": "first_item_name", "type": "str", "description": "Name of first item ordered"},
                {"name": "first_item_price", "type": "float", "description": "Price of first item"},
                {"name": "second_item_name", "type": "str", "description": "Name of second item ordered"},
                {"name": "second_item_price", "type": "float", "description": "Price of second item"},
                {"name": "total_bill", "type": "float", "description": "Total bill amount"},
                {"name": "would_return", "type": "bool", "description": "Whether the reviewer would return"},
            ],
            multiple=False,
            system_prompt="Extract detailed restaurant review information from the input text.",
        )

        # Get the structured output
        result = component.build_structured_output_base()

        # Verify the result
        assert isinstance(result, list)
        assert len(result) > 0
        assert "restaurant_name" in result[0]
        assert "street" in result[0]
        assert "city" in result[0]
        assert "state" in result[0]
        assert "zip" in result[0]
        assert "first_item_name" in result[0]
        assert "first_item_price" in result[0]
        assert "total_bill" in result[0]
        assert "would_return" in result[0]

        assert result[0]["restaurant_name"] == "Bella Italia"
        assert result[0]["street"] == "123 Main St"
        assert result[0]["total_bill"] == 35.49
        assert result[0]["would_return"] is True

    @pytest.mark.skipif(
        "NVIDIA_API_KEY" not in os.environ,
        reason="NVIDIA_API_KEY environment variable not set",
    )
    def test_with_real_nvidia_model_simple_schema(self):
        # Create a real NVIDIA model
        llm = ChatNVIDIA(model="meta/llama-3.2-3b-instruct", temperature=0, max_tokens=10)

        # Create a component with a simple schema
        component = StructuredOutputComponent(
            llm=llm,
            input_value="Extract the name and age from this text: John Doe is 30 years old.",
            schema_name="PersonInfo",
            output_schema=[
                {"name": "name", "type": "str", "description": "The person's name"},
                {"name": "age", "type": "int", "description": "The person's age"},
            ],
            multiple=False,
            system_prompt="Extract structured information from the input text.",
        )

        # The test is expected to fail with a 400 Bad Request error
        with pytest.raises(Exception, match="400 Bad Request"):
            component.build_structured_output_base()
