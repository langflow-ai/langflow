"""Shared helpers for the split authorization-helper tests.

After the ``utils.py`` refactor on PR #13153, the runtime helpers live in
three modules:

* ``langflow.services.authorization.audit``   — batched audit pipeline
* ``langflow.services.authorization.guards``  — ``ensure_*_permission`` family
* ``langflow.services.authorization.listing`` — ``filter_visible_resources``

Each module imports ``get_settings_service`` / ``get_authorization_service``
at import time, so a test that wants to stub the live services must patch the
attributes on *every* module that uses them. This file centralises the
patching shape so individual test files stay focused.

Pytest fixtures (``fake_user``, ``fake_superuser``) live in
``conftest.py`` so they are discovered automatically without per-file imports.
"""

from __future__ import annotations

from types import SimpleNamespace

from langflow.services.authorization import audit as authz_audit
from langflow.services.authorization import guards as authz_guards
from langflow.services.authorization import listing as authz_listing


class _StubAuthorizationService:
    """Minimal stand-in for BaseAuthorizationService that records calls."""

    def __init__(self, *, allow: bool = True, batch_results: list[bool] | None = None) -> None:
        self.allow = allow
        self.batch_results = batch_results
        self.calls: list[dict] = []
        self.batch_calls: list[dict] = []

    async def enforce(self, **kwargs) -> bool:
        self.calls.append(kwargs)
        return self.allow

    async def batch_enforce(self, **kwargs) -> list[bool]:
        self.batch_calls.append(kwargs)
        if self.batch_results is not None:
            return self.batch_results
        return [self.allow] * len(kwargs.get("requests", []))


def install_settings(monkeypatch, *, authz_enabled: bool, audit_enabled: bool = False) -> None:
    """Patch settings on every module that calls ``get_settings_service``."""
    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=authz_enabled,
            AUTHZ_AUDIT_ENABLED=audit_enabled,
        ),
    )
    for module in (authz_audit, authz_guards, authz_listing):
        monkeypatch.setattr(module, "get_settings_service", lambda s=settings: s)


def install_authz(monkeypatch, service: _StubAuthorizationService) -> None:
    """Patch the authorization service factory on guards + listing."""
    for module in (authz_guards, authz_listing):
        monkeypatch.setattr(module, "get_authorization_service", lambda s=service: s)


def install_audit_recorder(monkeypatch) -> list[dict]:
    """Replace ``audit_decision`` with a recorder so tests can assert audit writes.

    ``ensure_permission`` in ``guards`` reaches for ``audit.audit_decision``
    via the module reference (``from ... import audit as _audit``), so patching
    the function attribute on the ``audit`` module is sufficient — every caller
    sees the recorder.
    """
    calls: list[dict] = []

    async def _recorder(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(authz_audit, "audit_decision", _recorder)
    return calls
