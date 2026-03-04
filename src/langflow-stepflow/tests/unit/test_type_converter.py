"""Unit tests for BaseModel serialization and deserialization handlers."""

import os
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import BaseModel, SecretStr

from langflow_stepflow.worker.base_executor import BaseExecutor
from langflow_stepflow.worker.handlers import (
    BaseModelInputHandler,
    BaseModelOutputHandler,
)
from langflow_stepflow.worker.handlers.base_model import (
    _is_secret_str_type,
)


# Test BaseModel classes
class SimpleTestModel(BaseModel):
    """Simple test model without special types."""

    name: str
    value: int
    enabled: bool = True


class SecretTestModel(BaseModel):
    """Test model with SecretStr fields."""

    name: str
    api_key: SecretStr
    optional_secret: SecretStr | None = None


class MockOpenAIEmbeddings(BaseModel):
    """Mock OpenAI embeddings model to test real-world scenario."""

    model: str = "text-embedding-3-small"
    openai_api_key: SecretStr
    chunk_size: int = 1000
    max_retries: int = 3
    dimensions: int | None = None


class ConcreteTestExecutor(BaseExecutor):
    """Concrete BaseExecutor subclass for tree walker tests."""

    async def _instantiate_component(self, component_info: dict[str, Any]) -> tuple[Any, str]:
        return component_info.get("instance"), component_info.get("name", "test")


class TestBaseModelOutputHandler:
    """Test cases for BaseModelOutputHandler serialization."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = BaseModelOutputHandler()

    def test_simple_types_not_matched(self):
        """Test that simple types are not matched by BaseModelOutputHandler."""
        assert not self.handler.matches(value="test")
        assert not self.handler.matches(value=42)
        assert not self.handler.matches(value=True)
        assert not self.handler.matches(value=[1, 2, 3])
        assert not self.handler.matches(value={"key": "value"})
        assert not self.handler.matches(value=None)

    @pytest.mark.asyncio
    async def test_simple_basemodel_serialization(self):
        """Test serialization of simple BaseModel without special types."""
        model = SimpleTestModel(name="test", value=42, enabled=False)

        serialized = await self.handler.process(model)

        # Check that it includes the data
        assert serialized["name"] == "test"
        assert serialized["value"] == 42
        assert serialized["enabled"] is False

        # Check that it includes class metadata
        assert serialized["__class_name__"] == "SimpleTestModel"
        assert serialized["__module_name__"] == "tests.unit.test_type_converter"

    @pytest.mark.asyncio
    async def test_secret_str_serialization_with_actual_secret(self):
        """Test that SecretStr fields are properly serialized with actual values."""
        secret_value = "sk-test-api-key-12345"
        model = SecretTestModel(
            name="test",
            api_key=SecretStr(secret_value),
            optional_secret=SecretStr("optional-secret-value"),
        )

        serialized = await self.handler.process(model)

        # Check that secret values are properly extracted
        assert serialized["name"] == "test"
        assert serialized["api_key"] == secret_value
        assert serialized["optional_secret"] == "optional-secret-value"

        # Check class metadata
        assert serialized["__class_name__"] == "SecretTestModel"
        assert serialized["__module_name__"] == "tests.unit.test_type_converter"

    @pytest.mark.asyncio
    async def test_secret_str_serialization_with_env_var_resolution(self):
        """Test that SecretStr fields with environment variable names are resolved."""
        # Set up environment variable
        test_api_key = "sk-actual-api-key-from-env"

        with patch.dict(os.environ, {"TEST_API_KEY": test_api_key}):
            # Create model with environment variable name as secret
            model = SecretTestModel(
                name="test",
                api_key=SecretStr("TEST_API_KEY"),  # Environment variable name
            )

            serialized = await self.handler.process(model)

            # Check that environment variable was resolved
            assert serialized["api_key"] == test_api_key
            assert serialized["name"] == "test"

    @pytest.mark.asyncio
    async def test_secret_str_serialization_no_env_var_fallback(self):
        """Test SecretStr serialization when environment variable doesn't exist."""
        # Create model with non-existent environment variable name
        model = SecretTestModel(name="test", api_key=SecretStr("NON_EXISTENT_ENV_VAR"))

        serialized = await self.handler.process(model)

        # Should keep the original value if env var doesn't exist
        assert serialized["api_key"] == "NON_EXISTENT_ENV_VAR"
        assert serialized["name"] == "test"

    @pytest.mark.asyncio
    async def test_openai_embeddings_like_serialization(self):
        """Test serialization of OpenAI-like embeddings model."""
        api_key = "sk-real-openai-key-12345"
        model = MockOpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=SecretStr(api_key),
            chunk_size=500,
            dimensions=1536,
        )

        serialized = await self.handler.process(model)

        # Check all fields are properly serialized
        assert serialized["model"] == "text-embedding-3-small"
        assert serialized["openai_api_key"] == api_key  # SecretStr unwrapped
        assert serialized["chunk_size"] == 500
        assert serialized["max_retries"] == 3  # Default value
        assert serialized["dimensions"] == 1536

        # Check class metadata for reconstruction
        assert serialized["__class_name__"] == "MockOpenAIEmbeddings"
        assert serialized["__module_name__"] == "tests.unit.test_type_converter"

    @pytest.mark.asyncio
    async def test_openai_api_key_env_var_resolution(self):
        """Test that OPENAI_API_KEY environment variable is properly resolved."""
        real_api_key = "sk-proj-real-openai-key-from-environment"

        with patch.dict(os.environ, {"OPENAI_API_KEY": real_api_key}):
            model = MockOpenAIEmbeddings(openai_api_key=SecretStr("OPENAI_API_KEY"))

            serialized = await self.handler.process(model)

            # Verify the actual API key value is serialized, not the env var name
            assert serialized["openai_api_key"] == real_api_key

    @pytest.mark.asyncio
    async def test_mixed_secret_and_regular_fields(self):
        """Test model with both secret and regular fields."""
        api_key = "secret-key-value"
        model = SecretTestModel(
            name="production-model",
            api_key=SecretStr(api_key),
            optional_secret=None,  # Test None value
        )

        serialized = await self.handler.process(model)

        # Regular field should be unchanged
        assert serialized["name"] == "production-model"
        # Secret field should be unwrapped
        assert serialized["api_key"] == api_key
        # None secret field should remain None
        assert serialized["optional_secret"] is None

    @pytest.mark.asyncio
    @patch.dict(os.environ, {}, clear=True)  # Clear environment
    async def test_secret_str_with_no_env_vars(self):
        """Test SecretStr serialization when no environment variables are set."""
        model = SecretTestModel(name="test", api_key=SecretStr("MISSING_API_KEY"))

        serialized = await self.handler.process(model)

        # Should keep original value if env var resolution fails
        assert serialized["api_key"] == "MISSING_API_KEY"

    @pytest.mark.asyncio
    async def test_serialized_data_structure_debugging(self):
        """Test to show what serialized data looks like for debugging."""
        api_key = "sk-debug-key-12345"
        model = MockOpenAIEmbeddings(model="test-model", openai_api_key=SecretStr(api_key), chunk_size=123)

        serialized = await self.handler.process(model)

        # Verify the structure
        assert "openai_api_key" in serialized
        assert serialized["openai_api_key"] == api_key
        assert "__class_name__" in serialized
        assert "__module_name__" in serialized


