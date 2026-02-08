from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from lfx.components.policies.llm_wrapper import LangchainModelWrapper


@pytest.fixture
def mock_langchain_model():
    """Create a mock BaseChatModel for testing."""
    model = MagicMock()
    model.max_tokens = None
    model.agenerate = AsyncMock()
    return model


@pytest.fixture
def wrapper(mock_langchain_model):
    """Create a LangchainModelWrapper instance with mocked model."""
    return LangchainModelWrapper(mock_langchain_model)


def create_llm_result(content: str, finish_reason: str = "stop") -> LLMResult:
    """Helper to create a mock LLMResult."""
    message = AIMessage(content=content)
    generation = ChatGeneration(message=message, generation_info={"finish_reason": finish_reason})
    return LLMResult(generations=[[generation]])


class TestInitialization:
    """Tests for LangchainModelWrapper initialization."""

    @pytest.mark.asyncio
    async def test_init_sets_max_tokens(self, mock_langchain_model):
        """Test that __init__ sets max_tokens to DEFAULT_MAX_TOKENS if it's None."""
        assert mock_langchain_model.max_tokens is None

        wrapper = LangchainModelWrapper(mock_langchain_model)

        assert getattr(wrapper.langchain_model, "max_tokens", None) == LangchainModelWrapper.DEFAULT_MAX_TOKENS

    @pytest.mark.asyncio
    async def test_init_preserves_existing_max_tokens(self):
        """Test that __init__ doesn't override existing max_tokens."""
        model = MagicMock()
        model.max_tokens = 5000
        model.agenerate = AsyncMock()

        wrapper = LangchainModelWrapper(model)

        assert getattr(wrapper.langchain_model, "max_tokens", None) == 5000

    @pytest.mark.asyncio
    async def test_init_without_max_tokens_attribute(self):
        """Test that __init__ handles models without max_tokens attribute."""
        model = MagicMock(spec=["agenerate"])  # No max_tokens attribute
        model.agenerate = AsyncMock()

        # Should not raise an error
        wrapper = LangchainModelWrapper(model)

        assert wrapper.langchain_model == model


class TestRoleConversion:
    """Tests for role conversion logic."""

    def test_convert_role_user_to_human(self, wrapper):
        """Test that 'user' role converts to 'human'."""
        assert wrapper._convert_role("user") == "human"

    def test_convert_role_assistant_to_ai(self, wrapper):
        """Test that 'assistant' role converts to 'ai'."""
        assert wrapper._convert_role("assistant") == "ai"

    def test_convert_role_system_to_system(self, wrapper):
        """Test that 'system' role stays as 'system'."""
        assert wrapper._convert_role("system") == "system"

    def test_convert_role_unknown_defaults_to_system(self, wrapper):
        """Test that unknown roles default to 'system'."""
        assert wrapper._convert_role("unknown") == "system"
        assert wrapper._convert_role("") == "system"


class TestMessageValidation:
    """Tests for message validation."""

    def test_validate_messages_valid(self, wrapper):
        """Test validation passes for valid messages."""
        messages = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there"}]
        # Should not raise
        wrapper._validate_messages(messages)

    def test_validate_messages_not_list(self, wrapper):
        """Test validation fails if messages is not a list."""
        with pytest.raises(TypeError, match="Messages must be a list"):
            wrapper._validate_messages("not a list")

    def test_validate_messages_item_not_dict(self, wrapper):
        """Test validation fails if message item is not a dict."""
        messages = [{"role": "user", "content": "Hello"}, "not a dict"]
        with pytest.raises(TypeError, match="Message at index 1 must be a dict"):
            wrapper._validate_messages(messages)

    def test_validate_messages_missing_role(self, wrapper):
        """Test validation fails if message missing 'role'."""
        messages = [{"content": "Hello"}]
        with pytest.raises(ValueError, match="missing 'role' field"):
            wrapper._validate_messages(messages)

    def test_validate_messages_missing_content(self, wrapper):
        """Test validation fails if message missing 'content'."""
        messages = [{"role": "user"}]
        with pytest.raises(ValueError, match="missing 'content' field"):
            wrapper._validate_messages(messages)


class TestContentExtraction:
    """Tests for content extraction logic."""

    def test_extract_content_string(self, wrapper):
        """Test extracting string content."""
        assert wrapper._extract_content("Hello") == "Hello"

    def test_extract_content_none(self, wrapper):
        """Test extracting None returns empty string."""
        assert wrapper._extract_content(None) == ""

    def test_extract_content_list(self, wrapper):
        """Test extracting list joins with space."""
        assert wrapper._extract_content(["Hello", "world"]) == "Hello world"

    def test_extract_content_tuple(self, wrapper):
        """Test extracting tuple joins with space."""
        assert wrapper._extract_content(("Hello", "world")) == "Hello world"

    def test_extract_content_number(self, wrapper):
        """Test extracting number converts to string."""
        assert wrapper._extract_content(42) == "42"

    def test_extract_content_mixed_list(self, wrapper):
        """Test extracting list with mixed types."""
        assert wrapper._extract_content(["Hello", 42, None]) == "Hello 42 None"


