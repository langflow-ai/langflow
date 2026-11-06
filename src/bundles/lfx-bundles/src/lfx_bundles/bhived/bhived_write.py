"""Write a lesson back to bhived."""

from __future__ import annotations

from bhived import BhivedError, DuplicateLessonError
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.bhived.bhived_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    MISSING_KEY_ERROR,
    error_text,
    make_client,
    secret_value,
)

LESSON_TYPES = ["instruction", "mistake", "update"]
TITLE_MAX_CHARS = 100


class BhivedWriteComponent(Component):
    """Write a verified lesson to bhived so other agents can find it.

    The API key decides where the lesson lands, on the server: a personal key
    publishes it to the public shared lessons, a team key keeps it private to
    the team.
    """

    display_name = "bhived Write Lesson"
    description = (
        "Share a lesson you verified with other AI agents: an approach that worked (instruction), one that "
        "fails (mistake), or a version change, deprecation or breaking change (update). Write only after you "
        "checked it, and quote error messages verbatim. With a personal bhived key the lesson is public, so "
        "never include secrets, API keys, tokens, passwords, credentials, private URLs, customer data or "
        "private code; write a general lesson, not a report about this project."
    )
    documentation = DOCUMENTATION_URL
    icon = "Bhived"
    name = "BhivedWrite"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="bhived API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        DropdownInput(
            name="lesson_type",
            display_name="Lesson Type",
            info=(
                "instruction: an approach that worked. mistake: an approach that fails, with the exact error. "
                "update: a version change, deprecation or breaking change, naming the old and new versions."
            ),
            options=LESSON_TYPES,
            value="instruction",
            tool_mode=True,
        ),
        MultilineInput(
            name="text",
            display_name="Lesson",
            info=(
                "The lesson, ideally under 350 words: stack and versions, the exact steps or error, and how it "
                "was verified. Never include secrets, credentials, customer data or private code."
            ),
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="title",
            display_name="Title",
            info=f"Short summary, at most {TITLE_MAX_CHARS} characters. Repeat its key terms in the lesson.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="query_id",
            display_name="Query ID",
            info="The query_id from a bhived search this lesson relates to. It credits the lessons that helped.",
            advanced=True,
            tool_mode=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for each request to bhived.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="write_lesson"),
    ]

    async def write_lesson(self) -> Data:
        """Write the lesson and return what happened as one ``Data``."""
        lesson_type = str(self.lesson_type or "").strip()
        text = str(self.text or "").strip()
        title = str(self.title or "").strip()
        api_key = secret_value(self.api_key)
        if lesson_type not in LESSON_TYPES:
            return self._error(f"Lesson type must be one of: {', '.join(LESSON_TYPES)}.")
        if not text or not title:
            return self._error("Enter the lesson text and a title.")
        if len(title) > TITLE_MAX_CHARS:
            return self._error(f"The title must be at most {TITLE_MAX_CHARS} characters.")
        if not api_key:
            return self._error(MISSING_KEY_ERROR)

        query_id = str(self.query_id or "").strip() or None
        try:
            async with make_client(api_key, self.timeout) as client:
                write = getattr(client, f"write_{lesson_type}")
                result = await write(text, title, query_id=query_id)
        except DuplicateLessonError as exc:
            message = "Not saved: bhived already has a near-identical lesson."
            data = Data(
                text=message,
                data={
                    "saved": False,
                    "lesson_type": lesson_type,
                    "duplicate_of": exc.duplicate_of,
                    "similarity": exc.similarity,
                },
            )
            self.status = data
            return data
        except (BhivedError, ValueError) as exc:
            return self._error(error_text(exc, api_key))

        data = Data(
            text=f"Saved {lesson_type} {result.bhived_id} ({result.action_performed}).",
            data={
                "saved": True,
                "lesson_type": lesson_type,
                "bhived_id": result.bhived_id,
                "action": result.action_performed,
                "query_id_linked": result.query_id_linked,
            },
        )
        self.status = data
        return data

    def _error(self, message: str) -> Data:
        """Log the error, show it as the component status and return it as Data."""
        logger.error(message)
        self.status = message
        return Data(text=message, data={"error": message})
