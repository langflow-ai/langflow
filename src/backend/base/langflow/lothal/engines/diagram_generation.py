"""Diagram *generation* logic for the ARCHITECTURE stage (Story 2.1, D2 in D.2; merged in Epic E.2).

Once clarification produces a PRD, this turns that spec into the first diagram. As
of Epic D the diagram artifact is **D2 source** (https://d2lang.com): the model is
asked for a single D2 sequence diagram — participants and the messages between
them — and emits raw D2 text, no positions (D2 owns layout).

The engine returns that text on `LLMResponse.diagram_d2` and the chat endpoint
persists it to `lothal_project.diagram_d2`. `next_phase` is `None`: Epic E.2
merged generation and refinement into the single `ARCHITECTURE` stage, so after
the first draft the project stays put and the next turn refines the diagram the
user is now looking at (the `ArchitectureEngine` dispatches generate-vs-refine on
whether a diagram exists yet) rather than auto-advancing to a separate phase. The
engine never touches the DB.

This class is no longer registered directly; the `ArchitectureEngine`
(`architecture.py`) owns the `ARCHITECTURE` phase and delegates the
no-diagram-yet turn here. Epic E.3 grows generation from one diagram into the full
ADR + diagram-set artifact map.

Validation (D.3): the gate is "does the D2 compile?" — the reply is run through
the `d2` compiler with one corrective retry (the shared `d2_gate` the refinement
engine reuses). The legacy xyflow path (`diagram.py`, `diagram_json`) is
untouched — it stays for transitional reads until D.13.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.lothal.context import build_messages
from langflow.lothal.engines.d2_gate import compile_validated_d2, count_messages
from langflow.lothal.router import LLMResponse, PhaseEngine

if TYPE_CHECKING:
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


def _assistant_text(d2: str) -> str:
    """The human-facing reply stored alongside the generated D2.

    Grounded in the actual diagram (message count) so the chat reads as a real
    result, while the D2 itself rides on `LLMResponse.diagram_d2`.
    """
    messages = count_messages(d2)
    if messages:
        return (
            f"I've drafted a sequence diagram with {messages} interactions from your spec. "
            f"Review it on the canvas and tell me what to add, remove, or change."
        )
    return "I've drafted a diagram from your spec. Review it on the canvas and tell me what to add, remove, or change."


class DiagramGenerationEngine(PhaseEngine):
    """Generates the first D2 diagram from the clarified spec; the project stays in ARCHITECTURE.

    Not registered for a phase of its own (Epic E.2 merged the diagram phases) —
    the `ArchitectureEngine` delegates the first, no-diagram-yet turn here.
    """

    async def process(self, history: list[Message], user_message: str, **_kwargs) -> LLMResponse:
        # `**_kwargs` absorbs the refinement inputs (`prd`/`current_d2`, see
        # `PhaseEngine.process`); generation reads the spec from `history` and
        # starts the diagram fresh, so it ignores them.
        messages = build_messages(SYSTEM_PROMPT, history, user_message)
        d2 = await compile_validated_d2(messages)
        # next_phase=None: Epic E.2 dropped the generation→refinement auto-advance;
        # the project stays in ARCHITECTURE and the next turn refines this diagram.
        return LLMResponse(
            text=_assistant_text(d2),
            suggestions=[],
            next_phase=None,
            diagram_d2=d2,
        )