class TestBaseModelInputHandler:
    """Test cases for BaseModelInputHandler deserialization."""

    def setup_method(self):
        """Set up test fixtures."""
        self.input_handler = BaseModelInputHandler()
        self.output_handler = BaseModelOutputHandler()

    @pytest.mark.asyncio
    async def test_simple_basemodel_deserialization(self):
        """Test deserialization of simple BaseModel."""
        model = SimpleTestModel(name="test", value=42, enabled=False)
        serialized = await self.output_handler.process(model)

        fields = {"param": (serialized, {})}
        result = await self.input_handler.prepare(fields, None)

        deserialized = result["param"]
        assert isinstance(deserialized, SimpleTestModel)
        assert deserialized.name == "test"
        assert deserialized.value == 42
        assert deserialized.enabled is False

    @pytest.mark.asyncio
    async def test_openai_embeddings_like_deserialization(self):
        """Test deserialization of OpenAI-like embeddings model."""
        api_key = "sk-real-openai-key-12345"
        model = MockOpenAIEmbeddings(
            model="text-embedding-ada-002",
            openai_api_key=SecretStr(api_key),
            chunk_size=750,
        )

        # Serialize then deserialize
        serialized = await self.output_handler.process(model)
        fields = {"param": (serialized, {})}
        result = await self.input_handler.prepare(fields, None)

        deserialized = result["param"]
        assert isinstance(deserialized, MockOpenAIEmbeddings)
        assert deserialized.model == "text-embedding-ada-002"
        assert deserialized.chunk_size == 750
        assert deserialized.max_retries == 3  # Default

        # Check that SecretStr field is reconstructed properly
        assert isinstance(deserialized.openai_api_key, SecretStr)
        assert deserialized.openai_api_key.get_secret_value() == api_key

    @pytest.mark.asyncio
    async def test_openai_api_key_env_var_round_trip(self):
        """Test that OPENAI_API_KEY environment variable is properly resolved."""
        real_api_key = "sk-proj-real-openai-key-from-environment"

        with patch.dict(os.environ, {"OPENAI_API_KEY": real_api_key}):
            model = MockOpenAIEmbeddings(openai_api_key=SecretStr("OPENAI_API_KEY"))

            serialized = await self.output_handler.process(model)

            # Test full round-trip
            fields = {"param": (serialized, {})}
            result = await self.input_handler.prepare(fields, None)

            deserialized = result["param"]
            assert isinstance(deserialized.openai_api_key, SecretStr)
            assert deserialized.openai_api_key.get_secret_value() == real_api_key

    def test_deserialization_without_class_metadata(self):
        """Test that regular dicts without markers don't match."""
        regular_dict = {"name": "test", "value": 42}
        assert not self.input_handler.matches(template_field={}, value=regular_dict)

    @pytest.mark.asyncio
    async def test_deserialization_with_invalid_class_metadata(self):
        """Test deserialization gracefully handles invalid class metadata."""
        invalid_serialized = {
            "name": "test",
            "__class_name__": "NonExistentClass",
            "__module_name__": "non.existent.module",
        }

        fields = {"param": (invalid_serialized, {})}
        result = await self.input_handler.prepare(fields, None)

        # Should return the dict unchanged if class can't be imported
        assert result["param"] == invalid_serialized


