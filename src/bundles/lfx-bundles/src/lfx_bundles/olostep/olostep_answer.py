"""Answer a question from live web sources with Olostep."""

from __future__ import annotations

import json

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.olostep.olostep_common import (
    API_KEY_INFO,
    DOCUMENTATION_URL,
    OlostepAPIError,
    olostep_request,
)

# Answers search and read several pages before replying, so they take longer than a scrape.
ANSWER_TIMEOUT_SECONDS = 120.0


def _parse_json_format(value: str) -> dict | str:
    """Send a JSON object as an object, and anything else as a plain description of the fields."""
    try:
        parsed = json.loads(value)
    except ValueError:
        return value
    return parsed if isinstance(parsed, dict) else value


class OlostepAnswerComponent(Component):
    """Answer a question with Olostep, grounded in live web pages, with sources."""

    display_name = "Olostep Answer"
    description = "Answer a question from live web sources with Olostep, with the source URLs."
    documentation = f"{DOCUMENTATION_URL}/features/answers"
    icon = "Olostep"
    name = "OlostepAnswer"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Olostep API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="task",
            display_name="Question",
            info="The question to answer from the web, such as a company's founding year or a product's price.",
            required=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="json_format",
            display_name="Output Fields",
            info=(
                "Optional. A JSON object of the fields you want, with empty values, "
                'such as {"ceo": "", "founded": ""}, or a plain description of the data you want.'
            ),
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Olostep to answer.",
            value=ANSWER_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Answer", name="answer", method="get_answer"),
    ]

    def get_answer(self) -> Data:
        """Return the answer as ``text`` and the parsed fields and sources as ``data``."""
        task = str(self.task or "").strip()
        if not task:
            error = "Enter a question."
            self.status = error
            return Data(text=error, data={"error": error})

        payload: dict[str, object] = {"task": task}
        json_format = str(self.json_format or "").strip()
        if json_format:
            payload["json_format"] = _parse_json_format(json_format)

        try:
            body = olostep_request(
                "POST",
                "/v1/answers",
                api_key=self.api_key,
                timeout=float(self.timeout or ANSWER_TIMEOUT_SECONDS),
                json=payload,
            )
        except OlostepAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})

        result = body.get("result") or {}
        raw = result.get("json_content")
        try:
            content = json.loads(raw) if isinstance(raw, str) else raw
        except ValueError:
            content = raw
        # Without output fields the API wraps the answer as {"result": "..."}.
        if isinstance(content, dict) and set(content) == {"result"}:
            text = str(content["result"] or "")
        elif isinstance(content, (dict, list)):
            text = json.dumps(content, ensure_ascii=False)
        else:
            text = str(content or "")
        if not text.strip():
            text = "Olostep found no answer to this question on the web."

        answer = Data(
            text=text,
            data={
                "id": body.get("id"),
                "answer": content,
                "sources": result.get("sources") or [],
            },
        )
        self.status = answer
        return answer
