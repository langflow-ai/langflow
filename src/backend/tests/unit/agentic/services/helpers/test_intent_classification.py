"""Tests for intent classification helper.

Tests the classify_intent function that translates text and
classifies user intent as component generation or question.
"""

from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.flow_types import IntentResult
from langflow.agentic.services.helpers.intent_classification import classify_intent


class TestClassifyIntent:
    """Tests for classify_intent function."""

    @pytest.mark.asyncio
    async def test_should_return_generate_component_intent(self):
        """Should return generate_component intent when LLM classifies as such."""
        mock_result = {"result": '{"translation": "create a component", "intent": "generate_component"}'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="crie um componente",
                global_variables={},
            )

            assert result.intent == "generate_component"
            assert result.translation == "create a component"

    @pytest.mark.asyncio
    async def test_should_return_question_intent(self):
        """Should return question intent when LLM classifies as such."""
        mock_result = {"result": '{"translation": "how to create a component", "intent": "question"}'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="como criar um componente",
                global_variables={},
            )

            assert result.intent == "question"
            assert result.translation == "how to create a component"

    @pytest.mark.asyncio
    async def test_should_return_question_for_empty_text(self):
        """Should return question intent with original text for empty input."""
        result = await classify_intent(
            text="",
            global_variables={},
        )

        assert result.intent == "question"
        assert result.translation == ""

    @pytest.mark.asyncio
    async def test_should_handle_non_json_response(self):
        """Should treat non-JSON response as question with the text as translation."""
        mock_result = {"result": "This is not valid JSON response"}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="some input",
                global_variables={},
            )

            assert result.intent == "question"
            assert result.translation == "This is not valid JSON response"

    @pytest.mark.asyncio
    async def test_should_default_to_question_on_flow_error(self):
        """Should default to question intent when flow execution fails."""
        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            side_effect=Exception("Flow execution failed"),
        ):
            result = await classify_intent(
                text="create a component",
                global_variables={},
            )

            assert result.intent == "question"
            assert result.translation == "create a component"

    @pytest.mark.asyncio
    async def test_should_default_to_question_on_empty_response(self):
        """Should default to question when response text is empty."""
        mock_result = {"result": ""}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="some input",
                global_variables={},
            )

            assert result.intent == "question"
            assert result.translation == "some input"

    @pytest.mark.asyncio
    async def test_should_handle_missing_translation_field(self):
        """Should use original text when translation field is missing."""
        mock_result = {"result": '{"intent": "question"}'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="input text",
                global_variables={},
            )

            assert result.intent == "question"
            assert result.translation == "input text"

    @pytest.mark.asyncio
    async def test_should_handle_missing_intent_field(self):
        """Should default to question when intent field is missing."""
        mock_result = {"result": '{"translation": "translated text"}'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="input text",
                global_variables={},
            )

            assert result.intent == "question"
            assert result.translation == "translated text"

    @pytest.mark.asyncio
    async def test_should_pass_all_parameters_to_flow(self):
        """Should pass all optional parameters to the flow executor."""
        mock_result = {"result": '{"translation": "test", "intent": "question"}'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_execute:
            await classify_intent(
                text="test input",
                global_variables={"API_KEY": "secret"},
                user_id="user123",
                session_id="session456",
                provider="OpenAI",
                model_name="gpt-4",
                api_key_var="OPENAI_API_KEY",
            )

            mock_execute.assert_called_once()
            call_kwargs = mock_execute.call_args[1]
            assert call_kwargs["input_value"] == "test input"
            assert call_kwargs["global_variables"] == {"API_KEY": "secret"}
            assert call_kwargs["user_id"] == "user123"
            assert call_kwargs["session_id"] == "session456"
            assert call_kwargs["provider"] == "OpenAI"
            assert call_kwargs["model_name"] == "gpt-4"
            assert call_kwargs["api_key_var"] == "OPENAI_API_KEY"

    @pytest.mark.asyncio
    async def test_should_use_translation_flow_filename(self):
        """Should use the TRANSLATION_FLOW constant as flow filename."""
        mock_result = {"result": '{"translation": "test", "intent": "question"}'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_execute:
            await classify_intent(
                text="test",
                global_variables={},
            )

            call_kwargs = mock_execute.call_args[1]
            assert call_kwargs["flow_filename"] == "TranslationFlow"


class TestIntentResult:
    """Tests for IntentResult dataclass."""

    def test_should_create_with_translation_and_intent(self):
        """Should create IntentResult with translation and intent."""
        result = IntentResult(translation="hello", intent="question")

        assert result.translation == "hello"
        assert result.intent == "question"

    def test_should_allow_generate_component_intent(self):
        """Should allow generate_component as valid intent."""
        result = IntentResult(translation="create a component", intent="generate_component")

        assert result.intent == "generate_component"

    def test_should_be_comparable(self):
        """Should be comparable with other IntentResult instances."""
        result1 = IntentResult(translation="test", intent="question")
        result2 = IntentResult(translation="test", intent="question")
        result3 = IntentResult(translation="test", intent="generate_component")

        assert result1 == result2
        assert result1 != result3