class TestGenerate:
    """Tests for the generate method."""

    @pytest.mark.asyncio
    async def test_generate_simple_message(self, wrapper, mock_langchain_model):
        """Test generate with a simple message that completes successfully."""
        messages = [{"role": "user", "content": "Hello, how are you?"}]

        mock_langchain_model.agenerate.return_value = create_llm_result("I'm doing well, thank you!")

        result = await wrapper.generate(messages)

        assert result == "I'm doing well, thank you!"
        assert mock_langchain_model.agenerate.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_multiple_messages(self, wrapper, mock_langchain_model):
        """Test generate with multiple messages."""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]

        mock_langchain_model.agenerate.return_value = create_llm_result("I'm good!")

        result = await wrapper.generate(messages)

        assert result == "I'm good!"

    @pytest.mark.asyncio
    async def test_generate_with_max_tokens_reached(self, wrapper, mock_langchain_model):
        """Test generate handles max tokens reached by continuing generation."""
        messages = [{"role": "user", "content": "Write a long story"}]

        # First call: max tokens reached
        first_result = create_llm_result("Once upon a time, there was", finish_reason="length")

        # Second call: completion
        second_result = create_llm_result(" a brave knight who saved the kingdom.", finish_reason="stop")

        mock_langchain_model.agenerate.side_effect = [first_result, second_result]

        result = await wrapper.generate(messages)

        assert result == "Once upon a time, there was a brave knight who saved the kingdom."
        assert mock_langchain_model.agenerate.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_max_continuations_exceeded(self, wrapper, mock_langchain_model):
        """Test that max continuations limit prevents infinite recursion."""
        messages = [{"role": "user", "content": "Test"}]

        # Always return length finish reason
        mock_langchain_model.agenerate.return_value = create_llm_result("Part", finish_reason="length")

        with pytest.raises(RuntimeError, match="Maximum continuation depth"):
            await wrapper.generate(messages)

    @pytest.mark.asyncio
    async def test_generate_invalid_messages(self, wrapper):
        """Test generate fails with invalid messages."""
        with pytest.raises(TypeError, match="Messages must be a list"):
            await wrapper.generate("not a list")

    @pytest.mark.asyncio
    async def test_generate_api_failure(self, wrapper, mock_langchain_model):
        """Test generate handles API failures gracefully."""
        messages = [{"role": "user", "content": "Test"}]

        mock_langchain_model.agenerate.side_effect = Exception("API Error")

        with pytest.raises(RuntimeError, match="Language model API call failed"):
            await wrapper.generate(messages)

    @pytest.mark.asyncio
    async def test_generate_empty_response(self, wrapper, mock_langchain_model):
        """Test generate handles empty response."""
        messages = [{"role": "user", "content": "Test"}]

        mock_langchain_model.agenerate.return_value = LLMResult(generations=[[]])

        with pytest.raises(ValueError, match="Empty response from language model"):
            await wrapper.generate(messages)

    @pytest.mark.asyncio
    async def test_generate_with_tuple_content(self, wrapper, mock_langchain_model):
        """Test generate handles tuple content correctly."""
        messages = [{"role": "user", "content": ("Line 1", "Line 2")}]

        mock_langchain_model.agenerate.return_value = create_llm_result("Response")

        result = await wrapper.generate(messages)

        assert result == "Response"
        # Verify the tuple was converted to string
        call_args = mock_langchain_model.agenerate.call_args
        called_messages = call_args.kwargs["messages"][0]
        assert "Line 1 Line 2" in str(called_messages[0].content)

    @pytest.mark.asyncio
    async def test_generate_with_none_content(self, wrapper, mock_langchain_model):
        """Test generate handles None content."""
        messages = [{"role": "user", "content": None}]

        mock_langchain_model.agenerate.return_value = create_llm_result("Response")

        result = await wrapper.generate(messages)

        assert result == "Response"

    @pytest.mark.asyncio
    async def test_generate_preserves_message_order(self, wrapper, mock_langchain_model):
        """Test that message order is preserved during conversion."""
        messages = [
            {"role": "system", "content": "First"},
            {"role": "user", "content": "Second"},
            {"role": "assistant", "content": "Third"},
        ]

        mock_langchain_model.agenerate.return_value = create_llm_result("Response")

        await wrapper.generate(messages)

        call_args = mock_langchain_model.agenerate.call_args
        called_messages = call_args.kwargs["messages"][0]

        assert called_messages[0].content == "First"
        assert called_messages[1].content == "Second"
        assert called_messages[2].content == "Third"

    @pytest.mark.asyncio
    async def test_generate_continuation_includes_previous_messages(self, wrapper, mock_langchain_model):
        """Test that continuation includes all previous messages."""
        messages = [{"role": "user", "content": "Original message"}]

        first_result = create_llm_result("Incomplete", finish_reason="length")
        second_result = create_llm_result(" Complete", finish_reason="stop")

        mock_langchain_model.agenerate.side_effect = [first_result, second_result]

        await wrapper.generate(messages)

        # Check second call includes original message + response + continuation prompt
        second_call_args = mock_langchain_model.agenerate.call_args_list[1]
        called_messages = second_call_args.kwargs["messages"][0]

        # Should have at least 3 messages: original + assistant response + continuation
        assert len(called_messages) >= 3


# Made with Bob
