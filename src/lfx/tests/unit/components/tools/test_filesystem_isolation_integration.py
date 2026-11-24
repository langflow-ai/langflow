"""End-to-end integration tests for AUTO_LOGIN-driven isolation in FileSystemToolComponent.

The dispatch table:

    AUTO_LOGIN=True             → <BASE>/shared/<sub_path>/...
    AUTO_LOGIN=False + user     → <BASE>/users/<hash(user_id)>/<sub_path>/...
    AUTO_LOGIN=False + no user  → structured error

Threats covered:
    T1 — User B reads user A's files via the same flow
    T2 — Anonymous run in multi-user mode (AUTO_LOGIN=False without user)
    T3 — Sub-path traversal attempts in either mode
    T4 — `.lfsig` reserved tree
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
    sub_path: str = "",
    read_only: bool = False,
) -> FileSystemToolComponent:
    """Build a component with the AUTO_LOGIN flag pinned for the test."""
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(base_dir))

    component = FileSystemToolComponent(root_path=sub_path, read_only=read_only)
    # Per-instance override avoids pulling in the global settings service.
    component._resolve_auto_login = lambda: auto_login  # type: ignore[method-assign]
    if user_id is not None:
        component._user_id = user_id
    return component


class TestSharedModeWhenAutoLoginTrue:
    """Slice S3 — AUTO_LOGIN=True puts every file under <BASE>/shared/<sub>."""

    def test_should_create_files_inside_shared_namespace(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        base = tmp_path / "base"
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=True,
            sub_path="",
        )

        write_result = component._write_file("notes.md", "hello")

        assert write_result.get("status") in {"created", "updated"}, write_result
        assert (base / "shared" / "notes.md").read_text(encoding="utf-8") == "hello"

    def test_should_treat_root_path_as_subpath_under_shared(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=True,
            sub_path="projects/demo",
        )

        write_result = component._write_file("notes.md", "demo")

        assert write_result.get("status") in {"created", "updated"}, write_result
        assert (base / "shared" / "projects" / "demo" / "notes.md").exists()

    def test_should_not_create_users_directory_in_shared_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=True,
            user_id="user-ignored",
            sub_path="",
        )

        component._write_file("doc.txt", "x")

        # When AUTO_LOGIN=True we must not leak a users/ tree even if a
        # user_id happens to be available — that would mix the two layouts.
        assert not (base / "users").exists()

    def test_should_serve_anonymous_calls_in_shared_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # AUTO_LOGIN=True implies a single trusted operator; the absence of a
        # user_id is the norm, not an error.
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=tmp_path / "base",
            auto_login=True,
            user_id=None,
        )

        result = component._write_file("hello.txt", "ok")

        assert result.get("status") in {"created", "updated"}, result


class TestIsolatedModeWhenAutoLoginFalse:
    """Slice S4 — AUTO_LOGIN=False scopes every call under <BASE>/users/<hash>/."""

    def test_should_create_files_inside_user_namespace(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        base = tmp_path / "base"
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=False,
            user_id="user-alice",
            sub_path="",
        )

        write_result = component._write_file("notes.md", "hello")

        assert write_result.get("status") in {"created", "updated"}, write_result
        users_dir = base / "users"
        assert users_dir.exists()
        user_subdirs = list(users_dir.iterdir())
        assert len(user_subdirs) == 1
        assert (user_subdirs[0] / "notes.md").read_text(encoding="utf-8") == "hello"

    def test_should_treat_root_path_as_subpath_under_user_namespace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=False,
            user_id="user-alice",
            sub_path="projects/demo",
        )

        write_result = component._write_file("notes.md", "demo")

        assert write_result.get("status") in {"created", "updated"}, write_result
        user_subdirs = list((base / "users").iterdir())
        assert (user_subdirs[0] / "projects" / "demo" / "notes.md").exists()


class TestRefusesAnonymousWhenAutoLoginFalse:
    """Slice S5 — AUTO_LOGIN=False without user_id must fail closed."""

    @pytest.mark.parametrize(
        "method_call",
        [
            lambda c: c._read_file("a.txt"),
            lambda c: c._write_file("a.txt", "x"),
            lambda c: c._edit_file("a.txt", old_string="x", new_string="y"),
            lambda c: c._glob_search("**/*"),
            lambda c: c._grep_search("foo"),
        ],
        ids=["read", "write", "edit", "glob", "grep"],
    )
    def test_should_return_structured_error_for_each_tool(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        method_call,
    ) -> None:
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=tmp_path / "base",
            auto_login=False,
            user_id=None,
        )

        result = method_call(component)

        assert "error" in result, f"Expected structured error, got {result}"
        assert "user" in result["error"].lower() or "authenticated" in result["error"].lower()


class TestCrossUserIsolation:
    """Threat T1 — two users on the same flow must never see each other's files."""

    def test_user_b_should_not_read_file_written_by_user_a(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"

        component_a = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=False,
            user_id="user-alice",
        )
        component_a._write_file("secret.txt", "alice-only")

        component_b = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=False,
            user_id="user-bob",
        )
        result = component_b._read_file("secret.txt")

        assert "error" in result, f"User B SHOULD NOT see Alice's file: {result}"
        assert "not found" in result["error"].lower() or "does not exist" in result["error"].lower()

    def test_user_b_glob_should_not_list_files_written_by_user_a(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"

        component_a = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=False,
            user_id="user-alice",
        )
        component_a._write_file("alice-doc.txt", "secret")

        component_b = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=False,
            user_id="user-bob",
        )
        result = component_b._glob_search("**/*")

        assert result.get("status") == "ok", result
        assert "alice-doc.txt" not in result.get("matches", [])

    def test_user_b_cannot_escape_via_dotdot_to_user_a_namespace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"

        component_a = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=False,
            user_id="user-alice",
        )
        component_a._write_file("secret.txt", "alice")

        component_b = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=False,
            user_id="user-bob",
        )
        result = component_b._read_file("../../secret.txt")

        assert "error" in result, f"Path traversal escape not blocked: {result}"


