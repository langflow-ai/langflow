"""B1 — `_force_isolation` flag on FileSystemToolComponent.

The agentic API surface (files_router, the agent's write tools) carries an
authenticated user_id and must always resolve a per-user sandbox root —
even when ``AUTO_LOGIN=True``. Today ``_validate_root`` returns the shared
root whenever AUTO_LOGIN is True, so two distinct users in a multi-user
deployment running default auth resolve to the same root and can read each
other's files. The new ``_force_isolation`` flag closes that gap without
changing default behavior for any other caller (default False).

Cross-platform: only ``pathlib`` and a tmp_path fixture — no POSIX paths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

if TYPE_CHECKING:
    from pathlib import Path


def _make_component(
    *,
    monkeypatch: pytest.MonkeyPatch,
    base_dir: Path,
    auto_login: bool,
    user_id: str | None = None,
    force_isolation: bool = False,
    sub_path: str = "",
) -> FileSystemToolComponent:
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(base_dir))
    component = FileSystemToolComponent(root_path=sub_path)
    component._resolve_auto_login = lambda: auto_login  # type: ignore[method-assign]
    if user_id is not None:
        component._user_id = user_id
    if force_isolation:
        component._force_isolation = True
    return component


class TestForceIsolationOverridesAutoLogin:
    """The flag forces the per-user root even under AUTO_LOGIN=True."""

    def test_should_write_to_per_user_root_when_force_isolation_and_auto_login_true(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=True,
            user_id="user-alice",
            force_isolation=True,
        )

        result = component._write_file("notes.md", "hello")

        assert result.get("status") in {"created", "updated"}, result
        # The file must NOT land in the shared root.
        assert not (base / "shared" / "notes.md").exists()
        # It must land under users/<hash(alice)>/.
        users_root = base / "users"
        assert users_root.exists(), "users/ namespace should be materialized"
        candidates = list(users_root.glob("*/notes.md"))
        assert len(candidates) == 1, candidates
        assert candidates[0].read_text(encoding="utf-8") == "hello"

    def test_should_isolate_two_users_under_auto_login_when_force_isolation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"
        alice = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=True,
            user_id="user-alice",
            force_isolation=True,
        )
        bob = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=True,
            user_id="user-bob",
            force_isolation=True,
        )

        alice._write_file("secret.md", "alice-owned")
        bob_path_resolved = bob._validate_path("secret.md")
        alice_path_resolved = alice._validate_path("secret.md")

        # Different physical files = isolation holds even under AUTO_LOGIN.
        assert bob_path_resolved != alice_path_resolved
        assert not bob_path_resolved.exists(), "bob must not see alice's file"
        assert alice_path_resolved.read_text(encoding="utf-8") == "alice-owned"

    def test_should_raise_permission_error_when_force_isolation_without_user_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=True,
            user_id=None,
            force_isolation=True,
        )

        with pytest.raises(PermissionError, match="requires an authenticated user"):
            component._validate_root()


class TestDefaultBehaviorUnchanged:
    """No flag set ⇒ AUTO_LOGIN dispatch is unchanged — backward compat."""

    def test_should_use_shared_root_when_force_isolation_default_and_auto_login_true(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=True,
            user_id="user-alice",
            force_isolation=False,
        )

        component._write_file("notes.md", "hello")

        assert (base / "shared" / "notes.md").read_text(encoding="utf-8") == "hello"
        assert not (base / "users").exists() or not list((base / "users").glob("*"))
