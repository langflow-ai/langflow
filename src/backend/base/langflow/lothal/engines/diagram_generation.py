"""The `DIAGRAM_GENERATION` phase engine (Story 2.1, re-pointed to D2 in Epic D.2).

Once clarification produces a PRD, this engine turns that spec into the first
diagram. As of Epic D the diagram artifact is **D2 source** (https://d2lang.com):
the model is asked for a single D2 sequence diagram — participants and the
messages between them — and emits raw D2 text, no positions (D2 owns layout).

The engine returns that text on `LLMResponse.diagram_d2` and the chat endpoint
persists it to `lothal_project.diagram_d2`. `next_phase` stays `None` — generating
a diagram keeps the project in DIAGRAM_GENERATION; refining and approving it are
Epic D.8+. The engine never touches the DB.

Validation (D.3): the gate is "does the D2 compile?" — we run the model's reply
through the `d2` compiler (`d2_compile.compile_d2`). On a compile failure we retry
**once**, feeding the compiler's error back as a correction (the same shape as
2.1's validator-feedback retry); a second failure fails the turn as a bad model
round-trip (`LLMConnectionError` → 502). If the compiler binary is unavailable we
log and store the source unvalidated rather than break generation — the gate is
best-effort, not a hard dependency. The legacy xyflow path (`diagram.py`,
`diagram_json`) is untouched — it stays for transitional reads until D.13.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.lothal.context import build_messages
from langflow.lothal.d2_compile import D2CompilerUnavailableError, compile_d2
from langflow.lothal.engines.parsing import strip_code_fences
from langflow.lothal.llm import LLMConnectionError, call_llm
from langflow.lothal.router import LLMResponse, PhaseEngine, register_engine
from langflow.services.database.models.lothal_project.model import ProjectPhase

if TYPE_CHECKING:
    from langflow.lothal.d2_compile import D2CompileResult
    from langflow.lothal.llm.base import Message as LLMMessage
    from langflow.services.database.models.lothal_project.model import Message

# Minimum scope we ask the model for, mirrored into the prompt so the request is
# explicit. Kept local to the D2 engine (the legacy xyflow MIN_NODES/MIN_EDGES
# live in `diagram.py`).
MIN_PARTICIPANTS = 2
MIN_MESSAGES = 3

SYSTEM_PROMPT = f"""\
You are Lothal's diagram architect. The conversation so far — especially the \
product spec (PRD) — describes an application. Express its core flow as a single \
**D2 sequence diagram** (D2 is the text diagramming language at d2lang.com): the \
participants are the actors/services and the messages between them are the \
ordered interactions.

Reply with D2 source and nothing else — no markdown fences, no prose. Use \
exactly this structure:

shape: sequence_diagram
user: User
api: API
db: Database

user -> api: submit form
api -> db: insert row
db -> api: ok
api -> user: 200 OK

Rules:
- Open with `shape: sequence_diagram`.
- Declare every participant once, before its first message, as `id: Label`. \
Order them left to right by when they first take part. Use stable, lowercase, \
hyphen-free ids ("user", "api", "db"); the label is the readable name.
- Each interaction is one connection on its own line, `source -> target: label`, \
written in time order. Use `->` for a synchronous call and `-->` for an \
asynchronous message or a reply/return (dashed). Every endpoint must be a \
declared participant id.
- D2 owns layout: never write positions, coordinates, or `near`/`width`/`height`.
- Produce at least {MIN_PARTICIPANTS} participants and at least {MIN_MESSAGES} \
messages. Cover the core flow end to end; keep it focused, not exhaustive.
- Emit only valid D2 so it compiles.

Emit raw D2 only."""

# Connection operators D2 uses between participants; counted to ground the
# assistant's reply in the actual diagram without a full D2 parse.
_CONNECTION_RE = re.compile(r"<->|<-|-->|->|--")

# Fed back verbatim on the one retry so the model sees exactly what the D2
# compiler rejected and can correct it, rather than guessing (mirrors 2.1).
_RETRY_TEMPLATE = (
    "That D2 did not compile:\n{error}\n"
    "Reply again with corrected D2 source only — same structure, no commentary or fences."
)


def _count_messages(d2: str) -> int:
    """Crudely count interaction lines (those with a D2 connection operator).

    A grounding heuristic for the assistant text, not a validator: it strips a
    trailing `#` comment per line and counts lines carrying a connection arrow.
    """
    return sum(1 for line in d2.splitlines() if _CONNECTION_RE.search(line.split("#", 1)[0]))


def _assistant_text(d2: str) -> str:
    """The human-facing reply stored alongside the generated D2.

    Grounded in the actual diagram (message count) so the chat reads as a real
    result, while the D2 itself rides on `LLMResponse.diagram_d2`.
    """
    messages = _count_messages(d2)
    if messages:
        return (
            f"I've drafted a sequence diagram with {messages} interactions from your spec. "
            f"Review it on the canvas and tell me what to add, remove, or change."
        )
    return "I've drafted a diagram from your spec. Review it on the canvas and tell me what to add, remove, or change."


@register_engine
class DiagramGenerationEngine(PhaseEngine):
    """Generates the first D2 diagram from the clarified spec."""

    phase = ProjectPhase.DIAGRAM_GENERATION

    async def process(self, history: list[Message], user_message: str) -> LLMResponse:
        messages = build_messages(SYSTEM_PROMPT, history, user_message)
        d2 = await self._generate(messages)
        return LLMResponse(text=_assistant_text(d2), suggestions=[], next_phase=None, diagram_d2=d2)

    async def _generate(self, messages: list[LLMMessage]) -> str:
        """Call the model, compile-validate the D2, and retry once on failure.

        Strips any stray markdown fence and rejects an empty reply as a bad model
        round-trip (`LLMConnectionError` → 502). The reply is then run through the
        `d2` compiler: if it doesn't compile, we resend the conversation plus the
        invalid reply and the compiler's complaint so the second attempt is a
        correction rather than a blind redo. A second compile failure raises
        `LLMConnectionError` (→ 502); the user retries the turn.
        """
        raw = await call_llm(messages)
        d2 = self._extract_d2(raw)
        result = await self._compile(d2)
        if result is None or result.ok:
            return d2  # compiled, or the compiler is unavailable (gate skipped)

        retry_messages = [
            *messages,
            {"role": "assistant", "content": raw},
            {"role": "user", "content": _RETRY_TEMPLATE.format(error=result.error)},
        ]
        raw = await call_llm(retry_messages)
        d2 = self._extract_d2(raw)
        result = await self._compile(d2)
        if result is None or result.ok:
            return d2
        msg = f"Model returned D2 that failed to compile twice: {result.error}"
        raise LLMConnectionError(msg)

    @staticmethod
    def _extract_d2(raw: str) -> str:
        """Strip a stray markdown fence; reject an empty reply as a bad round-trip."""
        d2 = strip_code_fences(raw).strip()
        if not d2:
            msg = "Model returned an empty diagram."
            raise LLMConnectionError(msg)
        return d2

    @staticmethod
    async def _compile(d2: str) -> D2CompileResult | None:
        """Compile-check `d2`, returning the result — or `None` if the compiler is unavailable.

        A missing binary is an environment fault, not a verdict on the source, so
        we log and let the caller treat it as "gate skipped" (store the D2 as-is)
        rather than wrongly failing the turn or blaming the model.
        """
        try:
            return await compile_d2(d2)
        except D2CompilerUnavailableError:
            logger.warning(
                "d2 compiler unavailable; storing generated D2 without compile-validation (D.3 gate skipped)."
            )
            return None
