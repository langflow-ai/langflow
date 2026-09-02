"""Every ``lfx serve`` launch path must start each request task from a clean context.

A request that arrives while another is still in flight on the same connection is queued as a
pipelined request, and uvicorn starts it from inside the finishing request's task
(``httptools_impl.on_response_complete`` -> ``_start_asgi_task``). ``create_task`` copies the
context, so without ``reset_contextvars`` the new request begins with the previous request's
already-ended server span still current. OpenTelemetry's ASGI middleware reads that as nesting
and emits the request as an INTERNAL child of an unrelated finished request rather than as a
SERVER root, merging unrelated traces and hiding most HTTP traffic from RED metrics.

langflow set the flag on both of its launch paths; lfx serve has three and had none of them,
so the same defect stayed live on the runtime that actually serves traffic. These tests cover
all three, and the source-level one covers a fourth if anyone adds it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import lfx.cli.commands
import pytest
import uvicorn

pytest.importorskip("gunicorn", reason="the gunicorn worker path is Unix-only")


def test_the_gunicorn_worker_resets_the_context_and_keeps_its_inherited_options():
    """Asserted through a real ``uvicorn.Config``, so a renamed or rejected option fails here.

    The inherited keys matter too: ``CONFIG_KWARGS`` is spread over the base class's, and
    replacing it outright would silently drop uvicorn's loop and http selection.
    """
    from lfx.cli.serve_gunicorn import LFXUvicornWorker
    from uvicorn.workers import UvicornWorker

    config = uvicorn.Config("lfx.cli.serve_app:create_serve_app", **LFXUvicornWorker.CONFIG_KWARGS)

    assert config.reset_contextvars is True
    for key, value in UvicornWorker.CONFIG_KWARGS.items():
        assert LFXUvicornWorker.CONFIG_KWARGS[key] == value, f"dropped inherited {key}"


def _uvicorn_run_calls() -> list[ast.Call]:
    source = Path(lfx.cli.commands.__file__).read_text(encoding="utf-8")
    return [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "uvicorn"
    ]


def test_every_uvicorn_launch_in_the_serve_command_resets_the_context():
    """Read from the source rather than by starting a server or patching ``uvicorn.run``.

    This is the guard that would have caught the original gap. Both call sites are literal
    kwargs, and a new launch path added later fails here until it opts in too.
    """
    calls = _uvicorn_run_calls()
    assert len(calls) >= 2, "expected the single-worker and Windows multi-worker launches"

    for call in calls:
        passed = {kw.arg: kw.value for kw in call.keywords}
        assert "reset_contextvars" in passed, f"uvicorn.run at line {call.lineno} does not reset the context"
        value = passed["reset_contextvars"]
        assert isinstance(value, ast.Constant), (
            f"uvicorn.run at line {call.lineno} passes a non-literal reset_contextvars={ast.unparse(value)}"
        )
        assert value.value is True, f"uvicorn.run at line {call.lineno} passes reset_contextvars={value.value!r}"
