"""Regression tests for KB path traversal via username (CVE-2026-33186).

``_resolve_kb_path`` and ``create_knowledge_base`` build the KB directory from the owner's
``username`` and previously only checked that ``kb_name`` stayed within the username-derived
base — never that the username-derived base stayed within the KB root. A username containing
``..`` therefore escaped the root, enabling arbitrary-directory access / deletion across the
read / update / delete / ingest / query routes (and the JWT-secret directory). Both paths now
check containment against the real root first, matching the list endpoint's guard.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from langflow.api.v1 import knowledge_bases
from langflow.api.v1.knowledge_bases import _resolve_kb_path


@pytest.fixture
def kb_root(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge_bases.KBStorageHelper, "get_root_path", lambda: tmp_path)
    return tmp_path


@pytest.mark.usefixtures("kb_root")
def test_username_traversal_blocked():
    """A username with '..' must not escape the KB root."""
    owner = SimpleNamespace(username="../../etc")
    with pytest.raises(HTTPException) as exc:
        _resolve_kb_path("cron.d", owner)
    assert exc.value.status_code == 403


@pytest.mark.usefixtures("kb_root")
def test_username_with_separator_blocked():
    owner = SimpleNamespace(username="../victim")
    with pytest.raises(HTTPException) as exc:
        _resolve_kb_path("evil", owner)
    assert exc.value.status_code == 403


@pytest.mark.usefixtures("kb_root")
def test_kbname_traversal_still_blocked():
    """The pre-existing kb_name traversal guard is preserved."""
    owner = SimpleNamespace(username="alice")
    with pytest.raises(HTTPException) as exc:
        _resolve_kb_path("../bob/secret", owner)
    assert exc.value.status_code == 403


def test_contained_path_allowed(kb_root):
    """A normal username + kb_name resolves without error."""
    owner = SimpleNamespace(username="alice")
    (kb_root / "alice" / "mykb").mkdir(parents=True)
    resolved = _resolve_kb_path("mykb", owner)
    assert resolved == (kb_root / "alice" / "mykb").resolve()
