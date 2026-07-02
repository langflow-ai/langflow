import time

import httpx
from langchain_core.tools import StructuredTool, ToolException
from pydantic import BaseModel, Field

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.field_typing import Tool
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

try:  # packaged in the monorepo
    from lfx.components.tools.loopquest_core import build_task_body, verdict_to_string
except ImportError:  # standalone / tests
    from loopquest_core import build_task_body, verdict_to_string

DEFAULT_BASE_URL = "https://loopquest.tomphillips.uk"
GAMES = ["swiper", "versus", "sorter", "detective", "fixer", "redact", "grounding"]


class LoopQuestReviewSchema(BaseModel):
    content: str = Field(..., description="The output or decision a human should review.")
    title: str | None = Field(None, description="Optional short heading for the reviewer.")
    claim: str | None = Field(None, description="Grounding game only: the claim to verify.")
    source: str | None = Field(None, description="Grounding game only: the source text to check the claim against.")


class LoopQuestComponent(LCToolComponent):
    display_name = "LoopQuest Human Review"
    description = (
        "Send the agent's output to a human for review and wait for their verdict (approve/flag) before continuing."
    )
    icon = "LoopQuest"
    name = "LoopQuestHumanReview"
    documentation = "https://loopquest.tomphillips.uk/docs"

    inputs = [
        SecretStrInput(name="api_key", display_name="LoopQuest API Key", required=True, info="Workspaces → API keys."),
        MessageTextInput(
            name="base_url",
            display_name="Base URL",
            value=DEFAULT_BASE_URL,
            advanced=True,
            info="Only change this for a self-hosted LoopQuest deployment.",
        ),
        DropdownInput(
            name="game", display_name="Game", options=GAMES, value="swiper", info="How the reviewer sees the item."
        ),
        DropdownInput(
            name="mode",
            display_name="Mode",
            options=["gate", "monitor"],
            value="gate",
            info="Gate blocks until a human decides. Monitor creates the review and returns immediately.",
        ),
        MessageTextInput(name="content", display_name="Content", info="The item to review (used when run directly)."),
        MessageTextInput(name="title", display_name="Title", advanced=True),
        MessageTextInput(name="claim", display_name="Claim", advanced=True, info="Grounding only."),
        MessageTextInput(name="source", display_name="Source text", advanced=True, info="Grounding only."),
        IntInput(
            name="timeout_seconds",
            display_name="Gate timeout (seconds)",
            value=3600,
            advanced=True,
            info="Server-side fail-closed timeout (30–2592000). On timeout it escalates.",
        ),
        IntInput(
            name="max_wait_seconds",
            display_name="Max wait (seconds)",
            value=300,
            advanced=True,
            info="How long this component blocks polling for a verdict.",
        ),
        IntInput(name="poll_seconds", display_name="Poll interval (seconds)", value=5, advanced=True),
    ]

    def _base_url(self) -> str:
        return (self.base_url or DEFAULT_BASE_URL).rstrip("/")

    def _headers(self) -> dict:
        return {"authorization": f"Bearer {self.api_key}", "content-type": "application/json"}

    def _review(
        self, content: str, title: str | None = None, claim: str | None = None, source: str | None = None
    ) -> str:
        if not self.api_key:
            msg = "LoopQuest API Key is missing. Please configure it on the component."
            raise ToolException(msg)
        # Clamp to positive values — a 0/negative poll interval would tight-loop.
        timeout_seconds = max(1, int(self.timeout_seconds or 3600))
        max_wait = max(1, int(self.max_wait_seconds or 300))
        poll = max(1, int(self.poll_seconds or 5))
        mode = self.mode or "gate"
        body = build_task_body(
            content=content,
            module=self.game or "swiper",
            mode=mode,
            title=title,
            claim=claim,
            source=source,
            timeout_seconds=timeout_seconds,
            on_timeout="escalate",
            review_source="langflow",
        )
        base = self._base_url()
        headers = self._headers()
        try:
            created = httpx.post(f"{base}/api/v1/tasks", json=body, headers=headers, timeout=30)
            created.raise_for_status()
            task_id = created.json().get("id")
            if not task_id:
                return "Failed to create the review task."
            if mode != "gate":
                return f"Review task {task_id} created (monitor mode) — not waiting for a verdict."

            deadline = time.monotonic() + max_wait
            while time.monotonic() < deadline:
                time.sleep(poll)
                try:
                    res = httpx.get(f"{base}/api/v1/tasks/{task_id}", headers=headers, timeout=30)
                    res.raise_for_status()
                    verdict = verdict_to_string(res.json())
                    if verdict:
                        self.status = verdict
                        return verdict
                except httpx.HTTPError:
                    logger.debug("Transient error polling LoopQuest task %s", task_id, exc_info=True)
            return "No human verdict within the wait window — treat as NOT approved (fail closed)."
        except httpx.HTTPError as exc:
            msg = f"Error contacting LoopQuest: {exc}"
            raise ToolException(msg) from exc

    def run_model(self) -> list[Data]:
        verdict = self._review(self.content, self.title, self.claim, self.source)
        self.status = verdict
        return [Data(data={"result": verdict})]

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="request_human_review",
            description=(
                "Send content to a human reviewer and wait for their verdict. "
                "Use before any consequential or irreversible action."
            ),
            func=self._review,
            args_schema=LoopQuestReviewSchema,
        )
