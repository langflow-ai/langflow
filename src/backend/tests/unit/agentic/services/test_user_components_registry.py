"""UC2 — register_user_component privileged helper.

Writes a validated user-authored Component class as a `.py` file inside
the user's existing FS sandbox at ``<root>/.components/<ClassName>.py``.

Reuses every primitive the FileSystemToolComponent already provides:
    - sandbox resolution (`_validate_root`)
    - per-user hash (HMAC-SHA256 with stored pepper)
    - AUTO_LOGIN dispatch (shared vs isolated)
    - refusal when AUTO_LOGIN=False and no user is bound
    - cross-platform name validation (Windows reserved, forbidden chars)

The helper itself is the only path that may write into the reserved
`.components/` segment — the agent's FS tools refuse it (UC1).
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import pytest
from langflow.agentic.services.user_components import (
    UserComponentError,
    register_user_component,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def isolated_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the FS tool sandbox at a fresh tmp_path.

    Mirrors the fixture used by other agentic sandbox tests:
      - Pre-seeds the pepper so the user hash is reproducible.
      - Pins AUTO_LOGIN=False at the FileSystemToolComponent class level
        so the singleton settings service can't taint other tests.
    """
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
    pepper = tmp_path / ".fs_pepper"
    pepper.write_bytes(secrets.token_bytes(32))

    from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

    monkeypatch.setattr(
        FileSystemToolComponent,
        "_resolve_auto_login",
        lambda self: False,  # noqa: ARG005
    )
    return tmp_path


@pytest.fixture
def shared_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """AUTO_LOGIN=True variant — components land in <BASE>/shared/.components/."""
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
    pepper = tmp_path / ".fs_pepper"
    pepper.write_bytes(secrets.token_bytes(32))

    from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

    monkeypatch.setattr(
        FileSystemToolComponent,
        "_resolve_auto_login",
        lambda self: True,  # noqa: ARG005
    )
    return tmp_path


SAMPLE_CODE = (
    "from lfx.custom import Component\n"
    "from lfx.io import FloatInput, Output\n"
    "from lfx.schema import Data\n"
    "\n"
    "class SumComponent(Component):\n"
    "    display_name = 'Sum'\n"
    "    inputs = [FloatInput(name='a'), FloatInput(name='b')]\n"
    "    outputs = [Output(name='result', display_name='Sum', method='run')]\n"
    "    def run(self) -> Data:\n"
    "        return Data(data={'sum': (self.a or 0) + (self.b or 0)})\n"
)


