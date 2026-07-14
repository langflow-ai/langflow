"""Tests for the agentic MCP server's authenticated-user binding.

The flow/component tools must derive the acting user from the server-injected
``LANGFLOW_AGENTIC_USER_ID`` env var (set by Langflow at spawn from the request identity), NOT
from a caller-supplied parameter. ``_bound_user_id`` fails closed when the env var is absent so a
server spawned without a bound identity cannot read or write any user's flows.
"""

import inspect

import pytest
from langflow.agentic.mcp.server import _bound_user_id, run_assistant
from lfx.base.mcp.security import AGENTIC_USER_ID_ENV_VAR


def test_bound_user_id_returns_env_value(monkeypatch):
    monkeypatch.setenv(AGENTIC_USER_ID_ENV_VAR, "11111111-1111-1111-1111-111111111111")
    assert _bound_user_id() == "11111111-1111-1111-1111-111111111111"


def test_bound_user_id_fails_closed_when_unset(monkeypatch):
    monkeypatch.delenv(AGENTIC_USER_ID_ENV_VAR, raising=False)
    with pytest.raises(ValueError, match="not bound to an authenticated user"):
        _bound_user_id()


def test_bound_user_id_fails_closed_when_empty(monkeypatch):
    monkeypatch.setenv(AGENTIC_USER_ID_ENV_VAR, "")
    with pytest.raises(ValueError, match="not bound to an authenticated user"):
        _bound_user_id()


def test_run_assistant_does_not_accept_caller_supplied_user_id():
    assert "user_id" not in inspect.signature(run_assistant).parameters
