"""Tests for the fail-fast dependency preflight in `lfx run`.

The preflight runs in :func:`lfx.run.base.run_flow` (and its helper
:func:`lfx.run.base._preflight_dependencies`) *before* the graph load, so a
flow that needs an uninstalled provider package surfaces as one actionable
``pip install ...`` message instead of a deep ``ModuleNotFoundError`` mid-build.
"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import patch

import pytest
from lfx.run.base import RunError, _preflight_dependencies, run_flow

# A distribution / import name guaranteed to be absent from any environment.
_MISSING_PKG = "totally-missing-pkg-xyz123"
_MISSING_IMPORT = "totally_missing_pkg_xyz123"


def _node_with_code(code: str) -> dict:
    """Build a minimal flow node whose component `code` field is *code*."""
    return {
        "id": "node-1",
        "type": "genericNode",
        "data": {
            "id": "node-1",
            "type": "CustomComponent",
            "node": {
                "display_name": "Custom",
                "template": {"_type": "Component", "code": {"type": "code", "value": code}},
            },
        },
    }


def _flow_inner(code: str) -> dict:
    """Bare inner graph (no outer envelope)."""
    return {"nodes": [_node_with_code(code)], "edges": []}


def _flow_envelope_json(code: str) -> str:
    """Exported-flow JSON string with the ``{"data": ...}`` envelope."""
    return json.dumps({"name": "Test Flow", "data": _flow_inner(code)})


class TestRunFlowPreflight:
    @pytest.mark.asyncio
    async def test_missing_dependency_fails_fast(self):
        with pytest.raises(RunError) as exc_info:
            await run_flow(flow_json=_flow_envelope_json(f"import {_MISSING_IMPORT}"))
        message = str(exc_info.value)
        assert _MISSING_PKG in message
        assert "pip install" in message
        assert "--no-check-dependencies" in message

    @pytest.mark.asyncio
    async def test_check_dependencies_false_skips_preflight(self):
        # The flag must short-circuit the preflight entirely. The bogus flow may
        # still fail to load afterwards — that is irrelevant to this assertion.
        with patch("lfx.run.base._preflight_dependencies") as mock_preflight:
            with contextlib.suppress(RunError):
                await run_flow(
                    flow_json=_flow_envelope_json(f"import {_MISSING_IMPORT}"),
                    check_dependencies=False,
                    check_variables=False,
                )
            mock_preflight.assert_not_called()

    @pytest.mark.asyncio
    async def test_default_invokes_preflight(self):
        # Preflight is on by default; assert run_flow routes through it.
        with patch("lfx.run.base._preflight_dependencies") as mock_preflight:
            with contextlib.suppress(RunError):
                await run_flow(flow_json=_flow_envelope_json("import os"), check_variables=False)
            mock_preflight.assert_called_once()


class TestPreflightDependenciesHelper:
    def test_raises_for_missing_dep_dict(self):
        with pytest.raises(RunError) as exc_info:
            _preflight_dependencies(
                flow_dict=_flow_inner(f"import {_MISSING_IMPORT}"),
                script_path=None,
                verbose=False,
            )
        assert _MISSING_PKG in str(exc_info.value)

    def test_noop_for_stdlib_dict(self):
        # Should not raise for a stdlib-only flow.
        _preflight_dependencies(flow_dict=_flow_inner("import os"), script_path=None, verbose=False)

    def test_skips_python_script(self, tmp_path):
        # .py scripts declare deps via PEP 723, not flow analysis — preflight is a no-op.
        script = tmp_path / "flow.py"
        script.write_text(f"import {_MISSING_IMPORT}\n", encoding="utf-8")
        _preflight_dependencies(flow_dict=None, script_path=script, verbose=False)

    def test_reads_json_file_path(self, tmp_path):
        flow_file = tmp_path / "flow.json"
        flow_file.write_text(_flow_envelope_json(f"import {_MISSING_IMPORT}"), encoding="utf-8")
        with pytest.raises(RunError) as exc_info:
            _preflight_dependencies(flow_dict=None, script_path=flow_file, verbose=False)
        assert _MISSING_PKG in str(exc_info.value)

    def test_skips_unreadable_json_file(self, tmp_path):
        # Malformed JSON must fail open here (the graph loader reports it precisely later).
        bad = tmp_path / "bad.json"
        bad.write_text("{ not valid json", encoding="utf-8")
        _preflight_dependencies(flow_dict=None, script_path=bad, verbose=False)

    def test_no_source_is_noop(self):
        _preflight_dependencies(flow_dict=None, script_path=None, verbose=False)
