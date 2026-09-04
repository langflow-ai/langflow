"""Regression tests for KB path traversal via username (CVE-2026-33186).

KB directory paths are built from the owner's ``username``, and the guard
previously only checked that ``kb_name`` stayed within the username-derived
base — never that the username-derived base stayed within the KB root. A
username containing ``..`` therefore escaped the root, enabling
arbitrary-directory access / deletion across the read / update / delete /
ingest / query routes (and the JWT-secret directory). Containment is now
checked against the real root first, then the user directory.

Path construction has since moved behind ``_resolve_kb_store_path``, which is
also the only place a local path is built at all — and only for local Chroma.
The guard is exercised there; the remote-backend case is covered too, since a
backend that resolves no path cannot be traversed.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from langflow.api.v1 import knowledge_bases
from langflow.api.v1.knowledge_bases import _resolve_kb_store_path


@pytest.fixture
def kb_root(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge_bases.KBStorageHelper, "get_root_path", lambda: tmp_path)
    return tmp_path


def _resolve(kb_name: str, owner, *, backend_type: str = "chroma", backend_config: dict | None = None):
    return _resolve_kb_store_path(
        kb_name,
        owner,
        backend_type=backend_type,
        backend_config=backend_config or {},
    )


@pytest.mark.usefixtures("kb_root")
def test_username_traversal_blocked():
    """A username with '..' must not escape the KB root."""
    owner = SimpleNamespace(username="../../etc")
    with pytest.raises(HTTPException) as exc:
        _resolve("cron.d", owner)
    assert exc.value.status_code == 403


@pytest.mark.usefixtures("kb_root")
def test_username_with_separator_blocked():
    owner = SimpleNamespace(username="../victim")
    with pytest.raises(HTTPException) as exc:
        _resolve("evil", owner)
    assert exc.value.status_code == 403


@pytest.mark.usefixtures("kb_root")
def test_kbname_traversal_still_blocked():
    """The pre-existing kb_name traversal guard is preserved."""
    owner = SimpleNamespace(username="alice")
    with pytest.raises(HTTPException) as exc:
        _resolve("../bob/secret", owner)
    assert exc.value.status_code == 403


def test_contained_path_allowed(kb_root):
    """A normal username + kb_name resolves without error.

    No directory is created first: Chroma makes its own on first write, so a KB
    that exists (as a row) but has never been ingested into legitimately has none.
    """
    owner = SimpleNamespace(username="alice")
    assert _resolve("mykb", owner) == (kb_root / "alice" / "mykb").resolve()


@pytest.mark.usefixtures("kb_root")
@pytest.mark.parametrize(
    ("backend_type", "backend_config"),
    [("opensearch", {}), ("postgres", {}), ("chroma", {"mode": "cloud"})],
)
def test_remote_backends_build_no_path_to_traverse(backend_type, backend_config):
    """Traversal is unreachable for remote backends — no path is constructed at all."""
    owner = SimpleNamespace(username="../../etc")
    assert _resolve("cron.d", owner, backend_type=backend_type, backend_config=backend_config) is None
