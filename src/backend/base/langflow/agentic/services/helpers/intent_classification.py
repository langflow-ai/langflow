"""Intent classification for assistant requests."""

import asyncio
import json
import re

from lfx.log.logger import logger

from langflow.agentic.services.flow_executor import (
    execute_flow_file,
    extract_response_text,
)
from langflow.agentic.services.flow_types import (
    EDIT_CONTINUATION_INPUT,
    TRANSLATION_FLOW,
    IntentResult,
)

# An intent call is a network round-trip to a slow, unreliable LLM. Without an
# explicit bound a hung provider stalls the whole SSE request indefinitely.
# Generous enough for a small classification call + cold starts, but finite.
INTENT_CLASSIFICATION_TIMEOUT_SECONDS = 30.0

# Pattern to extract JSON from markdown code blocks (```json ... ``` or ``` ... ```)
_MARKDOWN_JSON_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)
# Pattern to find JSON object in surrounding text
_EMBEDDED_JSON_RE = re.compile(r"\{[^{}]*\"intent\"[^{}]*\}", re.DOTALL)

# Deterministic run-flow detector. "run/execute/test the flow" is a
# high-confidence request — a flaky LLM occasionally mislabels
# "rode o flow e me diga o resultado" as a question (it also asks for the
# result), which then plan-gates and trips the no-action build guard. A
# tight "<run-verb> … flow/fluxo" pattern forces run_flow and skips the
# classifier LLM call entirely. Kept tight so "build a chat flow" / "what
# does this flow do" / "test input" are NOT captured.
_RUN_FLOW_RE = re.compile(
    r"\b(run|execute|rode|roda|rodar|executa|executar|test|testa|testar|teste)\b"
    r"[^.\n]{0,40}\b(flow|fluxo)\b",
    re.IGNORECASE,
)


def _looks_like_run_request(text: str) -> bool:
    """True when the user clearly asks to RUN/EXECUTE the existing flow.

    Matches the user message only — when a framed ``[Session context …]``
    block is present we test the part after ``User message:`` so a prior
    turn that mentioned running can't false-positive the current one.
    """
    message = text.rsplit("User message:", 1)[-1] if "User message:" in text else text
    return bool(_RUN_FLOW_RE.search(message))


def _finalize(translation: str, intent: str, text: str) -> IntentResult:
    """Apply the run-request safety net WITHOUT overriding the classifier.

    The language-agnostic TranslationFlow is the source of truth. The
    deterministic run detector now only RESCUES an explicit run request
    when the classifier fell back to ``question`` (its proven flaky
    failure mode). It must NEVER override a confident
    build_flow / component_then_flow / run_flow answer — doing so as a
    PRE-LLM short-circuit wrongly forced "create a flow with an agent …
    and run it" to run_flow (no orchestration, wrong route).

    The detector runs on the English ``translation`` (the TranslationFlow
    already produced it) so the English-only regex rescues run requests
    written in ANY language; it falls back to the raw ``text`` only on
    degraded paths where no real translation is available.
    """
    if intent == "question" and _looks_like_run_request(translation or text):
        logger.info("intent.run_flow: classifier returned question; rescued explicit run request")
        return IntentResult(translation=translation, intent="run_flow")
    return IntentResult(translation=translation, intent=intent)


async def classify_intent(
    text: str,
    global_variables: dict[str, str],
    user_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
    context: str | None = None,
) -> IntentResult:
    """Translate text to English and classify user intent using the TranslationFlow.

    The flow returns JSON with translation and intent classification.
    Returns original text with "question" intent if classification fails.

    ``context`` is an optional, pre-framed disambiguation block (built by
    ``build_intent_context``) carrying the session's recent turns and the
    current-canvas summary. When provided it is prepended to the message so
    the classifier can tell a follow-up edit ("add a second agent") from a
    new question. When ``None`` the flow input is byte-identical to the bare
    text — the no-context path is unchanged (regression-safe).

    Note: session_id is intentionally NOT accepted here. The TranslationFlow is
    stateless and must use an isolated session to avoid polluting the conversation
    memory with JSON classification output.
    """
    if not text:
        return IntentResult(translation=text, intent="question")

    # Deterministic: the edit-approval continuation is a backend protocol
    # string, not a user question. It must reach the flow-builder assistant
    # (a flow request) so the agent can finish the deferred steps — never
    # the flaky LLM, never off_topic/question.
    if text.strip() == EDIT_CONTINUATION_INPUT:
        logger.info("intent.build_flow.deterministic: edit-approval continuation signal")
        return IntentResult(translation=text, intent="build_flow")

    flow_input = f"{context}\n\nUser message: {text}" if context else text

    try:
        logger.debug("Classifying intent and translating text")
        result = await asyncio.wait_for(
            execute_flow_file(
                flow_filename=TRANSLATION_FLOW,
                input_value=flow_input,
                global_variables=global_variables,
                verbose=False,
                user_id=user_id,
                provider=provider,
                model_name=model_name,
                api_key_var=api_key_var,
            ),
            timeout=INTENT_CLASSIFICATION_TIMEOUT_SECONDS,
        )

        response_text = extract_response_text(result)
        if response_text:
            try:
                parsed = json.loads(response_text)
                translation = parsed.get("translation", text)
                intent = parsed.get("intent", "question")
                logger.debug(f"Intent: {intent}, Translation: '{translation[:50]}'")
                return _finalize(translation, intent, text)
            except json.JSONDecodeError:
                # Fallback 1: JSON wrapped in markdown code block (```json ... ```)
                md_match = _MARKDOWN_JSON_RE.search(response_text)
                if md_match:
                    try:
                        parsed = json.loads(md_match.group(1).strip())
                        return _finalize(parsed.get("translation", text), parsed.get("intent", "question"), text)
                    except json.JSONDecodeError:
                        pass

                # Fallback 2: JSON embedded in surrounding text
                json_match = _EMBEDDED_JSON_RE.search(response_text)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group(0))
                        return _finalize(parsed.get("translation", text), parsed.get("intent", "question"), text)
                    except json.JSONDecodeError:
                        pass

                # Fallback 3: look for intent as a quoted JSON value
                # Use strict patterns to avoid matching prompt-echoes
                intent_match = re.search(
                    r'["\']intent["\']\s*:\s*["\']'
                    r"(generate_component|build_flow|run_flow|component_then_flow|off_topic)[\"']",
                    response_text,
                )
                if intent_match:
                    matched_intent = intent_match.group(1)
                    logger.info("Extracted %s intent from non-JSON response via pattern match", matched_intent)
                    return _finalize(text, matched_intent, text)

                logger.warning("Intent flow returned non-JSON, treating as question")
                return _finalize(response_text, "question", text)

        return _finalize(text, "question", text)
    except asyncio.TimeoutError:
        logger.warning(
            "intent.classification.timeout: TranslationFlow exceeded %ss, defaulting to question",
            INTENT_CLASSIFICATION_TIMEOUT_SECONDS,
        )
        return _finalize(text, "question", text)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Intent classification failed, defaulting to question: {e}")
        return _finalize(text, "question", text)
