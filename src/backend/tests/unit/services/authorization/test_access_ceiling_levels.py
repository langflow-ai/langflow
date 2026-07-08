"""Regression tests for the external access-ceiling action vocabulary.

These guard the deny-only ceiling levels enforced by
``langflow.services.authorization.access_ceiling`` (see PR #13293). The
editor level is expected to permit ``delete`` (a user editing their own
resources should be able to remove them) while ``deploy`` stays admin-only.
"""

from __future__ import annotations

import pytest
from langflow.services.authorization.access_ceiling import (
    ExternalAccessContext,
    external_access_allows,
    filter_actions_by_external_access_ceiling,
    set_current_external_access_context,
)

_ALL_ACTIONS = ("read", "write", "create", "delete", "execute", "ingest", "deploy")


def _ctx(level: str) -> ExternalAccessContext:
    return ExternalAccessContext(provider="openrag", subject="subject-1", level=level)


@pytest.mark.parametrize("action", ["read"])
def test_viewer_ceiling_allows_read(action: str) -> None:
    assert external_access_allows(action, _ctx("viewer")) is True


@pytest.mark.parametrize("action", ["write", "create", "delete", "execute", "ingest", "deploy"])
def test_viewer_ceiling_denies_non_read(action: str) -> None:
    assert external_access_allows(action, _ctx("viewer")) is False


@pytest.mark.parametrize("action", ["read", "write", "create", "delete", "execute", "ingest"])
def test_editor_ceiling_allows_crud_and_execute(action: str) -> None:
    # ``delete`` is included deliberately (regression for PR #13293): an editor
    # may remove their own resources.
    assert external_access_allows(action, _ctx("editor")) is True


def test_editor_ceiling_denies_deploy() -> None:
    # Deploy is intentionally reserved for admin.
    assert external_access_allows("deploy", _ctx("editor")) is False


@pytest.mark.parametrize("action", _ALL_ACTIONS)
def test_admin_ceiling_allows_everything(action: str) -> None:
    assert external_access_allows(action, _ctx("admin")) is True


@pytest.mark.parametrize("action", _ALL_ACTIONS)
def test_no_ceiling_allows_everything(action: str) -> None:
    """When no external ceiling is installed, every action is permitted."""
    assert external_access_allows(action, None) is True


def test_filter_actions_through_editor_ceiling_keeps_delete_drops_deploy() -> None:
    set_current_external_access_context(_ctx("editor"))
    try:
        kept = filter_actions_by_external_access_ceiling(["read", "delete", "deploy"])
    finally:
        set_current_external_access_context(None)
    assert kept == ["read", "delete"]
