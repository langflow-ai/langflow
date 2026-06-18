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


# Pydantic renders a non-empty SecretStr field as this mask under model_dump(mode="json").
MASKED_SECRET = "**********"  # pragma: allowlist secret


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
    async def test_secret_str_fields_are_masked(self):
        """SecretStr fields serialize masked -- the plaintext value is never emitted."""
        secret_value = "test-api-key-12345"  # pragma: allowlist secret
        model = SecretTestModel(
            name="test",
            api_key=SecretStr(secret_value),
            optional_secret=SecretStr("optional-secret-value"),
        )

        serialized = await self.handler.process(model)

        assert serialized["name"] == "test"
        assert serialized["api_key"] == MASKED_SECRET
        assert serialized["optional_secret"] == MASKED_SECRET
        assert secret_value not in serialized.values()

        assert serialized["__class_name__"] == "SecretTestModel"
        assert serialized["__module_name__"] == "tests.unit.test_type_converter"

    @pytest.mark.asyncio
    async def test_env_var_name_secret_is_not_resolved(self):
        """A SecretStr holding an env var name must NOT be resolved onto the output edge."""
        test_api_key = "actual-api-key-from-env"  # pragma: allowlist secret

        with patch.dict(os.environ, {"TEST_API_KEY": test_api_key}):
            model = SecretTestModel(name="test", api_key=SecretStr("TEST_API_KEY"))

            serialized = await self.handler.process(model)

            # Neither the env var value nor its name should leak; the field stays masked.
            assert serialized["api_key"] == MASKED_SECRET
            assert test_api_key not in serialized.values()
            assert serialized["name"] == "test"

    @pytest.mark.asyncio
    async def test_openai_embeddings_like_serialization_masks_key(self):
        """OpenAI-like embeddings model serializes with its api key masked, others intact."""
        api_key = "real-openai-key-12345"  # pragma: allowlist secret
        model = MockOpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=SecretStr(api_key),
            chunk_size=500,
            dimensions=1536,
        )

        serialized = await self.handler.process(model)

        assert serialized["model"] == "text-embedding-3-small"
        assert serialized["openai_api_key"] == MASKED_SECRET
        assert api_key not in serialized.values()
        assert serialized["chunk_size"] == 500
        assert serialized["max_retries"] == 3  # Default value
        assert serialized["dimensions"] == 1536

        assert serialized["__class_name__"] == "MockOpenAIEmbeddings"
        assert serialized["__module_name__"] == "tests.unit.test_type_converter"

    @pytest.mark.asyncio
    async def test_mixed_secret_and_regular_fields(self):
        """Model with both secret and regular fields: secret masked, regular fields intact."""
        api_key = "secret-key-value"  # pragma: allowlist secret
        model = SecretTestModel(
            name="production-model",
            api_key=SecretStr(api_key),
            optional_secret=None,  # Test None value
        )

        serialized = await self.handler.process(model)

        assert serialized["name"] == "production-model"
        assert serialized["api_key"] == MASKED_SECRET
        assert api_key not in serialized.values()
        # None secret field should remain None
        assert serialized["optional_secret"] is None


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
    async def test_secret_round_trip_stays_masked(self):
        """Across the worker boundary a secret survives only as its mask, not the real value.

        Masking on the output edge is intentional (see BaseModelOutputHandler): the plaintext
        is never serialized, so a serialize->deserialize round trip reconstructs the masked
        SecretStr. A component needing the real value must resolve it on its own input edge.
        """
        api_key = "real-openai-key-12345"  # pragma: allowlist secret
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

        # The real key never crossed the boundary; only the mask round-trips.
        assert isinstance(deserialized.openai_api_key, SecretStr)
        assert deserialized.openai_api_key.get_secret_value() == MASKED_SECRET
        assert deserialized.openai_api_key.get_secret_value() != api_key

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
    async def test_real_openai_embeddings_serialization_masks_key(self):
        """Real OpenAIEmbeddings serializes with its api key masked, not unwrapped."""
        try:
            from langchain_openai import OpenAIEmbeddings
            from pydantic import SecretStr

            # Test with a real OpenAIEmbeddings instance
            api_key = "test-real-openai-key"  # pragma: allowlist secret
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=api_key,  # Becomes SecretStr automatically
                chunk_size=500,
            )

            # Serialize
            serialized = await self.executor._apply_output_handlers(embeddings, self.handlers)

            # The plaintext key must never reach the serialized output edge.
            assert "openai_api_key" in serialized
            assert serialized["openai_api_key"] == MASKED_SECRET
            assert api_key not in serialized.values()
            assert serialized["model"] == "text-embedding-3-small"
            assert serialized["chunk_size"] == 500

            # Check metadata for reconstruction
            assert serialized["__class_name__"] == "OpenAIEmbeddings"
            assert "langchain_openai" in serialized["__module_name__"]

            # Round-trips as the mask, never the real key.
            input_handler = BaseModelInputHandler()
            fields = {"param": (serialized, {})}
            result = await input_handler.prepare(fields, None)

            deserialized = result["param"]
            assert isinstance(deserialized, OpenAIEmbeddings)
            assert deserialized.model == "text-embedding-3-small"
            assert deserialized.chunk_size == 500

            assert hasattr(deserialized, "openai_api_key")
            if isinstance(deserialized.openai_api_key, SecretStr):
                assert deserialized.openai_api_key.get_secret_value() == MASKED_SECRET
                assert deserialized.openai_api_key.get_secret_value() != api_key
            else:
                assert deserialized.openai_api_key == MASKED_SECRET

        except ImportError:
            pytest.skip("langchain_openai not available for real OpenAI embeddings test")
