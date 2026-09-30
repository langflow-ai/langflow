"""UC4 + UC5 — ContextVar threading + auto-registration hook.

UC4 confirms that ``set_current_user_id(uid)`` makes the value visible
to MCP tools and that the registry-overlay sees the right user.

UC5 confirms ``assistant_service`` writes the validated component file
to the user's sandbox at end-of-run so the next request's overlay sees
it. This is the end-to-end glue.
"""

from __future__ import annotations

import asyncio
import secrets
from typing import TYPE_CHECKING

import pytest
from langflow.agentic.services.user_components import (
    get_user_components_dir,
    register_user_component,
)
from langflow.agentic.services.user_components_context import (
    current_user_id,
    reset_current_user_id,
    set_current_user_id,
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


class TestCurrentUserIdContextVar:
    def setup_method(self):
        reset_current_user_id()

    def test_should_default_to_none(self) -> None:
        assert current_user_id() is None

    def test_should_set_and_get_user_id(self) -> None:
        set_current_user_id("user-alice")
        assert current_user_id() == "user-alice"

    def test_should_reset_to_none(self) -> None:
        set_current_user_id("user-alice")
        reset_current_user_id()
        assert current_user_id() is None

    def test_should_isolate_user_id_across_asyncio_gather_tasks(self) -> None:
        # Each gather child task gets its own copied context; setting the
        # user_id in one task must not leak into a sibling.
        observed: dict[str, str | None] = {}

        async def task(label: str, set_to: str):
            set_current_user_id(set_to)
            # Yield once so other tasks have a chance to run; verify our
            # value is still the one we set.
            await asyncio.sleep(0)
            observed[label] = current_user_id()

        async def main():
            await asyncio.gather(
                task("alpha", "user-alice"),
                task("beta", "user-bob"),
            )

        asyncio.run(main())

        assert observed == {"alpha": "user-alice", "beta": "user-bob"}


class TestOverlayConsumesContextVar:
    """Overlay reads the ContextVar when no user_id arg is passed.

    Helper for MCP tools that don't want to plumb user_id explicitly.
    """

    def setup_method(self):
        reset_current_user_id()

    def test_should_read_overlay_for_contextvar_user(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )
        set_current_user_id("user-alice")

        # Explicit pass-through still wins, but the call here uses the
        # ContextVar — we'll add a wrapper that does the read.
        from langflow.agentic.services.user_components_overlay import (
            load_registry_for_current_user,
        )

        registry = load_registry_for_current_user()
        assert "SumComponent" in registry

    def test_should_return_base_only_when_contextvar_unset(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )
        # ContextVar is None (setup_method reset it).

        from langflow.agentic.services.user_components_overlay import (
            load_registry_for_current_user,
        )

        registry = load_registry_for_current_user()
        assert "SumComponent" not in registry


class TestRegisterIfValid:
    """UC5 — best-effort wrapper invoked from `assistant_service`.

    Wraps `register_user_component` with the swallow-and-log semantics
    the streaming loop needs: a failure to register is operationally
    annoying but must NOT fail the user's request — the component code
    is already streamed to the chat.
    """

    def test_should_register_on_valid_input(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        from langflow.agentic.services.user_components import (
            register_user_component_if_valid,
        )

        result = register_user_component_if_valid(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        assert result is not None
        assert result.exists()
        components_dir = get_user_components_dir(user_id="user-alice")
        assert components_dir is not None
        assert (components_dir / "SumComponent.py").exists()

    def test_should_return_none_and_swallow_when_user_id_missing(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        from langflow.agentic.services.user_components import (
            register_user_component_if_valid,
        )

        result = register_user_component_if_valid(
            user_id=None,
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        assert result is None  # swallowed, not raised

    def test_should_return_none_and_swallow_when_class_name_missing(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        from langflow.agentic.services.user_components import (
            register_user_component_if_valid,
        )

        result = register_user_component_if_valid(
            user_id="user-alice",
            class_name=None,
            code=SAMPLE_CODE,
        )

        assert result is None

    def test_should_return_none_and_swallow_when_class_name_unsafe(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        from langflow.agentic.services.user_components import (
            register_user_component_if_valid,
        )

        # `register_user_component` would raise UserComponentError;
        # `register_user_component_if_valid` swallows that into None.
        result = register_user_component_if_valid(
            user_id="user-alice",
            class_name="../escape",
            code=SAMPLE_CODE,
        )

        assert result is None

    def test_should_return_none_and_swallow_when_code_empty(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        from langflow.agentic.services.user_components import (
            register_user_component_if_valid,
        )

        result = register_user_component_if_valid(
            user_id="user-alice",
            class_name="SumComponent",
            code="",
        )

        assert result is None

    def test_should_still_raise_on_unexpected_errors(
        self,
        isolated_sandbox: Path,  # noqa: ARG002
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unexpected errors must propagate, not be swallowed.

        The swallow is targeted at user-input refusals. A genuine crash
        (e.g., disk full) should propagate so observability is not
        silently degraded. We force one via monkey-patching.
        """
        from langflow.agentic.services import user_components as uc_mod

        def boom(*args, **kwargs):  # noqa: ARG001
            msg = "disk on fire"
            raise OSError(msg)

        monkeypatch.setattr(uc_mod, "_atomic_write_text", boom)

        with pytest.raises(OSError, match="disk on fire"):
            uc_mod.register_user_component_if_valid(
                user_id="user-alice",
                class_name="SumComponent",
                code=SAMPLE_CODE,
            )
