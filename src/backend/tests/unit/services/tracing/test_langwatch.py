"""Unit tests for the LangWatch tracer's handling of a missing ``langwatch`` package.

``langwatch`` is an optional dependency that caps ``requires-python`` at ``<3.14`` upstream,
so it is excluded from Python 3.14+ environments such as the official Langflow Docker images.
When ``LANGWATCH_API_KEY`` is set but the package cannot be imported, the tracer must disable
itself gracefully and emit a single actionable warning instead of failing silently.
"""

import sys
import uuid
from unittest.mock import patch

import pytest
from langflow.services.tracing import langwatch as langwatch_module
from langflow.services.tracing.langwatch import LangWatchTracer


@pytest.fixture(autouse=True)
def _reset_langwatch_state():
    """Reset the shared class-level state so tests don't leak into each other."""
    original_warned = LangWatchTracer._missing_dependency_warned
    original_provider = LangWatchTracer.tracer_provider
    LangWatchTracer._missing_dependency_warned = False
    LangWatchTracer.tracer_provider = None
    yield
    LangWatchTracer._missing_dependency_warned = original_warned
    LangWatchTracer.tracer_provider = original_provider


def _make_tracer() -> LangWatchTracer:
    return LangWatchTracer(
        trace_name="test flow - abc123",
        trace_type="chain",
        project_name="test",
        trace_id=uuid.uuid4(),
    )


def test_tracer_disabled_and_warns_once_when_package_missing(monkeypatch):
    """API key set + ``langwatch`` unimportable -> tracer not ready, warn exactly once.

    Forcing ``import langwatch`` to fail mirrors the Python 3.14 Docker images, where the
    package is absent. The warning must fire once even across multiple flow runs (each run
    constructs a fresh tracer).
    """
    monkeypatch.setenv("LANGWATCH_API_KEY", "test-key")  # pragma: allowlist secret
    # A ``None`` entry in ``sys.modules`` makes ``import langwatch`` raise ImportError,
    # even when the package is genuinely installed in the local (Python <3.14) test env.
    monkeypatch.setitem(sys.modules, "langwatch", None)

    with patch.object(langwatch_module.logger, "warning") as mock_warning:
        tracer1 = _make_tracer()
        tracer2 = _make_tracer()

    assert tracer1.ready is False
    assert tracer2.ready is False

    mock_warning.assert_called_once()
    message = mock_warning.call_args.args[0]
    assert "LANGWATCH_API_KEY" in message
    assert "langwatch" in message


def test_no_warning_when_api_key_not_set(monkeypatch):
    """No API key -> tracer is a silent no-op and emits no missing-package warning."""
    monkeypatch.delenv("LANGWATCH_API_KEY", raising=False)

    with patch.object(langwatch_module.logger, "warning") as mock_warning:
        tracer = _make_tracer()

    assert tracer.ready is False
    mock_warning.assert_not_called()
