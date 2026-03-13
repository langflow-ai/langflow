"""Intent classification for assistant requests."""

import json

from lfx.log.logger import logger

from langflow.agentic.services.flow_executor import (
    execute_flow_file,
    extract_response_text,
)
from langflow.agentic.services.flow_types import (
    TRANSLATION_FLOW,
    IntentResult,
)


async def classify_intent(
    text: str,
    global_variables: dict[str, str],
    user_id: str | None = None,
    session_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> IntentResult:
    """Translate text to English and classify user intent using the TranslationFlow.

    The flow returns JSON with translation and intent classification.
    Returns original text with "question" intent if classification fails.
    """
    if not text:
        return IntentResult(translation=text, intent="question")

    try:
        logger.debug("Classifying intent and translating text")
        result = await execute_flow_file(
            flow_filename=TRANSLATION_FLOW,
            input_value=text,
            global_variables=global_variables,
            verbose=False,
            user_id=user_id,
            session_id=session_id,
            provider=provider,
            model_name=model_name,
            api_key_var=api_key_var,
        )

        response_text = extract_response_text(result)
        if response_text:
            try:
                parsed = json.loads(response_text)
                translation = parsed.get("translation", text)
                intent = parsed.get("intent", "question")
                logger.debug("Intent: %s, translation_length=%d", intent, len(translation))
                return IntentResult(translation=translation, intent=intent)
            except json.JSONDecodeError:
                logger.warning("Intent flow returned non-JSON, treating as question")
                return IntentResult(translation=response_text, intent="question")

        return IntentResult(translation=text, intent="question")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Intent classification failed, defaulting to question: {e}")
        return IntentResult(translation=text, intent="question")
