"""Shared parity-test scaffolding for component-index and import-deferral parity tests.

Deliberately a plain module (not a pytest collector): tests import from here,
and the snapshot-generation step imports from here too. Underscore prefix keeps
pytest from attempting to collect this file as a test module.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_PARITY_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "component_index_parity"
_BENCHMARK_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "backend" / "tests" / "benchmarks" / "fixtures"
_MOCK_LLM_PATH = Path(__file__).resolve().parents[3] / "backend" / "tests" / "benchmarks" / "mock_llm.py"


def _install_mock_llm() -> bool:
    """Install BaseChatOpenAI mock from `src/backend/tests/benchmarks/mock_llm.py`. Idempotent.

    Returns True if the mock was installed, False if:
      * mock_llm.py source cannot be located (shallow clone / non-monorepo lfx checkout), or
      * langchain_openai is not installed in the current environment (lfx-only test venv).

    The False return is intentional: smallest.json parity does not require an LLM mock,
    and callers that run in the monorepo venv where langchain_openai IS available can
    still proceed even when the mock cannot be installed.
    """
    if not _MOCK_LLM_PATH.exists():
        return False
    spec = importlib.util.spec_from_file_location("_parity_mock_llm", _MOCK_LLM_PATH)
    if spec is None or spec.loader is None:
        return False
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.install_mock()
    except ModuleNotFoundError:
        # langchain_openai is not available in this environment (e.g. lfx-only venv).
        # That is expected and benign for fixtures that do not invoke an LLM.
        return False
    return True


async def _capture_parity_snapshot(fixture_path: Path, input_value: str = "hello") -> dict[str, Any]:
    """Drive a flow to completion in-process; return a (vertex_order, final_text) snapshot.

    Used by parity tests that need a deep end-to-end run, not just a smoke check.

    The Graph.async_start async-generator yields VertexBuildResult named tuples; each
    tuple has a ``result_dict`` (a ``ResultData`` pydantic model) whose ``.results`` dict
    contains a ``"message"`` key mapped to a ``Message`` object with a ``.text`` str.
    """
    from lfx.load import aload_flow_from_json
    from lfx.schema.schema import InputValueRequest

    graph = await aload_flow_from_json(fixture_path, disable_logs=True)
    inputs = InputValueRequest(input_value=input_value)
    vertex_order: list[str] = []
    final_text: str | None = None
    async for result in graph.async_start(inputs):
        vertex = getattr(result, "vertex", None)
        if vertex is None:
            # Finish sentinel or other non-vertex yield -- skip.
            continue
        vertex_order.append(vertex.id)
        if "ChatOutput" in vertex.id:
            rd = getattr(result, "result_dict", None)
            results = getattr(rd, "results", None) if rd is not None else None
            message = None
            if isinstance(results, dict):
                message = results.get("message")
            text = getattr(message, "text", None) if message is not None else None
            if text is not None:
                final_text = text
    return {"vertex_order": vertex_order, "final_text": final_text}


def _reset_component_cache_singleton(monkeypatch) -> None:
    """Zero the singleton state on both attrs so a fresh cold build is forced."""
    from lfx.interface import components as ci

    monkeypatch.setattr(ci.component_cache, "all_types_dict", None)
    monkeypatch.setattr(ci.component_cache, "_lock", None)


def _fake_settings_service():
    """Return a Mock settings service that skips custom index/cache paths."""
    from unittest.mock import Mock

    mock_settings = Mock()
    mock_settings.settings.components_index_path = None
    mock_settings.settings.lazy_load_components = False
    mock_settings.settings.components_path = []
    return mock_settings
