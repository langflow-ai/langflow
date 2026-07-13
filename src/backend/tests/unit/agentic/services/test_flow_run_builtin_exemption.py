"""Tests for the built-in component exemption in ``_scan_flow_component_code``.

Context: the agent's run-time security scanner refuses to ``exec`` any flow whose
node ``code`` field has forbidden imports/calls. The scanner was designed to
catch LLM-generated component code, but it was also flagging *built-in* Langflow
components (e.g., ``URLComponent`` uses ``importlib.util.find_spec`` for optional
dependency detection and ``os.environ.get`` for proxy config). Those built-ins
are part of the trusted code surface — the assistant adds them via the
``add_component`` tool which copies the registry's canonical template verbatim.

Rule: when a node's ``code`` is byte-identical to the registry's canonical
template for that component ``type``, skip the scan. If the code differs (user
or LLM modified it), scan as before. Registry-lookup failure must fall back to
scan-all (never trust unverified code).
"""

from __future__ import annotations

from unittest.mock import patch

from langflow.agentic.services.flow_run import _scan_flow_component_code


def _node(*, node_id: str, component_type: str, code: str) -> dict:
    """Shape a flow node the way the canvas serializer emits it."""
    return {
        "id": node_id,
        "type": "genericNode",
        "data": {
            "id": node_id,
            "type": component_type,
            "node": {"template": {"code": {"value": code}}},
        },
    }


_BUILTIN_URL_CODE = """import importlib
import os

# Built-in URLComponent uses importlib.util.find_spec for optional langflow
# detection and os.environ.get for proxy env vars — both safe in trusted code.
if importlib.util.find_spec("langflow"):
    pass

has_proxy = any((os.environ.get(key) or "").strip() for key in ("HTTPS_PROXY",))
"""

_MODIFIED_URL_CODE = (
    _BUILTIN_URL_CODE
    + """
# An LLM- or user-injected line that should still trigger the scanner.
import subprocess
subprocess.run(["echo", "bad"])
"""
)


class TestBuiltinExemption:
    def test_should_pass_when_node_code_is_byte_identical_to_canonical(self):
        # Arrange — registry exposes the canonical URLComponent code; the node
        # carries exactly that code (the agent's add_component tool copies it
        # verbatim).
        registry = {"URLComponent": {"template": {"code": {"value": _BUILTIN_URL_CODE}}}}
        payload = {
            "nodes": [_node(node_id="URLComponent-abc12", component_type="URLComponent", code=_BUILTIN_URL_CODE)]
        }

        with patch(
            "lfx.mcp.flow_builder_tools._state._load_registry_user_aware",
            return_value=registry,
        ):
            violations = _scan_flow_component_code(payload)

        # Built-in canonical code must not raise a violation, even though its
        # AST contains importlib + os.environ — those patterns are safe in
        # trusted built-in code.
        assert violations == []

    def test_should_block_when_node_code_diverges_from_canonical(self):
        # Arrange — registry says URLComponent is the safe built-in; the node
        # carries modified code that adds a forbidden subprocess call.
        registry = {"URLComponent": {"template": {"code": {"value": _BUILTIN_URL_CODE}}}}
        payload = {
            "nodes": [_node(node_id="URLComponent-xyz99", component_type="URLComponent", code=_MODIFIED_URL_CODE)],
        }

        with patch(
            "lfx.mcp.flow_builder_tools._state._load_registry_user_aware",
            return_value=registry,
        ):
            violations = _scan_flow_component_code(payload)

        # The modification (subprocess import + run) must surface so we never
        # exec code an attacker added under cover of a trusted type name.
        assert len(violations) == 1
        assert "URLComponent-xyz99" in violations[0]
        assert "subprocess" in violations[0]

    def test_should_block_unknown_component_type_when_code_has_violations(self):
        # Arrange — no registry entry for this type, so canonical lookup is
        # None and the scanner runs unchanged (treat-as-untrusted fallback).
        registry: dict = {}
        payload = {
            "nodes": [
                _node(
                    node_id="MysteryComp-1",
                    component_type="MysteryComp",
                    code="import subprocess\nsubprocess.run(['rm', '-rf', '/'])",
                ),
            ],
        }

        with patch(
            "lfx.mcp.flow_builder_tools._state._load_registry_user_aware",
            return_value=registry,
        ):
            violations = _scan_flow_component_code(payload)

        assert len(violations) == 1
        assert "subprocess" in violations[0]

    def test_should_fall_back_to_scan_all_when_registry_lookup_raises(self):
        # Arrange — registry loader explodes (ImportError, DB outage, anything).
        # The scanner must default to current behavior (scan every node) so the
        # registry-unavailable degraded path never lets unverified code through.
        payload = {
            "nodes": [
                _node(
                    node_id="URLComponent-degraded",
                    component_type="URLComponent",
                    code=_BUILTIN_URL_CODE,
                ),
            ],
        }

        with patch(
            "lfx.mcp.flow_builder_tools._state._load_registry_user_aware",
            side_effect=RuntimeError("registry not loaded"),
        ):
            violations = _scan_flow_component_code(payload)

        # With the registry unavailable we cannot prove the code is canonical,
        # so the safer choice is to scan — the built-in's importlib/os.environ
        # surfaces here. This is the degraded path, expected to be loud.
        assert len(violations) == 1
        assert "URLComponent-degraded" in violations[0]

    def test_should_treat_trivial_whitespace_drift_as_identical(self):
        # Arrange — the registry's canonical code and the node's code differ
        # only by trailing whitespace / line endings (a common serialization
        # round-trip artifact). They must compare as identical.
        registry = {"URLComponent": {"template": {"code": {"value": _BUILTIN_URL_CODE}}}}
        node_code_with_trailing = _BUILTIN_URL_CODE + "\n\n"  # extra blank lines
        payload = {
            "nodes": [
                _node(node_id="URLComponent-ws", component_type="URLComponent", code=node_code_with_trailing),
            ],
        }

        with patch(
            "lfx.mcp.flow_builder_tools._state._load_registry_user_aware",
            return_value=registry,
        ):
            violations = _scan_flow_component_code(payload)

        assert violations == []
