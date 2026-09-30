"""Tests for resolve_trusted_code_for_build (LE-1680 / CWE-345).

When LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false, the authenticated flow-build path validates each
node's code only by a 48-bit truncated hash, then execs the node's stored bytes. A second-preimage
collision against a built-in's template hash therefore yields RCE. resolve_trusted_code_for_build
closes this by substituting the server's trusted copy (keyed by the code's hash) before exec, and
failing closed when no trusted copy is known — while leaving permissive mode (the default) untouched.
"""

from types import SimpleNamespace

import pytest
from lfx.interface.initialize import loading
from lfx.services.authorization import PUBLIC_ANONYMOUS_ACTOR_ID
from lfx.utils import flow_validation
from lfx.utils.flow_validation import (
    CustomComponentValidationError,
    PublicFlowValidationError,
    resolve_trusted_code_for_build,
)


def _set_allow_custom_components(monkeypatch, *, allow: bool) -> None:
    fake = SimpleNamespace(settings=SimpleNamespace(allow_custom_components=allow))
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: fake)


def test_permissive_mode_returns_code_unchanged(monkeypatch):
    """Default mode (allow_custom_components=True): the node's own code runs, untouched."""
    _set_allow_custom_components(monkeypatch, allow=True)

    def _must_not_be_called(_code):
        pytest.fail("trusted lookup must not run in permissive mode")

    monkeypatch.setattr(flow_validation, "get_trusted_code_for_validation", _must_not_be_called)
    assert resolve_trusted_code_for_build("user-authored code") == "user-authored code"


def test_restricted_mode_substitutes_trusted_copy(monkeypatch):
    """Restricted mode + a hash match: the server's trusted source runs, not the node's bytes."""
    _set_allow_custom_components(monkeypatch, allow=False)
    monkeypatch.setattr(flow_validation, "get_trusted_code_for_validation", lambda _code: "SERVER_TRUSTED_SRC")
    # Even a forged blob that collides with a known hash resolves to the server copy.
    assert resolve_trusted_code_for_build("forged colliding blob") == "SERVER_TRUSTED_SRC"


def test_public_restricted_mode_checks_the_final_trusted_copy(monkeypatch):
    """The exact source selected immediately before eval is subject to public policy."""
    _set_allow_custom_components(monkeypatch, allow=False)
    trusted_repl = "class PythonREPLComponent(Component):\n    pass\n"
    trusted_hash = flow_validation._compute_code_hash(trusted_repl)
    monkeypatch.setattr(
        flow_validation,
        "get_trusted_code_and_hashes_for_validation",
        lambda _code: (trusted_repl, {"PythonREPLComponent": {trusted_hash}}),
    )

    with pytest.raises(PublicFlowValidationError, match="code-execution"):
        resolve_trusted_code_for_build("previously checked source", public_execution=True)


@pytest.mark.parametrize(
    ("user_id", "expected_public_execution"),
    [
        (str(PUBLIC_ANONYMOUS_ACTOR_ID), True),
        ("authenticated-owner", False),
    ],
)
def test_instantiate_class_marks_only_the_public_principal(monkeypatch, user_id, expected_public_execution):
    """The final pre-eval resolver receives the execution principal's public status."""
    seen: dict[str, object] = {}

    def resolve(code: str, *, public_execution: bool = False) -> str:
        seen.update(code=code, public_execution=public_execution)
        return "trusted source"

    class TestComponent:
        def __init__(self, **_kwargs):
            pass

    monkeypatch.setattr(flow_validation, "resolve_trusted_code_for_build", resolve)
    monkeypatch.setattr(loading, "eval_custom_component_code", lambda _code: TestComponent)
    vertex = SimpleNamespace(
        vertex_type="TestComponent",
        base_type="component",
        params={"code": "stored source"},
        id="test-component",
    )

    component, params = loading.instantiate_class(vertex, user_id=user_id)

    assert isinstance(component, TestComponent)
    assert params == {}
    assert seen == {"code": "stored source", "public_execution": expected_public_execution}


def test_restricted_mode_no_match_fails_closed(monkeypatch):
    """Restricted mode + no trusted hash match: fail closed (never fall back to client bytes)."""
    _set_allow_custom_components(monkeypatch, allow=False)
    monkeypatch.setattr(flow_validation, "get_trusted_code_for_validation", lambda _code: None)
    with pytest.raises(CustomComponentValidationError):
        resolve_trusted_code_for_build("attacker code with no trusted match")


def test_missing_settings_service_defaults_permissive(monkeypatch):
    """If settings are unavailable, mirror the module's default (allow) and run the code unchanged."""
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)

    def _fail_if_called(_code):
        pytest.fail("trusted lookup must not run when settings unavailable (permissive default)")

    monkeypatch.setattr(flow_validation, "get_trusted_code_for_validation", _fail_if_called)
    assert resolve_trusted_code_for_build("some code") == "some code"
