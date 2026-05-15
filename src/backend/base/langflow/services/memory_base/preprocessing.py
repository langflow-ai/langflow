"""LLM preprocessing for Memory Base ingestion.

Wraps a single ``LanguageModelComponent`` invocation that distills a batch of
``MessageTable`` rows into a single text output before it is written to Chroma.
The same call also acts as a deterministic gate: when the LLM emits the
configured kill phrase the batch is treated as "nothing worth ingesting" — the
ingestion task short-circuits the Chroma write but still advances the cursor
so the same batch is never re-evaluated.

Kept isolated from ``task.py`` so the LLM I/O is independently unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from lfx.base.models.model_metadata import get_provider_param_mapping
from lfx.base.models.unified_models import get_api_key_for_provider
from lfx.components.models import LanguageModelComponent

from langflow.services.memory_base.document_builders import extract_content_block_text
from langflow.services.memory_base.embedding_helpers import infer_llm_provider

if TYPE_CHECKING:
    import uuid

    from langflow.services.database.models.message.model import MessageTable


DEFAULT_KILL_PHRASE = "NO_INGEST"

# Trailing instruction injected into the user-supplied prompt so callers don't
# have to know the sentinel. Kept as a single line so the LLM treats it as a
# normal directive rather than free-form text.
_KILL_PHRASE_SUFFIX = (
    "\n\nIf this batch is not worth ingesting into long-term memory, respond with exactly: {kill_phrase}"
)


@dataclass(frozen=True, slots=True)
class PreprocessingResult:
    """Return value from :func:`run_preprocessing`.

    ``status`` is the *intent* the caller should commit to. ``"processed"`` is a
    DB state used by the ingestion task to mark a row whose Chroma write has
    not yet succeeded — it never appears here.
    """

    status: Literal["ingested", "skipped"]
    output_text: str  # Empty string when status == "skipped"
    raw_response: str  # Full unedited LLM response — preserved for logging / audit


def _build_model_config(provider: str, model_name: str) -> list[dict]:
    """Build the ``model`` input value for ``LanguageModelComponent``.

    Mirrors the helper in ``agentic.flows.translation_flow`` — promoted here so
    the memory-base layer doesn't import from agentic flows.
    """
    param_mapping = get_provider_param_mapping(provider)
    metadata: dict = {
        "api_key_param": param_mapping.get("api_key_param", "api_key"),
        "context_length": 128000,
        "model_class": param_mapping.get("model_class", "ChatOpenAI"),
        "model_name_param": param_mapping.get("model_name_param", "model"),
    }
    for extra_param in ("url_param", "project_id_param", "base_url_param"):
        if extra_param in param_mapping:
            metadata[extra_param] = param_mapping[extra_param]
    return [
        {
            "icon": provider,
            "metadata": metadata,
            "name": model_name,
            "provider": provider,
        }
    ]


def _format_batch(messages: list[MessageTable]) -> str:
    """Render a list of messages as a single prompt-friendly string."""
    parts: list[str] = []
    for m in messages:
        ts = m.timestamp.isoformat() if m.timestamp else ""
        body = (m.text or "").strip()
        cb = extract_content_block_text(m.content_blocks or [])
        if cb:
            body = f"{body}\n\n{cb}".strip() if body else cb
        if not body:
            continue
        speaker = m.sender_name or m.sender or ""
        parts.append(f"[{ts}] {speaker}:\n{body}")
    return "\n\n---\n\n".join(parts)


def is_kill_phrase(response: str, kill_phrase: str) -> bool:
    """Return True if ``response`` matches the configured kill phrase.

    Match rule: exact token, case-insensitive (``casefold``), tolerant of
    surrounding whitespace and standalone-line placement. Substring matches are
    rejected so phrases like ``"NO_INGEST_PLEASE"`` do not trigger the gate
    when ``kill_phrase = "NO_INGEST"``.
    """
    if not kill_phrase or not response:
        return False
    target = kill_phrase.strip().casefold()
    if not target:
        return False
    if response.strip().casefold() == target:
        return True
    return any(line.strip().casefold() == target for line in response.splitlines())


async def run_preprocessing(
    *,
    messages: list[MessageTable],
    preproc_model: str,
    preproc_instructions: str | None,
    kill_phrase: str,
    user_id: uuid.UUID | str | None,
) -> PreprocessingResult:
    """Run a single LLM call over ``messages`` and classify the result.

    Returns ``status="skipped"`` (and an empty ``output_text``) when the LLM
    response matches ``kill_phrase``. Otherwise returns ``status="ingested"``
    with the LLM response as ``output_text``.
    """
    if not messages:
        return PreprocessingResult(status="skipped", output_text="", raw_response="")

    provider = infer_llm_provider(preproc_model)

    # Resolve the provider's API key from the user's globally-configured
    # variables (or env). Required because we instantiate the component outside
    # a Graph, so ``self.user_id`` is unset and ``get_llm`` cannot look it up.
    api_key = get_api_key_for_provider(user_id, provider)

    llm = LanguageModelComponent()
    llm.set_input_value("model", _build_model_config(provider, preproc_model))

    system_message = preproc_instructions or ""
    if kill_phrase:
        system_message = f"{system_message}{_KILL_PHRASE_SUFFIX.format(kill_phrase=kill_phrase)}".strip()

    llm.set(
        input_value=_format_batch(messages),
        system_message=system_message,
        temperature=0.1,
        api_key=api_key,
    )

    message = await llm.text_response()
    response_text = getattr(message, "text", None) or str(message)

    if is_kill_phrase(response_text, kill_phrase):
        return PreprocessingResult(status="skipped", output_text="", raw_response=response_text)
    return PreprocessingResult(status="ingested", output_text=response_text, raw_response=response_text)
