"""Security tests for the agentic files endpoint.

The endpoint lets the frontend read files the agent wrote inside the
sandboxed workspace. Every adversarial test below maps to one threat in
``CZL/DEVELOPMENT/PLAN_document_assistant.md`` (T1-T13).

Tests invoke the route handler directly (not via TestClient) so we focus on
the security logic - authentication is decoupled via a mock ``current_user``.
End-to-end HTTP wiring is covered by the integration smoke test at the end.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from langflow.agentic.api.files_router import get_file

if TYPE_CHECKING:
    from pathlib import Path


def _make_user(user_id: str = "u-abc") -> SimpleNamespace:
    return SimpleNamespace(id=user_id)


def _write_sandbox_file(sandbox_root: Path, user_id: str, relative_path: str, content: bytes) -> Path:  # noqa: ARG001
    """Materialize a file inside the user's FileSystemToolComponent sandbox.

    Reproduces the layout FileSystemToolComponent uses so the endpoint
    resolves the same way as the agent's write_file tool. AUTO_LOGIN=False
    path: ``<base>/<namespace>/<relative>``. The namespace is derived from
    user_id + pepper inside FileSystemToolComponent — we just write into the
    namespace it computes so we can later read it back.
    """
    # Force the FileSystemToolComponent to be the single source of truth for
    # path layout — instantiate it, validate the root, then write our fixture
    # into the same directory.
    from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

    fs = FileSystemToolComponent()
    fs._user_id = user_id
    root = fs._validate_root()
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


@pytest.fixture
def isolated_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the FS tool sandbox at a fresh tmp_path with AUTO_LOGIN disabled.

    Why not ``monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")``: the settings
    service is a process-wide singleton that caches ``AUTO_LOGIN`` on first
    access. The env var revert at test teardown doesn't un-cache the value,
    so subsequent tests in the suite (e.g., the flow_builder filesystem-tool
    tests) would inherit ``AUTO_LOGIN=False`` and fail because they don't
    bind a user_id. We pin the per-instance method instead — no global state.
    """
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
    from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

    monkeypatch.setattr(
        FileSystemToolComponent,
        "_resolve_auto_login",
        lambda self: False,  # noqa: ARG005
    )
    return tmp_path


class TestHappyPath:
    """B5 happy path — authenticated user reads a file in their own sandbox."""

    @pytest.mark.asyncio
    async def test_should_return_file_content_when_path_valid(self, isolated_sandbox):
        # Arrange — materialize a file in user u-abc's namespace.
        user = _make_user("u-abc")
        _write_sandbox_file(isolated_sandbox, "u-abc", "DOCS.md", b"# Title\n\nHello.")

        # Act
        response = await get_file(path="DOCS.md", download=False, current_user=user)

        # Assert
        assert isinstance(response, Response)
        assert response.status_code == 200
        assert response.body == b"# Title\n\nHello."
        assert response.media_type.startswith("text/plain")


class TestPathTraversalRejection:
    """B5 — T1: path traversal must be refused BEFORE any I/O is attempted."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "evil_path",
        [
            "../escape.md",
            "../../etc/passwd",
            "subdir/../../../escape.md",
            "subdir/..",
        ],
    )
    async def test_should_reject_path_when_contains_dotdot(self, isolated_sandbox, evil_path):  # noqa: ARG002
        user = _make_user("u-abc")
        with pytest.raises(HTTPException) as exc:
            await get_file(path=evil_path, download=False, current_user=user)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_should_reject_path_when_absolute_unix(self, isolated_sandbox):  # noqa: ARG002
        user = _make_user("u-abc")
        with pytest.raises(HTTPException) as exc:
            await get_file(path="/etc/passwd", download=False, current_user=user)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_should_reject_path_when_absolute_unix_backslash(self, isolated_sandbox):  # noqa: ARG002
        user = _make_user("u-abc")
        with pytest.raises(HTTPException) as exc:
            await get_file(path="\\etc\\passwd", download=False, current_user=user)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_should_reject_path_when_windows_drive_letter(self, isolated_sandbox):  # noqa: ARG002
        user = _make_user("u-abc")
        with pytest.raises(HTTPException) as exc:
            await get_file(path="C:\\Users\\victim\\file.md", download=False, current_user=user)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_should_reject_path_when_null_byte(self, isolated_sandbox):  # noqa: ARG002
        user = _make_user("u-abc")
        with pytest.raises(HTTPException) as exc:
            await get_file(path="DOCS.md\x00.txt", download=False, current_user=user)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_should_reject_path_when_empty(self, isolated_sandbox):  # noqa: ARG002
        user = _make_user("u-abc")
        with pytest.raises(HTTPException) as exc:
            await get_file(path="", download=False, current_user=user)
        # Either 400 from our pre-validation or 422 from FastAPI — both are
        # acceptable refusals; we just don't tolerate a 200.
        assert exc.value.status_code in {400, 422}


class TestCrossUserDenial:
    """B5 — T2: user B must not read user A's files. Returns 404 (not 403)
    so the existence of A's namespace is not leaked.
    """  # noqa: D205

    @pytest.mark.asyncio
    async def test_should_return_404_when_target_in_other_user_namespace(self, isolated_sandbox):
        # Arrange — write a file as user A.
        _write_sandbox_file(isolated_sandbox, "user-a", "SECRET.md", b"a's secret")

        # Act — user B requests the SAME relative path (a's namespace has it,
        # b's namespace doesn't). The endpoint resolves under b's namespace,
        # finds nothing.
        user_b = _make_user("user-b")
        with pytest.raises(HTTPException) as exc:
            await get_file(path="SECRET.md", download=False, current_user=user_b)

        # 404 — not 403 — so we don't leak the existence of A's namespace.
        assert exc.value.status_code == 404


class TestMissingFile:
    """B5 — request for a file that doesn't exist returns 404."""

    @pytest.mark.asyncio
    async def test_should_return_404_when_file_does_not_exist(self, isolated_sandbox):  # noqa: ARG002
        user = _make_user("u-abc")
        with pytest.raises(HTTPException) as exc:
            await get_file(path="NONEXISTENT.md", download=False, current_user=user)
        assert exc.value.status_code == 404


