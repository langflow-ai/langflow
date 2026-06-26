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
    async def test_should_extract_json_from_markdown_code_block(self):
        """Models like IBM granite may wrap JSON in markdown code blocks."""
        mock_result = {"result": '```json\n{"translation": "create a component", "intent": "generate_component"}\n```'}

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
    async def test_should_extract_intent_from_text_containing_generate_component(self):
        """Fallback should extract intent from malformed JSON-like text with quoted intent value."""
        mock_result = {
            "result": 'The result is "intent": "generate_component" and translation is create a sum component'
        }

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="crie um componente que soma",
                global_variables={},
            )

            assert result.intent == "generate_component"

    @pytest.mark.asyncio
    async def test_should_extract_build_flow_intent_from_plaintext(self):
        """Fallback should extract build_flow from quoted intent value."""
        mock_result = {"result": 'I would classify this as "intent": "build_flow"'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="construa um fluxo de chatbot",
                global_variables={},
            )

            assert result.intent == "build_flow"

    @pytest.mark.asyncio
    async def test_should_extract_run_flow_intent_from_plaintext(self):
        """Bugfix: weak/non-JSON models must still surface run_flow."""
        mock_result = {"result": 'Classification: "intent": "run_flow"'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(text="rode o flow e me diga o resultado", global_variables={})

            assert result.intent == "run_flow"

    @pytest.mark.asyncio
    async def test_should_extract_off_topic_intent_from_plaintext(self):
        """Fallback should extract off_topic from quoted intent value."""
        mock_result = {"result": 'Classification: "intent": "off_topic"'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="como funciona o kubernetes",
                global_variables={},
            )

            assert result.intent == "off_topic"

    @pytest.mark.asyncio
    async def test_should_not_match_bare_intent_substring_in_prompt_echo(self):
        """Bare mention of build_flow without JSON quoting should NOT trigger fallback."""
        mock_result = {
            "result": (
                "The intent classification options are generate_component, build_flow, "
                "question, and off_topic. I cannot determine which one applies."
            )
        }

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="something ambiguous",
                global_variables={},
            )

            assert result.intent == "question"

    @pytest.mark.asyncio
    async def test_should_extract_json_with_surrounding_text(self):
        """Models may return JSON embedded in explanatory text."""
        mock_result = {
            "result": (
                'Here is the classification:\n{"translation": "build a parser", "intent": "generate_component"}\nDone.'
            )
        }

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="construa um parser",
                global_variables={},
            )

            assert result.intent == "generate_component"
            assert result.translation == "build a parser"

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
                provider="OpenAI",
                model_name="gpt-4",
                api_key_var="OPENAI_API_KEY",
            )

            mock_execute.assert_called_once()
            call_kwargs = mock_execute.call_args[1]
            assert call_kwargs["input_value"] == "test input"
            assert call_kwargs["global_variables"] == {"API_KEY": "secret"}
            assert call_kwargs["user_id"] == "user123"
            assert call_kwargs["provider"] == "OpenAI"
            assert call_kwargs["model_name"] == "gpt-4"
            assert call_kwargs["api_key_var"] == "OPENAI_API_KEY"

    @pytest.mark.asyncio
    async def test_should_not_pass_session_id_to_flow(self):
        """Should never pass session_id to TranslationFlow to avoid polluting conversation memory."""
        mock_result = {"result": '{"translation": "test", "intent": "question"}'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_execute:
            await classify_intent(
                text="test input",
                global_variables={},
                user_id="user123",
            )

            call_kwargs = mock_execute.call_args[1]
            assert "session_id" not in call_kwargs, (
                "session_id must not be passed to TranslationFlow to prevent polluting conversation memory"
            )

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
            assert call_kwargs["flow_filename"] == "translation_flow.py"


class TestCompoundComponentFlowClassification:
    """Compound create-component-then-build/run-flow → ``component_then_flow``.

    A request that BOTH creates a custom component AND builds/runs a flow
    with it is a multi-phase pipeline (intent ``component_then_flow``).
    Classification is LANGUAGE-AGNOSTIC: the TranslationFlow translates to
    English first, so this works for PT/EN/ES/… alike. These tests pin the
    plumbing (the new intent flows through classify_intent for both the
    JSON and the non-JSON fallback paths); a real-LLM multilingual proof
    lives in the e2e suite.
    """

    @pytest.mark.asyncio
    async def test_json_path_returns_component_then_flow(self):
        mock_result = {
            "result": '{"translation": "create a prime checker component then '
            'build a flow with it and run it with 14", "intent": "component_then_flow"}'
        }
        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="crie um componente de primo, monte o flow e rode com 14",
                global_variables={},
            )
        assert result.intent == "component_then_flow"

    @pytest.mark.asyncio
    async def test_non_json_fallback_extracts_component_then_flow(self):
        mock_result = {"result": 'I would classify this as "intent": "component_then_flow"'}
        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(text="make a component and a flow", global_variables={})
        assert result.intent == "component_then_flow"


