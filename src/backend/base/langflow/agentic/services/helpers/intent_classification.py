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
    PLAN_APPROVAL_INPUT,
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


def _with_tokens(result: IntentResult, tokens: dict[str, int] | None) -> IntentResult:
    """Attach the TranslationFlow's token usage to the IntentResult.

    Why a tiny wrapper: there are six different return points inside
    ``classify_intent`` after the LLM call (happy path + five JSON-parsing
    fallbacks). Threading tokens through ``_finalize`` would couple unrelated
    concerns (run-flow rescue vs cost accounting); a one-line attach keeps
    both rules independent and leaves the fallback paths byte-identical.
    """
    result.tokens = tokens
    return result


def _finalize(
    translation: str,
    intent: str,
    text: str,
    *,
    requested_model: str | None = None,
    requested_provider: str | None = None,
) -> IntentResult:
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

    ``requested_model`` / ``requested_provider`` are the model the user
    explicitly named (empty strings normalized to ``None``); they ride on the
    result so a downstream step can enforce it on the Agent.
    """
    rm = (requested_model or "").strip() or None
    rp = (requested_provider or "").strip() or None
    if intent == "question" and _looks_like_run_request(translation or text):
        logger.info("intent.run_flow: classifier returned question; rescued explicit run request")
        return IntentResult(translation=translation, intent="run_flow", requested_model=rm, requested_provider=rp)
    return IntentResult(translation=translation, intent=intent, requested_model=rm, requested_provider=rp)


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

    # Deterministic: the plan-approval continuation is also a backend protocol
    # string (sent verbatim by the frontend when the user clicks Continue on a
    # proposed plan or via skip-all auto-approve). It MUST route to build_flow
    # so the agent proceeds to execute the plan. Skipping TranslationFlow here
    # avoids one full LLM round-trip per approval click — pure cost win, byte-
    # identical UX (the classifier would route this to build_flow anyway).
    if text.strip() == PLAN_APPROVAL_INPUT:
        logger.info("intent.build_flow.deterministic: plan-approval continuation signal")
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

        # Consume the executor's per-run metrics BEFORE handing the dict to
        # extract_response_text — leaving ``_metrics`` in place would either
        # be silently ignored by extract_response_text (today) or, if the dict
        # falls through to ``str(result)``, leak the cost dict into the
        # user-facing text.
        translation_tokens: dict[str, int] | None = None
        if isinstance(result, dict):
            popped = result.pop("_metrics", None)
            if isinstance(popped, dict):
                translation_tokens = popped

        response_text = extract_response_text(result)
        if response_text:
            try:
                parsed = json.loads(response_text)
                translation = parsed.get("translation", text)
                intent = parsed.get("intent", "question")
                logger.debug(f"Intent: {intent}, Translation: '{translation[:50]}'")
                return _with_tokens(
                    _finalize(
                        translation,
                        intent,
                        text,
                        requested_model=parsed.get("requested_model"),
                        requested_provider=parsed.get("requested_provider"),
                    ),
                    translation_tokens,
                )
            except json.JSONDecodeError:
                # Fallback 1: JSON wrapped in markdown code block (```json ... ```)
                md_match = _MARKDOWN_JSON_RE.search(response_text)
                if md_match:
                    try:
                        parsed = json.loads(md_match.group(1).strip())
                        return _with_tokens(
                            _finalize(
                                parsed.get("translation", text),
                                parsed.get("intent", "question"),
                                text,
                                requested_model=parsed.get("requested_model"),
                                requested_provider=parsed.get("requested_provider"),
                            ),
                            translation_tokens,
                        )
                    except json.JSONDecodeError:
                        pass

                # Fallback 2: JSON embedded in surrounding text
                json_match = _EMBEDDED_JSON_RE.search(response_text)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group(0))
                        return _with_tokens(
                            _finalize(parsed.get("translation", text), parsed.get("intent", "question"), text),
                            translation_tokens,
                        )
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
                    return _with_tokens(_finalize(text, matched_intent, text), translation_tokens)

                logger.warning("Intent flow returned non-JSON, treating as question")
                return _with_tokens(_finalize(response_text, "question", text), translation_tokens)

        return _with_tokens(_finalize(text, "question", text), translation_tokens)
    except asyncio.TimeoutError:
        logger.warning(
            "intent.classification.timeout: TranslationFlow exceeded %ss, defaulting to question",
            INTENT_CLASSIFICATION_TIMEOUT_SECONDS,
        )
        return _finalize(text, "question", text)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Intent classification failed, defaulting to question: {e}")
        return _finalize(text, "question", text)
