"""UC7 — clear_user_components wipes the user's `.components/` dir.

Called on every "new session start" boundary (panel mount with fresh
session_id, explicit New session click). Idempotent and per-user
isolated — wiping Alice's components must not touch Bob's.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import pytest
from langflow.agentic.services.user_components import (
    clear_user_components,
    register_user_component,
)

if TYPE_CHECKING:
    from pathlib import Path

SAMPLE_CODE = (
    "from lfx.custom import Component\n"
    "from lfx.io import FloatInput, Output\n"
    "from lfx.schema import Data\n"
    "\n"
    "class SumComponent(Component):\n"
    "    inputs = [FloatInput(name='a'), FloatInput(name='b')]\n"
    "    outputs = [Output(name='result', display_name='Sum', method='run')]\n"
    "    def run(self) -> Data:\n"
    "        return Data(data={'sum': (self.a or 0) + (self.b or 0)})\n"
)


@pytest.fixture
def isolated_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
    (tmp_path / ".fs_pepper").write_bytes(secrets.token_bytes(32))

    from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

    monkeypatch.setattr(
        FileSystemToolComponent,
        "_resolve_auto_login",
        lambda self: False,  # noqa: ARG005
    )
    return tmp_path


@pytest.fixture
def shared_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
    (tmp_path / ".fs_pepper").write_bytes(secrets.token_bytes(32))

    from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

    monkeypatch.setattr(
        FileSystemToolComponent,
        "_resolve_auto_login",
        lambda self: True,  # noqa: ARG005
    )
    return tmp_path


class TestClearUserComponentsHappyPath:
    def test_should_delete_all_py_files_in_isolated_user_namespace(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )
        register_user_component(
            user_id="user-alice",
            class_name="MultiplyComponent",
            code=SAMPLE_CODE.replace("SumComponent", "MultiplyComponent"),
        )

        deleted = clear_user_components(user_id="user-alice")

        assert deleted == 2
        # The directory still exists (we wipe contents, not the dir itself
        # — keeps the loader's walk simple on the next register call).
        from langflow.agentic.services.user_components import (
            get_user_components_dir,
        )

        components_dir = get_user_components_dir(user_id="user-alice")
        assert components_dir is not None
        assert components_dir.exists()
        assert list(components_dir.iterdir()) == []

    def test_should_be_idempotent_when_directory_empty(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # No prior registration. Wipe is a no-op, returns 0.
        deleted = clear_user_components(user_id="user-alice")
        assert deleted == 0

    def test_should_be_idempotent_when_called_twice(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        first = clear_user_components(user_id="user-alice")
        second = clear_user_components(user_id="user-alice")

        assert first == 1
        assert second == 0

    def test_should_work_in_auto_login_shared_mode(self, shared_sandbox: Path) -> None:
        register_user_component(
            user_id="ignored-in-auto-login",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        deleted = clear_user_components(user_id="any")

        assert deleted == 1
        assert (shared_sandbox / "shared" / ".components").exists()
        assert list((shared_sandbox / "shared" / ".components").iterdir()) == []


class TestClearUserComponentsIsolation:
    def test_should_not_touch_other_users_components(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        register_user_component(
            user_id="user-alice",
            class_name="AliceSum",
            code=SAMPLE_CODE,
        )
        bob_path = register_user_component(
            user_id="user-bob",
            class_name="BobSum",
            code=SAMPLE_CODE,
        )

        clear_user_components(user_id="user-alice")

        # Bob's file still there.
        assert bob_path.exists()

    def test_should_not_touch_files_outside_components_directory(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # Plant a user-authored file in the sandbox ROOT (not .components/).
        # The FS tool would create one normally via write_file.
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )
        from langflow.agentic.services.user_components import (
            get_user_components_dir,
        )

        components_dir = get_user_components_dir(user_id="user-alice")
        assert components_dir is not None
        # The sandbox root is the parent of the components dir.
        sandbox_root = components_dir.parent
        user_file = sandbox_root / "NOTES.md"
        user_file.write_text("# my notes", encoding="utf-8")

        clear_user_components(user_id="user-alice")

        # User's regular file is untouched. Only the .components/ dir
        # was wiped.
        assert user_file.exists()
        assert user_file.read_text(encoding="utf-8") == "# my notes"


class TestClearUserComponentsRefusal:
    def test_should_return_zero_when_user_id_missing_and_auto_login_false(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # Sandbox resolution refuses without a user; clear silently
        # returns 0 (no-op) rather than raising — same shape as the
        # post-validation hook contract.
        deleted = clear_user_components(user_id=None)
        assert deleted == 0

    def test_should_only_delete_py_files_not_arbitrary_files(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # Defensive: even if some other code planted a non-.py file in
        # .components/ (shouldn't happen — reserved segment + privileged
        # writer — but assume the FS layer could be future-broken), we
        # only wipe `.py` files. Anything else is left alone.
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )
        from langflow.agentic.services.user_components import (
            get_user_components_dir,
        )

        components_dir = get_user_components_dir(user_id="user-alice")
        assert components_dir is not None
        readme = components_dir / "README.txt"
        readme.write_text("not python", encoding="utf-8")

        clear_user_components(user_id="user-alice")

        # README still there; .py was wiped.
        assert readme.exists()
        assert not (components_dir / "SumComponent.py").exists()