class TestDeterministicRunFlowDetection:
    """The run detector is a POST-LLM safety net, not a pre-LLM override.

    The language-agnostic TranslationFlow classifies; the run regex only
    RESCUES an explicit run request when the classifier fell back to
    ``question`` (its proven flaky failure). It must NEVER override a
    confident build_flow / component_then_flow answer — doing so wrongly
    forced "create a flow with an agent … and run it" to run_flow.
    """

    @pytest.mark.asyncio
    async def test_rescues_run_request_only_when_classifier_says_question(self):
        # LLM (mock) returns the flaky "question" for an explicit run.
        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value={"result": '{"translation": "run the flow", "intent": "question"}'},
        ):
            for phrase in (
                "rode o flow e me diga o resultado",
                "run the flow and tell me the output",
                "roda esse flow pra mim",
                "[Session context ...]\n\nUser message: rode o flow",
            ):
                result = await classify_intent(text=phrase, global_variables={})
                assert result.intent == "run_flow", f"{phrase!r} → {result.intent}"

    @pytest.mark.asyncio
    async def test_rescues_run_request_in_any_language_via_english_translation(self):
        # Bug: the rescue ran the EN/PT-only regex on the RAW source text,
        # so a Spanish/French/German "run the flow" that the classifier
        # mis-labelled as question was NOT rescued — a language-agnostic
        # regression. The TranslationFlow already produced the English
        # translation; the detector must use THAT.
        for source, english in (
            ("ejecuta el flujo y dame el resultado", "run the flow and give me the result"),
            ("exécute le flux et montre la sortie", "execute the flow and show the output"),
            ("führe den Flow aus", "run the flow"),
            ("このフローを実行して", "run this flow"),
        ):
            with patch(
                "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
                new_callable=AsyncMock,
                return_value={"result": f'{{"translation": "{english}", "intent": "question"}}'},
            ):
                result = await classify_intent(text=source, global_variables={})
            assert result.intent == "run_flow", f"{source!r} (→ {english!r}) → {result.intent}"

    @pytest.mark.asyncio
    async def test_does_not_override_a_confident_compound_classification(self):
        # The production bug: "crie um flow … e rode esse flow" contains a
        # run phrase but the classifier confidently says component_then_flow.
        # The detector must NOT downgrade it to run_flow.
        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value={"result": '{"translation": "x", "intent": "component_then_flow"}'},
        ):
            result = await classify_intent(
                text="quero que crie um flow com um agent que identifica primos e rode esse flow",
                global_variables={},
            )
        assert result.intent == "component_then_flow", result.intent

    @pytest.mark.asyncio
    async def test_does_not_override_a_confident_build_flow_classification(self):
        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value={"result": '{"translation": "x", "intent": "build_flow"}'},
        ):
            result = await classify_intent(
                text="crie um flow com um agent e rode esse flow pra testar",
                global_variables={},
            )
        assert result.intent == "build_flow", result.intent

    @pytest.mark.asyncio
    async def test_non_run_requests_still_go_through_the_llm(self):
        mock_result = {"result": '{"translation": "build a chatbot flow", "intent": "build_flow"}'}
        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_execute:
            result = await classify_intent(text="build me a chatbot flow", global_variables={})
            assert result.intent == "build_flow"
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_flow_word_without_run_verb_is_not_forced(self):
        mock_result = {"result": '{"translation": "what does this flow do", "intent": "build_flow"}'}
        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_execute:
            result = await classify_intent(text="what does this flow do", global_variables={})
            assert result.intent == "build_flow"
            mock_execute.assert_called_once()


class TestDeterministicEditContinuation:
    """The edit-approval continuation signal must route as a flow request.

    After the user approves a man-in-the-loop edit diff card, the frontend
    sends ``EDIT_CONTINUATION_INPUT`` as a silent turn so the agent can
    finish the rest of the original request (e.g. running the flow). That
    string must deterministically classify as ``build_flow`` (a flow
    request) so it reaches the flow-builder assistant — never the flaky
    LLM, never off_topic/question.
    """

    @pytest.mark.asyncio
    async def test_continuation_signal_forces_flow_request_without_llm(self):
        from langflow.agentic.services.flow_types import EDIT_CONTINUATION_INPUT

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
        ) as mock_execute:
            result = await classify_intent(text=EDIT_CONTINUATION_INPUT, global_variables={})
            assert result.intent == "build_flow"
            assert result.translation == EDIT_CONTINUATION_INPUT
            mock_execute.assert_not_called()


