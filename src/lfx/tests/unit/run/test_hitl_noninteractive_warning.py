"""Non-interactive ``lfx run`` of a pausing flow must warn, not silently mis-run (LE-1698).

Without a TTY (piped stdin, CI) or with ``--no-human-input``, the run goes through
``graph.async_start``, which never consults the pause seam: a HumanInput node does not
pause — it returns an empty message and the run continues down every branch. That is
correct-by-limitation, but it must be loud: the CLI has to tell the user the pause was
skipped and how to get the interactive behavior.
"""

from __future__ import annotations

import json

import pytest
from lfx.components.flow_controls.human_input import HumanInput
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.run.base import run_flow


def _node(component) -> dict:
    frontend = component.to_frontend_node()
    return {"id": frontend["id"], "data": frontend["data"]}


def _edge(source: str, target: str, handle: str, field: str = "input_value") -> dict:
    return {
        "source": source,
        "target": target,
        "id": f"{source}-{handle}-{target}",
        "data": {
            "sourceHandle": {"dataType": "x", "id": source, "name": handle, "output_types": ["Message"]},
            "targetHandle": {"fieldName": field, "id": target, "inputTypes": ["Message"], "type": "str"},
        },
    }


@pytest.fixture
def pausing_flow_path(tmp_path):
    payload = {
        "data": {
            "nodes": [
                _node(ChatInput(_id="chat_input")),
                _node(HumanInput(_id="hitl1")),
                _node(ChatOutput(_id="co_approve")),
                _node(ChatOutput(_id="co_reject")),
            ],
            "edges": [
                _edge("chat_input", "hitl1", "message", field="prompt"),
                _edge("hitl1", "co_approve", "branch_approve"),
                _edge("hitl1", "co_reject", "branch_reject"),
            ],
        }
    }
    path = tmp_path / "pausing_flow.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.asyncio
async def test_noninteractive_run_of_pausing_flow_warns(pausing_flow_path, capsys):
    result = await run_flow(
        script_path=pausing_flow_path,
        input_value="hello",
        check_variables=False,
        human_input=False,
    )

    assert result["success"] is True
    err = capsys.readouterr().err
    assert "Human Input" in err or "pausing" in err
    assert "--human-input" in err


@pytest.mark.asyncio
async def test_auto_detect_without_tty_also_warns(pausing_flow_path, capsys, monkeypatch):
    # Default (human_input=None) on a non-TTY stdin resolves to non-interactive; same warning.
    import sys as _sys

    monkeypatch.setattr(_sys.stdin, "isatty", lambda: False)

    result = await run_flow(
        script_path=pausing_flow_path,
        input_value="hello",
        check_variables=False,
        human_input=None,
    )

    assert result["success"] is True
    assert "--human-input" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_non_pausing_flow_does_not_warn(tmp_path, capsys):
    payload = {
        "data": {
            "nodes": [_node(ChatInput(_id="chat_input")), _node(ChatOutput(_id="chat_output"))],
            "edges": [_edge("chat_input", "chat_output", "message")],
        }
    }
    path = tmp_path / "plain_flow.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = await run_flow(
        script_path=path,
        input_value="hello",
        check_variables=False,
        human_input=False,
    )

    assert result["success"] is True
    assert "--human-input" not in capsys.readouterr().err