class TestIsSecretStrType:
    """Test the _is_secret_str_type helper function."""

    def test_direct_secret_str_detection(self):
        assert _is_secret_str_type(SecretStr)

    def test_optional_secret_str_detection(self):
        assert _is_secret_str_type(SecretStr | None)

    def test_non_secret_types(self):
        assert not _is_secret_str_type(str)
        assert not _is_secret_str_type(int)
        assert not _is_secret_str_type(str | None)


class TestOutputTreeWalker:
    """Test the recursive output tree walker in BaseExecutor."""

    def setup_method(self):
        self.executor = ConcreteTestExecutor()
        self.handlers = [BaseModelOutputHandler()]

    @pytest.mark.asyncio
    async def test_simple_types_pass_through(self):
        """Test that simple types pass through the tree walker unchanged."""
        assert await self.executor._apply_output_handlers("test", self.handlers) == "test"
        assert await self.executor._apply_output_handlers(42, self.handlers) == 42
        assert await self.executor._apply_output_handlers(True, self.handlers) is True
        assert await self.executor._apply_output_handlers([1, 2, 3], self.handlers) == [
            1,
            2,
            3,
        ]
        assert await self.executor._apply_output_handlers({"key": "value"}, self.handlers) == {"key": "value"}
        assert await self.executor._apply_output_handlers(None, self.handlers) is None

    @pytest.mark.asyncio
    async def test_non_basemodel_object_error(self):
        """Test that non-serializable objects raise appropriate errors."""

        class NonSerializableClass:
            def __init__(self):
                self.value = "test"

        obj = NonSerializableClass()

        with pytest.raises(ValueError, match="Cannot serialize object of type"):
            await self.executor._apply_output_handlers(obj, self.handlers)

    @pytest.mark.asyncio
    async def test_langflow_types_still_work(self):
        """Test that existing Langflow type serialization still works."""
        try:
            from langflow.schema.message import Message

            message = Message(text="test message")

            from langflow_stepflow.worker.handlers import (
                LangflowTypeOutputHandler,
            )

            handlers = [LangflowTypeOutputHandler(), BaseModelOutputHandler()]
            serialized = await self.executor._apply_output_handlers(message, handlers)

            # Should have Langflow type metadata, not BaseModel metadata
            assert "__langflow_type__" in serialized
            assert serialized["__langflow_type__"] == "Message"

        except ImportError:
            # Skip if Langflow not available
            pytest.skip("Langflow not available for testing")

    @pytest.mark.asyncio
    async def test_real_openai_embeddings_serialization(self):
        """Test with actual OpenAI embeddings class if available."""
        try:
            from langchain_openai import OpenAIEmbeddings
            from pydantic import SecretStr

            # Test with a real OpenAIEmbeddings instance
            api_key = "sk-test-real-openai-key"
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=api_key,  # Becomes SecretStr automatically
                chunk_size=500,
            )

            # Serialize
            serialized = await self.executor._apply_output_handlers(embeddings, self.handlers)

            # Check that API key is properly extracted
            assert "openai_api_key" in serialized
            assert serialized["openai_api_key"] == api_key
            assert serialized["model"] == "text-embedding-3-small"
            assert serialized["chunk_size"] == 500

            # Check metadata for reconstruction
            assert serialized["__class_name__"] == "OpenAIEmbeddings"
            assert "langchain_openai" in serialized["__module_name__"]

            # Test deserialization
            input_handler = BaseModelInputHandler()
            fields = {"param": (serialized, {})}
            result = await input_handler.prepare(fields, None)

            deserialized = result["param"]
            assert isinstance(deserialized, OpenAIEmbeddings)
            assert deserialized.model == "text-embedding-3-small"
            assert deserialized.chunk_size == 500

            # Check that SecretStr is properly reconstructed
            assert hasattr(deserialized, "openai_api_key")
            if isinstance(deserialized.openai_api_key, SecretStr):
                assert deserialized.openai_api_key.get_secret_value() == api_key
            else:
                # In some versions, it might be a string after deserialization
                assert deserialized.openai_api_key == api_key

        except ImportError:
            pytest.skip("langchain_openai not available for real OpenAI embeddings test")
