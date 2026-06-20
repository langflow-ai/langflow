"""D2 coherence validator (Epic D.10, supersedes Story 3.3's xyflow-graph validator).

The refinement engine (D.8) compile-validates every edit through the shared D.3
gate — but "it compiles" is not "it still describes the app". A diagram can be
perfectly valid D2 and yet drift from the spec: an edit that drops a participant
the PRD requires, or wires a flow the PRD rules out. This module is the *semantic*
check that compilation can't make. It asks the model whether the current D2 still
matches the application the PRD describes and turns a contradiction into one short,
user-facing warning.

It is advisory, not a gate. The edit has already been applied and stored by the
time this runs, so a validator that errors, returns nothing, or can't be reached
must never fail the turn: `validate_d2_against_prd` returns `None` (no warning) for
an empty PRD, a clean diagram, an unparseable reply, or any LLM fault, and only
returns a warning when the model clearly flags one (a reply that opens with
`WARNING`). The chat endpoint persists a returned warning as its own ASSISTANT
message (`LLMResponse.warning`); a `None` adds no message.

`call_llm` is a module-level name (not re-resolved per call) so a test can
monkeypatch the validator's model round-trip independently of the editor's
(`d2_gate.call_llm`) — the refinement turn drives both in sequence.
"""

from __future__ import annotations

import re

from lfx.log.logger import logger

from langflow.lothal.context import build_messages
from langflow.lothal.llm import call_llm

SYSTEM_PROMPT = """\
You are Lothal's diagram reviewer. You are given a product spec (PRD) and a D2 \
diagram (D2 is the text diagramming language at d2lang.com) meant to describe the \
same application. Judge only whether the diagram CONTRADICTS or materially \
misrepresents the spec — not whether it is exhaustive. A focused diagram \
legitimately leaves out detail; that is never a contradiction.

Reply with exactly one line and nothing else:
- `VALID` — the diagram is consistent with the spec.
- `WARNING: <one short sentence>` — the diagram contradicts the spec. Name the \
single most important problem: a participant or interaction the spec rules out, \
or a required one the diagram is missing. One sentence, no markdown, no preamble."""

# A reply is a warning only when its first line opens with `WARNING` as a
# standalone token — followed by `:`, whitespace, or end of line. The lookahead
# is what stops a VALID-intent reply that merely starts with the letters
# "warning" ("Warnings: none", "Warning-free", "Warningless") from misfiring as a
# garbled false alarm; anything that doesn't match is treated as "no warning".
_WARNING_RE = re.compile(r"^WARNING(?=$|[\s:])\s*:?\s*", re.IGNORECASE)


def _parse(reply: str) -> str | None:
    """Turn the reviewer's reply into a user-facing warning, or `None` when coherent.

    Only a first line whose opening token is `WARNING` raises one (the model is
    asked for a single-line verdict). The `WARNING:`/`WARNING ` marker is stripped
    and the rest of that line becomes the warning the user sees; an empty body
    falls back to a generic line so the warning is never blank.
    """
    text = reply.strip()
    if not text:
        return None
    first_line = text.splitlines()[0].strip()
    match = _WARNING_RE.match(first_line)
    if not match:
        return None
    detail = first_line[match.end() :].strip() or "the diagram may no longer match the spec."
    return f"Heads up — this edit may not match the spec: {detail}"


async def validate_d2_against_prd(prd: str | None, d2: str) -> str | None:
    """Check the edited D2 against the PRD; return a warning string, or `None` if coherent.

    Returns `None` immediately when there is no PRD or no diagram to compare. Any
    fault is swallowed (logged) and treated as "no warning": this runs inside the
    refine turn *before* the endpoint persists the edit, so a raising validator
    would roll the whole turn back — the validator is advisory and must never cost
    the user their (already compiled-and-validated) edit. The catch is broad on
    purpose: not just the typed LLM errors but any unexpected fault in the probe.
    """
    if not (prd and prd.strip()):
        return None
    if not (d2 and d2.strip()):
        return None
    turn = f"## Product spec (PRD)\n{prd.strip()}\n\n## Diagram (D2)\n{d2.strip()}"
    messages = build_messages(SYSTEM_PROMPT, [], turn)
    try:
        reply = await call_llm(messages)
        return _parse(reply)
    except Exception as exc:  # noqa: BLE001 — advisory probe must never fail the turn
        logger.warning(f"D2 coherence validator skipped (probe failed): {exc}")
        return None
