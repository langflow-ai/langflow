"""Shared D2 compile-validation gate (Story D.3) for the D2 phase engines.

Both the generation engine (D.2/D.3) and the refinement engine (D.8) turn one
model round-trip into compile-validated D2 source with the *same* gate: call the
model, strip a stray markdown fence, reject an empty reply (`LLMConnectionError`
→ 502), then run the reply through the `d2` compiler and — on a compile failure —
retry **once**, feeding the compiler's own error back so the second attempt is a
correction rather than a blind redo. A second failure is a bad model round-trip
(`LLMConnectionError` → 502); a missing compiler binary is an environment fault,
not a verdict on the source, so the gate degrades to storing the D2 unvalidated.

This module is the single home of that gate so the two engines can't drift, and
of the `count_messages` heuristic both use to ground their assistant text in the
diagram's interaction count. `call_llm` and `compile_d2` are module-level names
here (not re-resolved per call) so a test can monkeypatch the gate once for
whichever engine drives it.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.lothal.d2_compile import D2CompilerUnavailableError, compile_d2
from langflow.lothal.engines.parsing import strip_code_fences
from langflow.lothal.llm import LLMConnectionError, call_llm

if TYPE_CHECKING:
    from langflow.lothal.d2_compile import D2CompileResult
    from langflow.lothal.llm.base import Message as LLMMessage

# Connection operators D2 uses between participants; counted to ground the
# assistant's reply in the actual diagram without a full D2 parse.
_CONNECTION_RE = re.compile(r"<->|<-|-->|->|--")

# Fed back verbatim on the one retry so the model sees exactly what the D2
# compiler rejected and can correct it, rather than guessing (mirrors 2.1).
_RETRY_TEMPLATE = (
    "That D2 did not compile:\n{error}\n"
    "Reply again with corrected D2 source only — same structure, no commentary or fences."
)


def count_messages(d2: str) -> int:
    """Crudely count interaction lines (those with a D2 connection operator).

    A grounding heuristic for the assistant text, not a validator: it strips a
    trailing `#` comment per line and counts lines carrying a connection arrow.
    """
    return sum(1 for line in d2.splitlines() if _CONNECTION_RE.search(line.split("#", 1)[0]))


def extract_d2(raw: str) -> str:
    """Strip a stray markdown fence; reject an empty reply as a bad round-trip."""
    d2 = strip_code_fences(raw).strip()
    if not d2:
        msg = "Model returned an empty diagram."
        raise LLMConnectionError(msg)
    return d2


async def _compile(d2: str) -> D2CompileResult | None:
    """Compile-check `d2`, returning the result — or `None` if the compiler is unavailable.

    A missing binary is an environment fault, not a verdict on the source, so we
    log and let the caller treat it as "gate skipped" (store the D2 as-is) rather
    than wrongly failing the turn or blaming the model.
    """
    try:
        return await compile_d2(d2)
    except D2CompilerUnavailableError:
        logger.warning("d2 compiler unavailable; storing D2 without compile-validation (D.3 gate skipped).")
        return None


async def compile_validated_d2(messages: list[LLMMessage]) -> str:
    """Call the model, compile-validate the returned D2, and retry once on failure.

    Strips any stray markdown fence and rejects an empty reply as a bad model
    round-trip (`LLMConnectionError` → 502). The reply is then run through the
    `d2` compiler: if it doesn't compile, we resend the conversation plus the
    invalid reply and the compiler's complaint so the second attempt is a
    correction rather than a blind redo. A second compile failure raises
    `LLMConnectionError` (→ 502); the caller's user retries the turn.
    """
    raw = await call_llm(messages)
    d2 = extract_d2(raw)
    result = await _compile(d2)
    if result is None or result.ok:
        return d2  # compiled, or the compiler is unavailable (gate skipped)

    retry_messages = [
        *messages,
        {"role": "assistant", "content": raw},
        {"role": "user", "content": _RETRY_TEMPLATE.format(error=result.error)},
    ]
    raw = await call_llm(retry_messages)
    d2 = extract_d2(raw)
    result = await _compile(d2)
    if result is None or result.ok:
        return d2
    msg = f"Model returned D2 that failed to compile twice: {result.error}"
    raise LLMConnectionError(msg)
