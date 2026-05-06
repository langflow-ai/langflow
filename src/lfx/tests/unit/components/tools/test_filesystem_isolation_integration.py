"""End-to-end integration tests for per-user isolation in FileSystemToolComponent.

These tests cover the threats from the FILESYSTEM_USER_ISOLATION_PLAN:
    T1 — User B reads user A's files via the same flow
    T2 — Anonymous user with mode=on
    T3 — Tool reuse across user contexts (covered in TestToolBindingL2)
    T6 — `.lfsig` reserved tree
    L4 — Audit log emitted for every public tool call
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from lfx.components.tools.filesystem import FileSystemToolComponent

if TYPE_CHECKING:
    from pathlib import Path


def _make_isolated_component(
    *,
    monkeypatch: pytest.MonkeyPatch,
    base_dir: Path,
    user_id: str | None,
    mode: str = "auto",
    audit_log_path: Path | None = None,
    sub_path: str = "",
    pepper_path: Path | None = None,
    read_only: bool = False,
) -> FileSystemToolComponent:
    """Build a component with isolation env vars in place.

    We set the env vars rather than calling the helpers directly because the
    point of these tests is to assert the wiring from env → config → component.
    """
    monkeypatch.setenv("LANGFLOW_FS_TOOL_USER_ISOLATION", mode)
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(base_dir))
    if pepper_path is not None:
        monkeypatch.setenv("LANGFLOW_FS_TOOL_PEPPER_PATH", str(pepper_path))
    else:
        monkeypatch.setenv("LANGFLOW_FS_TOOL_PEPPER_PATH", str(base_dir / ".pepper"))
    if audit_log_path is not None:
        monkeypatch.setenv("LANGFLOW_FS_TOOL_AUDIT_LOG", str(audit_log_path))
    else:
        monkeypatch.delenv("LANGFLOW_FS_TOOL_AUDIT_LOG", raising=False)

    component = FileSystemToolComponent(root_path=sub_path, read_only=read_only)
    if user_id is not None:
        component._user_id = user_id
    return component


class TestLegacyBackwardsCompatibility:
    """Slice D1 — when isolation=auto AND no user_id, behavior matches the merged PR."""

    def test_should_use_root_path_directly_when_anonymous_in_auto_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Existing OSS / desktop deploys: no user, no isolation env vars set.
        # The agent must keep working with root_path as the literal sandbox.
        monkeypatch.delenv("LANGFLOW_FS_TOOL_USER_ISOLATION", raising=False)
        monkeypatch.delenv("LANGFLOW_FS_TOOL_BASE_DIR", raising=False)
        sandbox = tmp_path / "legacy"
        sandbox.mkdir()
        (sandbox / "hello.txt").write_text("ok", encoding="utf-8")

        component = FileSystemToolComponent(root_path=str(sandbox), read_only=False)
        result = component._read_file("hello.txt")

        assert result.get("status") == "ok", f"Legacy mode broken: {result}"
        assert "ok" in result["content"]


class TestIsolationOnRefusesAnonymous:
    """Slice D2 — mode=on must refuse calls without an authenticated user."""

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
    def test_should_return_structured_error_when_user_is_anonymous(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        method_call,
    ) -> None:
        component = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=tmp_path / "base",
            user_id=None,
            mode="on",
            sub_path="",
        )

        result = method_call(component)

        assert "error" in result, f"Expected structured error, got {result}"
        # Error message should make the cause discoverable to the operator.
        assert "user" in result["error"].lower() or "authenticated" in result["error"].lower()


class TestPerUserNamespacing:
    """Slice D3 — paths land under <base>/users/<hash>/<sub> when isolated."""

    def test_should_create_files_inside_user_namespace(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        base = tmp_path / "base"
        component = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            user_id="user-alice",
            mode="auto",
            sub_path="",
        )

        write_result = component._write_file("notes.md", "hello")

        assert write_result.get("status") in {"created", "updated"}, write_result
        # The actual file must live under <base>/users/<hash>/notes.md.
        users_dir = base / "users"
        assert users_dir.exists(), "Per-user namespace directory was not created"
        user_subdirs = list(users_dir.iterdir())
        assert len(user_subdirs) == 1
        assert (user_subdirs[0] / "notes.md").read_text(encoding="utf-8") == "hello"

    def test_should_treat_root_path_as_subpath_under_user_namespace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"
        component = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            user_id="user-alice",
            mode="auto",
            sub_path="projects/demo",
        )

        write_result = component._write_file("notes.md", "demo")

        assert write_result.get("status") in {"created", "updated"}, write_result
        users_dir = base / "users"
        user_subdirs = list(users_dir.iterdir())
        assert (user_subdirs[0] / "projects" / "demo" / "notes.md").exists()


class TestCrossUserIsolation:
    """Slice D4 — the core threat. User A and B must never see each other's files."""

    def test_user_b_should_not_read_file_written_by_user_a(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"
        pepper = tmp_path / ".pepper"

        # User A writes a secret file.
        component_a = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            user_id="user-alice",
            mode="auto",
            sub_path="",
            pepper_path=pepper,
        )
        component_a._write_file("secret.txt", "alice-only")

        # User B with the same flow tries to read it.
        component_b = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            user_id="user-bob",
            mode="auto",
            sub_path="",
            pepper_path=pepper,
        )
        result = component_b._read_file("secret.txt")

        assert "error" in result, f"User B SHOULD NOT see Alice's file: {result}"
        # Specifically, the file does not exist in B's namespace.
        assert "not found" in result["error"].lower() or "does not exist" in result["error"].lower()

    def test_user_b_glob_should_not_list_files_written_by_user_a(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = tmp_path / "base"
        pepper = tmp_path / ".pepper"

        component_a = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            user_id="user-alice",
            mode="auto",
            sub_path="",
            pepper_path=pepper,
        )
        component_a._write_file("alice-doc.txt", "secret")

        component_b = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            user_id="user-bob",
            mode="auto",
            sub_path="",
            pepper_path=pepper,
        )
        result = component_b._glob_search("**/*")

        # Bob's own namespace exists but is empty — so matches must be empty.
        assert result.get("status") == "ok", result
        assert "alice-doc.txt" not in result.get("matches", [])

    def test_user_b_cannot_escape_via_dotdot_to_user_a_namespace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Even if Bob crafts a relative path that would traverse into the
        # `users/<alice_hash>/` directory, the boundary check must reject it.
        base = tmp_path / "base"
        pepper = tmp_path / ".pepper"

        component_a = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            user_id="user-alice",
            mode="auto",
            sub_path="",
            pepper_path=pepper,
        )
        component_a._write_file("secret.txt", "alice")

        component_b = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            user_id="user-bob",
            mode="auto",
            sub_path="",
            pepper_path=pepper,
        )
        result = component_b._read_file("../../secret.txt")

        assert "error" in result, f"Path traversal escape not blocked: {result}"