class TestRegisterUserComponentHappyPath:
    def test_should_write_python_file_to_isolated_user_namespace(self, isolated_sandbox: Path) -> None:
        result_path = register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        assert result_path.exists()
        assert result_path.name == "SumComponent.py"
        assert result_path.parent.name == ".components"
        assert result_path.read_text(encoding="utf-8") == SAMPLE_CODE
        # The file MUST live under <BASE>/users/<hash>/.components/.
        assert "users" in result_path.parts
        assert isolated_sandbox in result_path.parents

    def test_should_write_python_file_under_shared_in_auto_login_mode(self, shared_sandbox: Path) -> None:
        result_path = register_user_component(
            user_id="ignored-in-auto-login",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        assert result_path.exists()
        assert result_path.parent == shared_sandbox / "shared" / ".components"
        assert result_path.name == "SumComponent.py"

    def test_should_overwrite_when_same_class_name_re_registered(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        first = register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )
        new_code = SAMPLE_CODE.replace("'sum'", "'total'")
        second = register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=new_code,
        )

        # Same on-disk path; the latest write wins.
        assert first == second
        assert second.read_text(encoding="utf-8") == new_code

    def test_should_isolate_components_by_user(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        alice_path = register_user_component(
            user_id="user-alice",
            class_name="AliceSum",
            code=SAMPLE_CODE,
        )
        bob_path = register_user_component(
            user_id="user-bob",
            class_name="BobSum",
            code=SAMPLE_CODE,
        )

        # Different hash-derived parent dirs.
        assert alice_path.parents[1] != bob_path.parents[1]
        # Alice can't see Bob's component on the filesystem.
        alice_components_dir = alice_path.parent
        assert list(alice_components_dir.iterdir()) == [alice_path]


class TestRegisterUserComponentRefusesUntrustedInputs:
    def test_should_refuse_when_user_id_missing_and_auto_login_false(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        with pytest.raises(UserComponentError, match="authenticated user"):
            register_user_component(
                user_id=None,
                class_name="SumComponent",
                code=SAMPLE_CODE,
            )

    def test_should_refuse_empty_class_name(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        with pytest.raises(UserComponentError, match="class_name"):
            register_user_component(
                user_id="user-alice",
                class_name="",
                code=SAMPLE_CODE,
            )

    @pytest.mark.parametrize(
        "bad_name",
        [
            "../escape",
            "subdir/Nested",
            "..",
            ".",
            "Sum/Component",
            "Sum\\Component",
            "\x00null",
            "Sum:Colon",  # Windows-forbidden
            "CON",  # Windows reserved
            "NUL",
            "COM1",
            "LPT9",
        ],
    )
    def test_should_refuse_path_traversal_or_reserved_class_names(self, isolated_sandbox: Path, bad_name: str) -> None:  # noqa: ARG002
        with pytest.raises(UserComponentError):
            register_user_component(
                user_id="user-alice",
                class_name=bad_name,
                code=SAMPLE_CODE,
            )

    def test_should_refuse_class_name_longer_than_max(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # Windows-portability safeguard: the on-disk path is
        # ``<BASE>/users/<32-hex-hash>/.components/<ClassName>.py``. Even
        # with a deep BASE on Windows (``C:\Users\<long-username>\AppData\
        # Local\langflow\fs_tool\fs_sandbox``), a 64-char cap on the
        # class name keeps the full path well under MAX_PATH=260 default.
        # 65 chars is over the cap; must be refused.
        from langflow.agentic.services.user_components import (
            MAX_CLASS_NAME_LENGTH,
        )

        too_long = "A" + ("a" * MAX_CLASS_NAME_LENGTH)  # MAX + 1
        assert len(too_long) == MAX_CLASS_NAME_LENGTH + 1

        with pytest.raises(UserComponentError, match="length"):
            register_user_component(
                user_id="user-alice",
                class_name=too_long,
                code=SAMPLE_CODE,
            )

    def test_should_accept_class_name_exactly_at_max_length(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # Boundary: a name of exactly MAX_CLASS_NAME_LENGTH chars must be
        # ACCEPTED. Off-by-one regression guard.
        from langflow.agentic.services.user_components import (
            MAX_CLASS_NAME_LENGTH,
        )

        at_max = "A" + ("a" * (MAX_CLASS_NAME_LENGTH - 1))
        assert len(at_max) == MAX_CLASS_NAME_LENGTH

        result_path = register_user_component(
            user_id="user-alice",
            class_name=at_max,
            code=SAMPLE_CODE,
        )
        assert result_path.exists()

    def test_max_class_name_length_constant_value(self) -> None:
        # Lock the cap so a refactor that bumps it accidentally past a
        # safe Windows value triggers this test. 64 is the documented
        # ceiling (see PLATFORM_AGNOSTIC_RULE.md path-length notes).
        from langflow.agentic.services.user_components import (
            MAX_CLASS_NAME_LENGTH,
        )

        assert MAX_CLASS_NAME_LENGTH == 64

    def test_should_refuse_dunder_or_leading_dot_class_name(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # `.hidden` or `__init__` would be filesystem-valid but break the
        # registry overlay (it'd treat them as importable modules).
        for name in ("__init__", "_private", ".hidden"):
            with pytest.raises(UserComponentError):
                register_user_component(
                    user_id="user-alice",
                    class_name=name,
                    code=SAMPLE_CODE,
                )

    def test_should_refuse_empty_code(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        with pytest.raises(UserComponentError, match="code"):
            register_user_component(
                user_id="user-alice",
                class_name="SumComponent",
                code="",
            )

    def test_should_refuse_oversized_code(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # The component-generation flow validates code well below 1 MB.
        # Anything larger is almost certainly an attack / runaway model.
        with pytest.raises(UserComponentError, match="size"):
            register_user_component(
                user_id="user-alice",
                class_name="HugeComponent",
                code="x" * (2 * 1024 * 1024),  # 2 MB
            )


class TestAtomicWrite:
    def test_should_not_leave_partial_file_when_write_fails(
        self,
        isolated_sandbox: Path,  # noqa: ARG002
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Atomic write: tmp file + rename.

        A failure leaves the directory empty (or with only a prior
        successful write), never a half-written file the loader could
        parse and crash on.
        """
        # First a successful write.
        first = register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )
        first_text = first.read_text(encoding="utf-8")
        assert first_text == SAMPLE_CODE

        # Force the atomic rename to fail mid-write. Patch the EXACT method the
        # code calls — Path.replace — NOT the transitive os.replace it wraps.
        # os.replace resolution proved order-sensitive under the full suite
        # (this test passed alone but flaked in the batch); patching the real
        # call site makes failure injection deterministic.
        def boom(self, target):  # noqa: ARG001
            msg = "simulated rename failure"
            raise OSError(msg)

        monkeypatch.setattr("pathlib.Path.replace", boom)

        new_code = SAMPLE_CODE.replace("'sum'", "'total'")
        with pytest.raises(UserComponentError):
            register_user_component(
                user_id="user-alice",
                class_name="SumComponent",
                code=new_code,
            )

        # monkeypatch reverts Path.replace at teardown; the assertions below
        # only read files (read_text / iterdir / unlink), which never use it.

        # The on-disk file is still the first version. No partial second.
        assert first.read_text(encoding="utf-8") == first_text
        # No leftover .tmp files in the components directory.
        tmps = [p for p in first.parent.iterdir() if p.suffix == ".tmp" or ".tmp." in p.name]
        assert tmps == [], f"Leftover tmp files: {tmps}"
