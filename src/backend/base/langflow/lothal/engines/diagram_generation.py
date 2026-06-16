"""The `DIAGRAM_GENERATION` phase engine (Story 2.1).

Once clarification produces a PRD, this engine turns that spec into the first
**xyflow sequence diagram** — directly, with no Mermaid and no conversion step
(Lothal is xyflow end to end). The model is asked for a single JSON object in the
canonical graph shape (`{nodes, edges}`, positions included); the engine parses
it, gates it through `validate_diagram` (the shared Story 2.2 schema), and on
failure retries **once** with the validator's complaint fed back as a correction.
If the second attempt is still invalid the turn fails as a bad model round-trip
(`LLMConnectionError` → 502), so the user can simply resend.

The engine never touches the DB: it returns the validated graph on
`LLMResponse.diagram` and the chat endpoint persists it to
`lothal_project.diagram_json`. `next_phase` stays `None` — generating a diagram
keeps the project in DIAGRAM_GENERATION; refining and approving it are Epic 3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.lothal.context import build_messages
from langflow.lothal.diagram import MIN_EDGES, MIN_NODES, DiagramValidationError, validate_diagram
from langflow.lothal.engines.parsing import extract_json_object
from langflow.lothal.llm import LLMConnectionError, call_llm
from langflow.lothal.router import LLMResponse, PhaseEngine, register_engine
from langflow.services.database.models.lothal_project.model import ProjectPhase

if TYPE_CHECKING:
    from langflow.lothal.diagram import DiagramGraph
    from langflow.lothal.llm.base import Message as LLMMessage
    from langflow.services.database.models.lothal_project.model import Message

SYSTEM_PROMPT = f"""\
You are Lothal's diagram architect. The conversation so far — especially the \
product spec (PRD) — describes an application. Turn it into a single **sequence \
diagram** expressed as an xyflow graph: the participants are nodes and the \
messages between them are directed edges.

Reply with ONE JSON object and nothing else — no markdown fences, no prose — in \
exactly this shape:

{{
  "nodes": [
    {{"id": "user", "type": "actorNode", "position": {{"x": 0, "y": 0}},
     "data": {{"label": "User", "kind": "person"}}}}
  ],
  "edges": [
    {{"id": "e1", "source": "user", "target": "api", "animated": false,
     "data": {{"order": 1, "label": "submit form", "kind": "sync"}}}}
  ]
}}

Rules:
- A node is a participant. "type" is "actorNode" for a person or external system, \
or "systemNode" for a service/component you are building. "data.label" is its \
short name; optional "data.kind" is a render hint ("person" or "service").
- Give every node a "position" with numeric "x" and "y". Lay the participants out \
left to right along the top: y = 0 for all, x = 0, 240, 480, 720, … in the order \
they first take part. Positions are required.
- An edge is one message from "source" to "target" (node ids). "data.order" is \
its 1-based position in the sequence; number them 1, 2, 3, … in time order. \
"data.label" is the message ("create order", "200 OK"). "animated" is false for a \
synchronous call (solid) and true for an asynchronous message or a return/reply \
(dashed); set "data.kind" to "sync", "async", or "return" to match.
- Produce at least {MIN_NODES} nodes and at least {MIN_EDGES} edges. Cover the \
core flow end to end; keep it focused, not exhaustive.
- Use stable, lowercase, hyphen-free ids ("user", "api", "db"); every edge's \
source and target MUST be an existing node id.

Emit raw JSON only."""

# Fed back verbatim on the one retry so the model sees exactly what the schema
# rejected and can correct it, rather than guessing.
_RETRY_TEMPLATE = (
    "That diagram was rejected by the validator: {error}\n"
    "Reply again with corrected JSON only — same shape, no commentary."
)


def _assistant_text(graph: DiagramGraph) -> str:
    """The human-facing reply stored alongside the generated diagram.

    Grounded in the actual graph (participant/message counts) so the chat reads
    as a real result, while the diagram itself rides on `LLMResponse.diagram`.
    """
    return (
        f"I've drafted a sequence diagram with {len(graph.nodes)} participants and "
        f"{len(graph.edges)} interactions from your spec. Review it on the canvas and "
        f"tell me what to add, remove, or change."
    )


@register_engine
class DiagramGenerationEngine(PhaseEngine):
    """Generates the first xyflow sequence diagram from the clarified spec."""

    phase = ProjectPhase.DIAGRAM_GENERATION

    async def process(self, history: list[Message], user_message: str) -> LLMResponse:
        messages = build_messages(SYSTEM_PROMPT, history, user_message)
        graph = await self._generate(messages)
        return LLMResponse(text=_assistant_text(graph), suggestions=[], next_phase=None, diagram=graph.model_dump())

    async def _generate(self, messages: list[LLMMessage]) -> DiagramGraph:
        """Call the model and validate; on a schema failure, retry exactly once.

        The retry resends the conversation plus the model's invalid reply and the
        validator's complaint, so the second attempt is a correction rather than a
        blind redo. A second failure raises `LLMConnectionError` (a bad model
        round-trip → 502); the user retries the turn.
        """
        raw = await call_llm(messages)
        try:
            return validate_diagram(extract_json_object(raw))
        except DiagramValidationError as first_error:
            retry_messages = [
                *messages,
                {"role": "assistant", "content": raw},
                {"role": "user", "content": _RETRY_TEMPLATE.format(error=first_error)},
            ]
            raw = await call_llm(retry_messages)
            try:
                return validate_diagram(extract_json_object(raw))
            except DiagramValidationError as second_error:
                msg = f"Model returned an invalid diagram twice: {second_error}"
                raise LLMConnectionError(msg) from second_error
