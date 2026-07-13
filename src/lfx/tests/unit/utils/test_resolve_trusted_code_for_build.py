"""Tests for resolve_trusted_code_for_build (LE-1680 / CWE-345).

When LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false, the authenticated flow-build path validates each
node's code only by a 48-bit truncated hash, then execs the node's stored bytes. A second-preimage
collision against a built-in's template hash therefore yields RCE. resolve_trusted_code_for_build
closes this by substituting the server's trusted copy (keyed by the code's hash) before exec, and
failing closed when no trusted copy is known — while leaving permissive mode (the default) untouched.
"""

from types import SimpleNamespace

import pytest
from lfx.utils import flow_validation
from lfx.utils.flow_validation import CustomComponentValidationError, resolve_trusted_code_for_build


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
