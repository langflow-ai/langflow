"""Intent classification for assistant requests."""

import json
import re

from lfx.log.logger import logger

from langflow.agentic.services.flow_executor import (
    execute_flow_file,
    extract_response_text,
)
from langflow.agentic.services.flow_types import (
    TRANSLATION_FLOW,
    IntentResult,
)

# Pattern to extract JSON from markdown code blocks (```json ... ``` or ``` ... ```)
_MARKDOWN_JSON_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)
# Pattern to find JSON object in surrounding text
_EMBEDDED_JSON_RE = re.compile(r"\{[^{}]*\"intent\"[^{}]*\}", re.DOTALL)


async def classify_intent(
    text: str,
    global_variables: dict[str, str],
    user_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> IntentResult:
    """Translate text to English and classify user intent using the TranslationFlow.

    The flow returns JSON with translation and intent classification.
    Returns original text with "question" intent if classification fails.

    Note: session_id is intentionally NOT accepted here. The TranslationFlow is
    stateless and must use an isolated session to avoid polluting the conversation
    memory with JSON classification output.
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
                logger.debug(f"Intent: {intent}, Translation: '{translation[:50]}'")
                return IntentResult(translation=translation, intent=intent)
            except json.JSONDecodeError:
                # Fallback 1: JSON wrapped in markdown code block (```json ... ```)
                md_match = _MARKDOWN_JSON_RE.search(response_text)
                if md_match:
                    try:
                        parsed = json.loads(md_match.group(1).strip())
                        return IntentResult(
                            translation=parsed.get("translation", text),
                            intent=parsed.get("intent", "question"),
                        )
                    except json.JSONDecodeError:
                        pass

                # Fallback 2: JSON embedded in surrounding text
                json_match = _EMBEDDED_JSON_RE.search(response_text)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group(0))
                        return IntentResult(
                            translation=parsed.get("translation", text),
                            intent=parsed.get("intent", "question"),
                        )
                    except json.JSONDecodeError:
                        pass

                # Fallback 3: plain text mentioning known intents
                if "generate_component" in response_text:
                    logger.info("Extracted generate_component intent from non-JSON response")
                    return IntentResult(translation=text, intent="generate_component")

                if "off_topic" in response_text:
                    logger.info("Extracted off_topic intent from non-JSON response")
                    return IntentResult(translation=text, intent="off_topic")

                logger.warning("Intent flow returned non-JSON, treating as question")
                return IntentResult(translation=response_text, intent="question")

        return IntentResult(translation=text, intent="question")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Intent classification failed, defaulting to question: {e}")
        return IntentResult(translation=text, intent="question")
