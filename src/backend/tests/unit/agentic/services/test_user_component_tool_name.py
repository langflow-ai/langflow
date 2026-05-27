"""Run-level proof that a user component with a generic method gets a meaningful tool name.

Production failure (2026-05-27 video): user asks the assistant to create
``RandomMenuItem`` as a tool for the agent. The assistant generates code
whose only output uses a generic method name (e.g. ``output``); the
overlay wires the component as a tool; the agent receives a tool named
``output``; the LLM never calls it because the name carries no signal.

This test closes the loop end-to-end through the production overlay
path (``load_registry_with_user_overlay`` →
``build_custom_component_template``) and asserts the final tool name is
derived from the class name, NOT the generic method. The unit-level
behavior of the rename rule is covered in
``src/lfx/tests/unit/custom/component/test_tool_name_fallback.py``;
this file is the integration glue.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import pytest
from langflow.agentic.services.user_components import register_user_component
from langflow.agentic.services.user_components_overlay import load_registry_with_user_overlay
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def isolated_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pin the per-user components dir to a tmp_path for test isolation.

    Avoids polluting the developer's real ``~/.components`` and never
    inherits leftover files from earlier failed runs.

    Duplicated from ``test_user_components_overlay.py`` instead of
    promoted to a conftest because that fixture also stubs the
    FileSystemTool's auto-login path, which is not relevant here — and
    pulling it into a conftest would couple unrelated test files.
    """
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
    (tmp_path / ".fs_pepper").write_bytes(secrets.token_bytes(32))
    return tmp_path


# Mirrors the failing production payload: no inputs, one output, generic
# method name. The class name is the only meaningful identifier.
_RANDOM_MENU_ITEM_CODE = (
    "import random\n"
    "from lfx.custom import Component\n"
    "from lfx.io import Output\n"
    "from lfx.schema import Message\n"
    "\n"
    "class RandomMenuItem(Component):\n"
    "    display_name = 'RandomMenuItem'\n"
    "    description = 'Returns a random menu item from the bar.'\n"
    "    inputs = []\n"
    "    outputs = [Output(name='item', display_name='Item', method='output')]\n"
    "    def output(self) -> Message:\n"
    "        return Message(text=random.choice(['Caipirinha', 'Coxinha']))\n"
)


@pytest.mark.asyncio
async def test_registered_component_with_generic_method_exposes_class_named_tool(
    isolated_sandbox: Path,  # noqa: ARG001 — fixture isolates the per-user .components dir
) -> None:
    """End-to-end production path through register/overlay/toolkit, asserting the LLM-facing name.

    Register → load overlay → instantiate → ``to_toolkit`` → assert the
    LLM-facing tool name. Closing the loop here is critical because the runtime rename rule
    lives in ``ComponentToolkit.get_tools`` and could silently regress
    when the overlay path is refactored (e.g. if a future change builds
    the toolkit from the static template dict instead of the
    instantiated component, the rename rule would no longer run).
    """
    register_user_component(
        user_id="user-tool-name",
        class_name="RandomMenuItem",
        code=_RANDOM_MENU_ITEM_CODE,
    )

    # Resolve the registered overlay entry the same way the assistant
    # would when wiring this component as a tool to an agent.
    registry = load_registry_with_user_overlay(user_id="user-tool-name")
    assert "RandomMenuItem" in registry

    code_value = registry["RandomMenuItem"]["template"]["code"]["value"]
    assert "class RandomMenuItem(Component)" in code_value

    # Build the live instance the runtime would build, then ask it for
    # the toolkit — exactly the path Agent._get_tools_from_inputs takes.
    _, instance = build_custom_component_template(Component(_code=code_value))
    tools = await instance.to_toolkit()

    assert len(tools) == 1, f"RandomMenuItem must produce exactly one tool; got {len(tools)}"
    assert tools[0].name == "random_menu_item", (
        f"With the fallback, the LLM-facing tool name for RandomMenuItem must be "
        f"'random_menu_item' (derived from the class name); got {tools[0].name!r}. "
        "If this is 'output' or 'process', the runtime rename rule in "
        "ComponentToolkit.get_tools regressed."
    )
    # Description must still come from the component's class-level description —
    # the rename only changes the *name*, not the description.
    assert "menu item" in tools[0].description.lower()
