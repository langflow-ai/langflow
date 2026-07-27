"""Natural suite correctness helpers (Locust-free for unit testing)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from tests.locust.langflow_runtime.components.perf_mock_llm import PERF_MOCK_LLM_MARKER
from tests.locust.langflow_runtime.flows.defaults import FLOWS_DIR
from tests.locust.langflow_runtime.users.helpers import extract_output_text

FireCorrectness = Callable[[str, Exception | None], None]


def load_expected_rule(fixture_id: str) -> dict[str, Any]:
    index_path = FLOWS_DIR / "fixture_index.json"
    if not index_path.exists():
        return {}
    for entry in json.loads(index_path.read_text(encoding="utf-8")).get("flows", []):
        if entry.get("id") == fixture_id:
            return dict(entry.get("expected_output_rule") or {})
    return {}


def check_natural_correctness(
    *,
    shape: str,
    fixture_id: str,
    result: object,
    external_apis: str,
    fire: FireCorrectness,
    rule: dict[str, Any] | None = None,
) -> None:
    """Evaluate Natural shape output and report via ``fire(txn_name, exc|None)``."""
    text = extract_output_text(result)
    resolved = rule if rule is not None else load_expected_rule(fixture_id)
    txn = f"natural_{shape}_{external_apis}"

    if contains := resolved.get("contains"):
        if contains not in text:
            fire(txn, AssertionError(f"expected {contains!r} in {text!r}"))
            return

    if resolved.get("contains_any") and external_apis == "live":
        if not text.strip():
            fire(txn, AssertionError("empty live natural output"))
            return

    if resolved.get("retrieval") or resolved.get("retrieval_hits_min"):
        if not text.strip():
            fire(txn, AssertionError("empty retrieval output"))
            return

    if resolved.get("save_to_file"):
        needle = resolved.get("filename_contains") or "perf"
        if needle not in text and "saved" not in text.lower() and "file" not in text.lower():
            fire(txn, AssertionError(f"missing file/parser artifact in {text!r}"))
            return

    if resolved.get("chat_message_persisted"):
        if not text.strip():
            fire(txn, AssertionError("empty memory chatbot output"))
            return

    if external_apis == "stubbed":
        needles = resolved.get("contains_any") or [PERF_MOCK_LLM_MARKER]
        if not any(token in text for token in needles):
            fire(txn, AssertionError(f"missing stub marker in {text!r}"))
            return

    fire(txn, None)
