"""UC3 — registry overlay merges base + user `.components/*.py`.

The overlay function is the contract the MCP tools (search, describe,
add, build_flow) use. It returns ``{component_type: template_dict}``
with the same shape ``load_local_registry()`` produces, just with the
user's registered components folded in.
"""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest
from langflow.agentic.services.user_components import register_user_component
from langflow.agentic.services.user_components_overlay import (
    load_registry_with_user_overlay,
)

SAMPLE_CODE = (
    "from lfx.custom import Component\n"
    "from lfx.io import FloatInput, Output\n"
    "from lfx.schema import Data\n"
    "\n"
    "class SumComponent(Component):\n"
    "    display_name = 'Sum'\n"
    "    description = 'Adds two numbers'\n"
    "    inputs = [FloatInput(name='a'), FloatInput(name='b')]\n"
    "    outputs = [Output(name='result', display_name='Sum', method='run')]\n"
    "    def run(self) -> Data:\n"
    "        return Data(data={'sum': (self.a or 0) + (self.b or 0)})\n"
)


@pytest.fixture
def isolated_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
    (tmp_path / ".fs_pepper").write_bytes(secrets.token_bytes(32))

    from lfx.components.tools.filesystem import FileSystemToolComponent

    monkeypatch.setattr(
        FileSystemToolComponent,
        "_resolve_auto_login",
        lambda self: False,
    )
    return tmp_path


class TestRegistryOverlay:
    def test_should_return_base_registry_when_no_user_components_exist(
        self, isolated_sandbox: Path
    ) -> None:
        registry = load_registry_with_user_overlay(user_id="user-alice")
        # Base registry contains a known component.
        assert "ChatInput" in registry
        # Nothing user-overlaid yet.
        assert "SumComponent" not in registry

    def test_should_include_user_component_in_registry_after_registration(
        self, isolated_sandbox: Path
    ) -> None:
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        registry = load_registry_with_user_overlay(user_id="user-alice")

        assert "SumComponent" in registry
        # And the base entries are still there.
        assert "ChatInput" in registry

    def test_should_isolate_user_components_between_users(
        self, isolated_sandbox: Path
    ) -> None:
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        bob_registry = load_registry_with_user_overlay(user_id="user-bob")
        assert "SumComponent" not in bob_registry

        alice_registry = load_registry_with_user_overlay(user_id="user-alice")
        assert "SumComponent" in alice_registry

    def test_should_return_base_only_when_user_id_is_none(
        self, isolated_sandbox: Path
    ) -> None:
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        registry = load_registry_with_user_overlay(user_id=None)
        # No user → no overlay (mirrors the FS tool refusal).
        assert "SumComponent" not in registry
        # Base registry still present.
        assert "ChatInput" in registry

    def test_should_carry_user_code_into_overlay_template(
        self, isolated_sandbox: Path
    ) -> None:
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        registry = load_registry_with_user_overlay(user_id="user-alice")
        entry = registry["SumComponent"]

        # The template carries a `code` field with the user's source so
        # BuildFlowFromSpec / AddComponent can materialize a node that
        # actually runs the user's class (and not a generic placeholder).
        assert "template" in entry
        code_field = entry["template"].get("code", {})
        # Could be a wrapper dict {"value": "..."} or the raw string; both
        # acceptable as long as the user's source is reachable.
        if isinstance(code_field, dict):
            assert code_field.get("value", "") == SAMPLE_CODE
        else:
            assert code_field == SAMPLE_CODE

    def test_should_pick_up_overwritten_component(
        self, isolated_sandbox: Path
    ) -> None:
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )
        new_code = SAMPLE_CODE.replace("'sum'", "'total'")
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=new_code,
        )

        registry = load_registry_with_user_overlay(user_id="user-alice")
        entry = registry["SumComponent"]
        code_field = entry["template"].get("code", {})
        observed = code_field.get("value") if isinstance(code_field, dict) else code_field
        assert observed == new_code

    def test_should_silently_skip_invalid_files(
        self, isolated_sandbox: Path
    ) -> None:
        # A file in `.components/` that isn't valid Python must NOT crash
        # the overlay — the rest of the user's components must still load.
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )
        # Plant a corrupt file directly under the user's components dir.
        from langflow.agentic.services.user_components import (
            _resolve_components_dir,
        )

        components_dir = _resolve_components_dir(user_id="user-alice")
        (components_dir / "BrokenComponent.py").write_text(
            "this is not valid python !!!", encoding="utf-8"
        )

        registry = load_registry_with_user_overlay(user_id="user-alice")
        assert "SumComponent" in registry
        # Broken file is simply skipped — no exception, no entry.
        assert "BrokenComponent" not in registry

    def test_should_not_clobber_base_registry_with_user_name_collision(
        self, isolated_sandbox: Path
    ) -> None:
        # If the user names their class identically to a base component,
        # the overlay must NOT silently replace the platform built-in.
        # Two acceptable behaviors:
        #   (a) skip the overlay entry (base wins)
        #   (b) namespace the user entry (e.g., "ChatInput*" or
        #       "user:ChatInput")
        # We assert (a): the base "ChatInput" stays addressable as-is.
        chatinput_code = SAMPLE_CODE.replace("SumComponent", "ChatInput")
        register_user_component(
            user_id="user-alice",
            class_name="ChatInput",
            code=chatinput_code,
        )

        registry = load_registry_with_user_overlay(user_id="user-alice")
        # Base ChatInput's template still has its original `input_value`
        # field — proves the user file didn't replace it.
        assert "template" in registry["ChatInput"]
        # The user's code is NOT exposed at the base name.
        code_field = registry["ChatInput"]["template"].get("code", {})
        observed = code_field.get("value") if isinstance(code_field, dict) else code_field
        assert observed != chatinput_code