class TestDeterministicPlanApproval:
    """The plan-approval continuation signal must route as a flow request.

    When the user clicks Continue on a proposed plan (manual approve or
    skip-all auto-approve), the frontend sends ``PLAN_APPROVAL_INPUT``
    verbatim so the agent proceeds to execute the plan. That string must
    deterministically classify as ``build_flow`` and MUST skip the
    TranslationFlow LLM call — same cost pattern as the edit-approval
    fast path. The classifier would route it to build_flow anyway, so the
    fast path is a pure cost win with byte-identical UX.
    """

    @pytest.mark.asyncio
    async def test_plan_approval_signal_forces_flow_request_without_llm(self):
        from langflow.agentic.services.flow_types import PLAN_APPROVAL_INPUT

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
        ) as mock_execute:
            result = await classify_intent(text=PLAN_APPROVAL_INPUT, global_variables={})
            assert result.intent == "build_flow"
            assert result.translation == PLAN_APPROVAL_INPUT
            mock_execute.assert_not_called()


class TestClassifyIntentWithContext:
    """WS-1 / RC-1: classify_intent forwards a disambiguation context block.

    The TranslationFlow only ever saw the bare user text, so follow-ups in a
    session ("add a second agent", "use the SumComponent") were classified
    as question/off_topic and the agent answered instead of acting. The
    optional ``context`` carries the session/canvas state into the
    classifier WITHOUT changing the no-context path.
    """

    @pytest.mark.asyncio
    async def test_should_send_only_text_when_context_is_none(self):
        """Regression pin: with no context the flow input is byte-identical."""
        mock_result = {"result": '{"translation": "test", "intent": "question"}'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_execute:
            await classify_intent(text="test input", global_variables={}, context=None)

            assert mock_execute.call_args[1]["input_value"] == "test input"

    @pytest.mark.asyncio
    async def test_should_include_context_in_flow_input_when_context_provided(self):
        """The context block AND the original message must reach the classifier."""
        mock_result = {"result": '{"translation": "add a second agent", "intent": "build_flow"}'}
        context = "[Session context — ...\nUser: build a chatbot\nAssistant: done\n[End of session context]"

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_execute:
            await classify_intent(
                text="adicione um segundo agente",
                global_variables={},
                context=context,
            )

            sent = mock_execute.call_args[1]["input_value"]
            assert context in sent, "Context block must be forwarded to the classifier"
            assert "adicione um segundo agente" in sent, "Original user message must still be present"

    @pytest.mark.asyncio
    async def test_should_still_parse_intent_when_context_provided(self):
        """Forwarding context must not break translation/intent parsing."""
        mock_result = {"result": '{"translation": "add a second agent", "intent": "build_flow"}'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="adicione um segundo agente",
                global_variables={},
                context="[Session context — ...]",
            )

            assert result.intent == "build_flow"
            assert result.translation == "add a second agent"


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


class TestClassifyIntentTokenUsage:
    """TranslationFlow LLM cost must be exposed to the upstream service.

    The classifier turn is one of two LLM calls per assistant turn and the
    user must see its cost. ``classify_intent`` exposes the TranslationFlow's
    token usage so the upstream assistant service can sum it with the agent's.
    """

    @pytest.mark.asyncio
    async def test_should_expose_tokens_from_translation_flow_result(self):
        translation_tokens = {"input_tokens": 11, "output_tokens": 4, "total_tokens": 15}
        mock_result = {
            "result": '{"translation": "create a component", "intent": "generate_component"}',
            "_metrics": translation_tokens,
        }

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(
                text="crie um componente",
                global_variables={},
            )

        assert result.tokens == translation_tokens

    @pytest.mark.asyncio
    async def test_should_return_none_tokens_when_translation_flow_metrics_are_missing(self):
        """Older / non-instrumented flow paths return no ``_metrics`` key — must not crash."""
        mock_result = {"result": '{"translation": "hi", "intent": "question"}'}

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(text="oi", global_variables={})

        assert result.tokens is None

    @pytest.mark.asyncio
    async def test_should_return_none_tokens_when_translation_flow_times_out(self):
        import asyncio

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError(),
        ):
            result = await classify_intent(text="hi", global_variables={})

        assert result.tokens is None

    @pytest.mark.asyncio
    async def test_should_not_leak_metrics_key_to_extract_response_text(self):
        """``_metrics`` must be consumed before extract_response_text runs.

        Otherwise the executor's internal envelope would surface as user-facing
        text via the ``str(dict)`` coercion fallback of extract_response_text.
        """
        translation_tokens = {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}
        mock_result = {
            "result": '{"translation": "hi", "intent": "question"}',
            "_metrics": translation_tokens,
        }

        with patch(
            "langflow.agentic.services.helpers.intent_classification.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await classify_intent(text="oi", global_variables={})

        # tokens captured AND removed from the dict passed to extract_response_text.
        assert result.tokens == translation_tokens
        assert "_metrics" not in mock_result, "_metrics should be popped by classify_intent"