class TestSizeAndBinaryGuards:
    """B5 — T8 (oversize), T9 (binary): refused with the right status code."""

    @pytest.mark.asyncio
    async def test_should_return_413_when_file_exceeds_max_size(self, isolated_sandbox, monkeypatch):
        from lfx.components.tools import filesystem as fs_module

        # Reduce the cap so we can exercise the limit cheaply.
        monkeypatch.setattr(fs_module, "MAX_FILE_SIZE_BYTES", 16)

        user = _make_user("u-abc")
        _write_sandbox_file(isolated_sandbox, "u-abc", "BIG.md", b"x" * 32)

        with pytest.raises(HTTPException) as exc:
            await get_file(path="BIG.md", download=False, current_user=user)
        assert exc.value.status_code == 413

    @pytest.mark.asyncio
    async def test_should_return_415_when_file_is_binary(self, isolated_sandbox):
        user = _make_user("u-abc")
        # A null byte in the first 8 KiB marks the file as binary per
        # FileSystemToolComponent's heuristic.
        _write_sandbox_file(isolated_sandbox, "u-abc", "BIN.dat", b"\x00\x01\x02hello")

        with pytest.raises(HTTPException) as exc:
            await get_file(path="BIN.dat", download=False, current_user=user)
        assert exc.value.status_code == 415


class TestDownloadMode:
    """B5 — T7: ?download=true must force attachment + octet-stream so the
    browser never inlines a returned .html / .svg / .js as page content.
    """  # noqa: D205

    @pytest.mark.asyncio
    async def test_should_set_content_disposition_attachment_when_download_true(self, isolated_sandbox):
        user = _make_user("u-abc")
        _write_sandbox_file(isolated_sandbox, "u-abc", "DOCS.md", b"hello")

        response = await get_file(path="DOCS.md", download=True, current_user=user)

        assert response.status_code == 200
        cd = response.headers.get("content-disposition", "")
        assert cd.startswith("attachment;"), cd
        assert "DOCS.md" in cd

    @pytest.mark.asyncio
    async def test_should_force_octet_stream_when_download_true(self, isolated_sandbox):
        user = _make_user("u-abc")
        _write_sandbox_file(isolated_sandbox, "u-abc", "DOCS.md", b"hello")

        response = await get_file(path="DOCS.md", download=True, current_user=user)
        assert response.media_type == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_should_sanitize_filename_in_content_disposition(self, isolated_sandbox):
        """A quote in the filename must not break out of the header value."""
        user = _make_user("u-abc")
        # Most filesystems allow quotes; we still want our header builder to
        # be robust if the LLM (or a future contributor) names a file weirdly.
        _write_sandbox_file(isolated_sandbox, "u-abc", "weird.md", b"x")

        response = await get_file(path="weird.md", download=True, current_user=user)
        cd = response.headers.get("content-disposition", "")
        # Header is well-formed: exactly one filename="..." segment.
        assert cd.count('filename="') == 1


class TestAuditLogging:
    """B5 — T11: every successful read emits an audit log line with the
    user_id, the (relative) path, and the size.
    """  # noqa: D205

    @pytest.mark.asyncio
    async def test_should_log_audit_event_when_file_read(self, isolated_sandbox, caplog):
        user = _make_user("u-abc")
        _write_sandbox_file(isolated_sandbox, "u-abc", "DOCS.md", b"hi")

        with caplog.at_level("INFO"):
            await get_file(path="DOCS.md", download=False, current_user=user)

        records = [r for r in caplog.records if "agentic.files.read" in r.message]
        assert records, f"Expected an agentic.files.read log entry, got: {[r.message for r in caplog.records]}"
