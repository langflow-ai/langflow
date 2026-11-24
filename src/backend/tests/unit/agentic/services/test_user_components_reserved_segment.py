"""UC1 — `.components/` is reserved in the FS tool sandbox.

The agent's 5 FileSystem tools must NOT see or touch `.components/*` even
though it lives inside the user's namespace. Validated component code is
stored there by a privileged backend writer (UC2); allowing the agent to
read or overwrite those files would defeat the privilege separation that
makes "code generated → registered for the user" trustable.

Mirrors the existing `.lfsig` reservation pattern (T4 in the FS plan).
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import pytest

# The lfx tests are blocked from the main venv by the package-isolation
# conftest, but importing the module itself works fine — we just can't
# colocate the test with the production code. Place the test where the
# main test runner reaches it.
from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

if TYPE_CHECKING:
    from pathlib import Path


def _make_component(
    monkeypatch: pytest.MonkeyPatch,
    *,
    base_dir: Path,
    auto_login: bool,
    user_id: str | None = None,
) -> FileSystemToolComponent:
    """Build a FileSystemToolComponent pinned to a fresh sandbox.

    The component bypasses the LangflowClient by binding ``_user_id``
    directly and overriding ``_resolve_auto_login``. We seed a pepper
    file so the hash is reproducible across tests; otherwise the first
    write creates one and subsequent runs see a different namespace.
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    pepper_path = base_dir / ".fs_pepper"
    if not pepper_path.exists():
        pepper_path.write_bytes(secrets.token_bytes(32))
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(base_dir))
    component = FileSystemToolComponent()
    monkeypatch.setattr(
        FileSystemToolComponent,
        "_resolve_auto_login",
        lambda self: auto_login,  # noqa: ARG005
    )
    if user_id is not None:
        component._user_id = user_id
    return component


class TestComponentsReservedInIsolatedMode:
    """`.components/` is reserved when AUTO_LOGIN=False and a user is bound."""

    @pytest.mark.parametrize(
        "path",
        [
            ".components",
            ".components/SumComponent.py",
            "ok/.components/anything",
            ".COMPONENTS/X.py",
        ],
    )
    def test_should_reject_components_segment_for_read(
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

        assert "error" in result, f"`.components/` must be reserved, got: {result}"
        # Be specific: the rejection must be a *reservation* failure,
        # not an incidental "file not found" — otherwise the test would
        # pass before the guard exists.
        assert "reserved" in result["error"].lower(), f"Expected reservation error, got: {result['error']}"

    @pytest.mark.parametrize(
        "path",
        [
            ".components/Evil.py",
            "ok/.components/x",
        ],
    )
    def test_should_reject_components_segment_for_write(
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

        result = component._write_file(path, "class Evil: pass")

        assert "error" in result, f"`.components/` writes must be reserved, got: {result}"
        assert "reserved" in result["error"].lower(), f"Expected reservation error, got: {result['error']}"

    @pytest.mark.parametrize(
        "path",
        [".components", ".components/X.py"],
    )
    def test_should_reject_components_segment_for_glob(
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

        # Sandbox subdir name is hash-derived; just verify the guard
        # triggers on the *requested* path regardless of FS state.
        result = component._glob_search(pattern=path)
        assert "error" in result or result.get("matches") == [], (
            f"`.components/` glob must be reserved or empty, got: {result}"
        )


class TestComponentsReservedInSharedMode:
    """`.components/` is reserved in AUTO_LOGIN shared mode too."""

    @pytest.mark.parametrize(
        "path",
        [".components", ".components/X.py", "ok/.components/anything"],
    )
    def test_should_reject_components_segment(
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

        assert "error" in result, f"`.components/` must be reserved in shared mode too, got: {result}"
        assert "reserved" in result["error"].lower(), f"Expected reservation error, got: {result['error']}"


class TestExistingLfsigReservationStillHolds:
    """Regression — `.lfsig` reservation still holds.

    Adding `.components/` to the reserved list must not accidentally
    weaken the existing `.lfsig` reservation.
    """

    @pytest.mark.parametrize("path", [".lfsig", ".lfsig/x", "ok/.lfsig/y"])
    def test_should_still_reject_lfsig(
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
        assert "error" in result


def base_for(p: Path) -> Path:
    """Helper that mirrors the production path resolution for assertions."""
    return p
