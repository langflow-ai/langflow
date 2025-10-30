from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.ollama.ollama import ChatOllamaComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


@pytest.mark.integration
class TestChatOllamaIntegration:
    """Integration tests for ChatOllama structured output flow."""

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllama")
    async def test_end_to_end_structured_output_to_data(self, mock_chat_ollama):
        """Test complete flow from model response to Data output with JSON schema."""
        # Mock the model and its response
        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        # Define a JSON schema for structured output
        json_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}, "email": {"type": "string"}},
            "required": ["name", "email"],
        }

        # Create component with schema format
        component = ChatOllamaComponent(
            base_url="http://localhost:11434", model_name="llama3.1", format=json_schema, temperature=0.1
        )

        # Set up input message
        component.input_value = "Tell me about John"

        # Build model with schema
        model = component.build_model()
        assert model is not None

        # Mock the text_response to return a Message with JSON content
        json_response = '{"name": "John Doe", "age": 30, "email": "john@example.com"}'
        mock_message = Message(text=json_response)

        # Patch text_response as an async method
        with patch.object(component, "text_response", new_callable=AsyncMock, return_value=mock_message):
            # Get Data output
            data_output = await component.build_data_output()

            # Verify Data output structure
            assert isinstance(data_output, Data)
            assert data_output.data["name"] == "John Doe"
            assert data_output.data["age"] == 30
            assert data_output.data["email"] == "john@example.com"

        # Verify ChatOllama was called with the schema
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["format"] == json_schema

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllama")
    async def test_end_to_end_structured_output_to_dataframe(self, mock_chat_ollama):
        """Test complete flow from model response to DataFrame output with list of dicts."""
        # Mock the model
        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        # Create component with JSON format
        component = ChatOllamaComponent(
            base_url="http://localhost:11434", model_name="llama3.1", format="json", temperature=0.1
        )

        # Set up input message
        component.input_value = "List some people"

        # Mock the text_response with list of structured data
        json_response = """[
            {"name": "Alice", "age": 28, "city": "NYC"},
            {"name": "Bob", "age": 35, "city": "LA"},
            {"name": "Charlie", "age": 42, "city": "Chicago"}
        ]"""
        mock_message = Message(text=json_response)

        with patch.object(component, "text_response", new_callable=AsyncMock, return_value=mock_message):
            # Get DataFrame output
            df_output = await component.build_dataframe_output()

            # Verify DataFrame structure
            assert isinstance(df_output, DataFrame)
            assert len(df_output) == 3
            assert list(df_output.columns) == ["name", "age", "city"]
            assert df_output.iloc[0]["name"] == "Alice"
            assert df_output.iloc[1]["name"] == "Bob"
            assert df_output.iloc[2]["name"] == "Charlie"

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllama")
    async def test_end_to_end_with_pydantic_schema(self, mock_chat_ollama):
        """Test end-to-end flow using Pydantic model schema (addresses issue #7122)."""
        from pydantic import BaseModel, Field

        # Mock the model
        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        # Create Pydantic model as users would
        class PersonInfo(BaseModel):
            """Information about a person."""

            name: str = Field(description="The person's full name")
            age: int = Field(ge=0, le=150, description="The person's age")
            email: str = Field(description="Email address")
            city: str = Field(description="City of residence")

        # Generate schema from Pydantic model
        pydantic_schema = PersonInfo.model_json_schema()

        # Create component with Pydantic schema
        component = ChatOllamaComponent(
            base_url="http://localhost:11434", model_name="llama3.1", format=pydantic_schema, temperature=0.1
        )

        component.input_value = "Extract person info"

        # Verify model builds without error (was the bug in #7122)
        model = component.build_model()
        assert model is not None

        # Mock the text_response
        json_response = '{"name": "Jane Smith", "age": 25, "email": "jane@test.com", "city": "Boston"}'
        mock_message = Message(text=json_response)

        with patch.object(component, "text_response", new_callable=AsyncMock, return_value=mock_message):
            # Verify Data output works
            data_output = await component.build_data_output()
            assert isinstance(data_output, Data)
            assert data_output.data["name"] == "Jane Smith"
            assert data_output.data["city"] == "Boston"

        # Verify schema was passed correctly
        call_args = mock_chat_ollama.call_args[1]
        assert call_args["format"] == pydantic_schema
        assert call_args["format"]["type"] == "object"

    @pytest.mark.asyncio
    @patch("lfx.components.ollama.ollama.ChatOllama")
    async def test_json_parsing_error_handling(self, mock_chat_ollama):
        """Test that invalid JSON responses are handled gracefully."""
        # Mock the model
        mock_model = MagicMock()
        mock_chat_ollama.return_value = mock_model

        component = ChatOllamaComponent(
            base_url="http://localhost:11434", model_name="llama3.1", format="json", temperature=0.1
        )

        component.input_value = "Generate some data"

        # Mock text_response with invalid JSON
        invalid_response = "This is not valid JSON at all!"
        mock_message = Message(text=invalid_response)

        with (
            patch.object(component, "text_response", new_callable=AsyncMock, return_value=mock_message),
            pytest.raises(ValueError, match="Invalid JSON response"),
        ):
            await component.build_data_output()