class TestReservedSignatureDirectory:
    """`.lfsig` is reserved in BOTH modes (future L3 sidecar hook)."""

    @pytest.mark.parametrize("path", [".lfsig", ".lfsig/anything.json", "ok/.lfsig/x"])
    def test_should_reject_lfsig_in_isolated_mode(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        path: str,
    ) -> None:
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=tmp_path / "base",
            auto_login=False,
            user_id="user-alice",
        )

        result = component._read_file(path)

        assert "error" in result, f"`.lfsig` must be reserved, got: {result}"
        assert "reserved" in result["error"].lower() or "lfsig" in result["error"].lower()

    @pytest.mark.parametrize("path", [".lfsig", ".lfsig/anything.json", "ok/.lfsig/x"])
    def test_should_reject_lfsig_in_shared_mode(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        path: str,
    ) -> None:
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=tmp_path / "base",
            auto_login=True,
        )

        result = component._read_file(path)

        assert "error" in result, f"`.lfsig` must be reserved in shared mode too, got: {result}"
        assert "reserved" in result["error"].lower() or "lfsig" in result["error"].lower()


class TestSharedModeBoundaryEnforcement:
    """Slice S7 — shared mode must enforce the same boundary rules as isolated."""

    def test_should_reject_dotdot_escape_in_shared_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        base = tmp_path / "base"
        # Drop a marker outside <BASE>/shared/ that traversal would expose.
        outside = tmp_path / "outside.txt"
        outside.write_text("compromised", encoding="utf-8")

        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            auto_login=True,
        )

        result = component._read_file("../../outside.txt")

        assert "error" in result, f"Traversal escape not blocked in shared mode: {result}"

    def test_should_reject_absolute_path_in_shared_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        component = _make_component(
            monkeypatch=monkeypatch,
            base_dir=tmp_path / "base",
            auto_login=True,
        )

        result = component._read_file("/etc/passwd")

        assert "error" in result
