from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lfx.integrations import ScopeMissingError, normalize_integration_error
from lfx.run.base import RunError, run_flow
from lfx.services.variable.request_scope import (
    activate_no_env_fallback,
    activate_request_variables,
    get_active_request_variables,
    is_env_fallback_disabled,
    reset_no_env_fallback,
    reset_request_variables,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def outer_scope(source, raw):
    if source != "inherited_request":
        yield
        return
    scope_token = activate_request_variables({"LF_CONNECTION__GOOGLE__WORK": raw})
    no_env_token = activate_no_env_fallback(disabled=True)
    try:
        yield
    finally:
        reset_no_env_fallback(no_env_token)
        reset_request_variables(scope_token)


@pytest.mark.usefixtures("outer_scope")
@pytest.mark.parametrize("source", ["environment", "request", "inherited_request"])
@pytest.mark.parametrize(
    ("raw", "allowed"),
    [
        ('{"access_token":"probe-token","scopes":["drive.read"]}', True),
        ('{"access_token":"probe-token","scopes":["drive.write"]}', False),
        ("probe-token", False),
        ('{"access_token":"probe-token"}', False),
    ],
)
async def test_headless_execution_enforces_declared_scopes(monkeypatch, tmp_path: Path, source, raw, allowed):
    script = tmp_path / "scoped_connection.py"
    script.write_text(
        """from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom import Component
from lfx.graph import Graph
from lfx.io import ConnectionRefInput, MessageTextInput, Output
from lfx.schema.message import Message

class ScopedConnectionProbe(Component):
    inputs = [
        MessageTextInput(name="input_value"),
        ConnectionRefInput(name="connection", provider="google", required_scopes=["drive.read"]),
    ]
    outputs = [Output(name="result", display_name="Result", method="check_connection")]

    async def check_connection(self) -> Message:
        await self.resolve_connection("connection").get_token()
        return Message(text="credential accepted")

chat = ChatInput(_id="chat").set(input_value="hello")
probe = ScopedConnectionProbe(_id="probe", connection="google/work").set(input_value=chat.message_response)
output = ChatOutput(_id="output").set(input_value=probe.check_connection)
graph = Graph(start=chat, end=output)
"""
        + ('graph.context["no_env_fallback"] = True\n' if source == "request" else ""),
        encoding="utf-8",
    )
    env_key = "LF_CONNECTION__GOOGLE__WORK"
    # The request must win even when ambient credentials have sufficient scopes.
    monkeypatch.setenv(
        env_key, raw if source == "environment" else '{"access_token":"ambient","scopes":["drive.read"]}'
    )
    if source == "inherited_request":
        monkeypatch.delenv(env_key)
    variables = {env_key: raw} if source == "request" else None
    previous_scope = get_active_request_variables()
    previous_no_env = is_env_fallback_disabled()
    if allowed:
        result = await run_flow(script_path=script, check_variables=True, global_variables=variables)
        assert result["success"] is True
        assert "credential accepted" in str(result)
        assert "probe-token" not in str(result)
    else:
        with pytest.raises(RunError) as caught:
            await run_flow(script_path=script, check_variables=True, global_variables=variables)
        assert isinstance(normalize_integration_error(caught.value, provider="google"), ScopeMissingError)
        assert "probe-token" not in str(caught.value)
    assert get_active_request_variables() is previous_scope
    assert is_env_fallback_disabled() is previous_no_env