class TestReservedSignatureDirectory:
    """Slice D5 — `.lfsig` is reserved (future L3 hook)."""

    @pytest.mark.parametrize("path", [".lfsig", ".lfsig/anything.json", "ok/.lfsig/x"])
    def test_should_reject_paths_that_traverse_through_lfsig(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        path: str,
    ) -> None:
        base = tmp_path / "base"
        component = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            user_id="user-alice",
            mode="auto",
            sub_path="",
        )

        result = component._read_file(path)

        assert "error" in result, f"`.lfsig` must be reserved, got: {result}"
        assert "reserved" in result["error"].lower() or "lfsig" in result["error"].lower()


class TestAuditLog:
    """Slice D6 — every public tool call emits one NDJSON line with required fields."""

    def test_should_emit_audit_record_for_successful_read(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        audit_log = tmp_path / "audit.jsonl"
        component = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=tmp_path / "base",
            user_id="user-alice",
            mode="auto",
            sub_path="",
            audit_log_path=audit_log,
        )
        component._write_file("a.txt", "hello")

        component._read_file("a.txt")

        lines = audit_log.read_text(encoding="utf-8").splitlines()
        # write_file + read_file = 2 records.
        assert len(lines) == 2
        records = [json.loads(line) for line in lines]
        actions = [r["action"] for r in records]
        assert "write_file" in actions
        assert "read_file" in actions
        for record in records:
            assert record["user_id"] == "user-alice"
            assert "ts" in record
            assert isinstance(record["ok"], bool)

    def test_should_emit_audit_record_for_failed_call(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        audit_log = tmp_path / "audit.jsonl"
        component = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=tmp_path / "base",
            user_id="user-alice",
            mode="auto",
            sub_path="",
            audit_log_path=audit_log,
        )

        component._read_file("../escape.txt")

        lines = audit_log.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["action"] == "read_file"
        assert record["ok"] is False
        assert record["err"] is not None

    def test_should_not_write_audit_when_audit_log_unset(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # No audit log env var — make_audit_sink returns NullAuditSink.
        # No file should ever be created in this scenario.
        base = tmp_path / "base"
        component = _make_isolated_component(
            monkeypatch=monkeypatch,
            base_dir=base,
            user_id="user-alice",
            mode="auto",
            sub_path="",
            audit_log_path=None,
        )

        component._write_file("a.txt", "x")
        component._read_file("a.txt")

        # No spurious audit.jsonl created anywhere under tmp_path.
        spurious = list(tmp_path.rglob("audit.jsonl"))
        assert spurious == []
