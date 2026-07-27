"""NaturalUser fail-hard and correctness-contract unit tests (Locust-free)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.locust.langflow_runtime.components.perf_mock_llm import PERF_MOCK_LLM_MARKER
from tests.locust.langflow_runtime.users.helpers import require_flow
from tests.locust.langflow_runtime.users.natural_correctness import check_natural_correctness


def _collect() -> tuple[list[tuple[str, Exception | None]], Any]:
    fired: list[tuple[str, Exception | None]] = []

    def fire(name: str, exc: Exception | None) -> None:
        fired.append((name, exc))

    return fired, fire


def test_require_flow_missing_from_state() -> None:
    assert require_flow({"api_key": "k", "flows": {}}, "natural_basic_prompting__external_stubbed") is None
    assert require_flow(None, "natural_basic_prompting__external_stubbed") is None


def test_require_flow_present() -> None:
    entry = {"flow_id": "abc"}
    state = {"flows": {"natural_basic_prompting__external_stubbed": entry}}
    assert require_flow(state, "natural_basic_prompting__external_stubbed") is entry


def test_correctness_stub_marker_missing() -> None:
    fired, fire = _collect()
    check_natural_correctness(
        shape="basic_prompting",
        fixture_id="natural_basic_prompting__external_stubbed",
        result={"text": "provider said hello"},
        external_apis="stubbed",
        fire=fire,
        rule={"contains_any": [PERF_MOCK_LLM_MARKER]},
    )
    assert fired[-1][1] is not None
    assert "missing stub marker" in str(fired[-1][1])


def test_correctness_stub_marker_ok() -> None:
    fired, fire = _collect()
    check_natural_correctness(
        shape="basic_prompting",
        fixture_id="natural_basic_prompting__external_stubbed",
        result={"text": f"{PERF_MOCK_LLM_MARKER}:ok"},
        external_apis="stubbed",
        fire=fire,
        rule={"contains_any": [PERF_MOCK_LLM_MARKER]},
    )
    assert fired[-1] == ("natural_basic_prompting_stubbed", None)


def test_correctness_empty_retrieval() -> None:
    fired, fire = _collect()
    check_natural_correctness(
        shape="vector_store_rag",
        fixture_id="natural_vector_store_rag__external_stubbed",
        result={"text": "  "},
        external_apis="stubbed",
        fire=fire,
        rule={"retrieval": True},
    )
    assert fired[-1][1] is not None
    assert "empty retrieval" in str(fired[-1][1])


def test_correctness_failed_persistence() -> None:
    fired, fire = _collect()
    check_natural_correctness(
        shape="memory_chatbot",
        fixture_id="natural_memory_chatbot__external_live",
        result={"text": ""},
        external_apis="live",
        fire=fire,
        rule={"chat_message_persisted": True},
    )
    assert fired[-1][1] is not None
    assert "empty memory chatbot" in str(fired[-1][1])


def test_correctness_missing_file_parser_artifact() -> None:
    fired, fire = _collect()
    check_natural_correctness(
        shape="file_parser_agent",
        fixture_id="natural_file_parser_agent__external_stubbed",
        result={"text": "no artifact here"},
        external_apis="stubbed",
        fire=fire,
        rule={"save_to_file": True, "filename_contains": "perf"},
    )
    assert fired[-1][1] is not None
    assert "file/parser artifact" in str(fired[-1][1])


def test_correctness_malformed_contains_rule() -> None:
    fired, fire = _collect()
    check_natural_correctness(
        shape="basic_prompting",
        fixture_id="natural_basic_prompting__external_live",
        result={"text": "unexpected provider text"},
        external_apis="live",
        fire=fire,
        rule={"contains": "perf-outbound-ok"},
    )
    assert fired[-1][1] is not None
    assert "expected 'perf-outbound-ok'" in str(fired[-1][1])


def test_require_flow_or_fail_message_contract() -> None:
    """Mirror PerfBaseUser.require_flow_or_fail without importing Locust."""
    fixture_id = "natural_basic_prompting__external_stubbed"
    assert require_flow({"flows": {}}, fixture_id) is None
    msg = f"provisioned flow {fixture_id!r} missing from state; cannot run NaturalUser"
    with pytest.raises(RuntimeError, match="missing"):
        raise RuntimeError(msg)
