"""UC3 — registry overlay merges base + user `.components/*.py`.

The overlay function is the contract the MCP tools (search, describe,
add, build_flow) use. It returns ``{component_type: template_dict}``
with the same shape ``load_local_registry()`` produces, just with the
user's registered components folded in.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING
from unittest.mock import patch

import lfx.custom.utils as lfx_utils
import pytest
from langflow.agentic.services.user_components import register_user_component
from langflow.agentic.services.user_components_overlay import (
    load_registry_with_user_overlay,
)

if TYPE_CHECKING:
    from pathlib import Path

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

    from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

    monkeypatch.setattr(
        FileSystemToolComponent,
        "_resolve_auto_login",
        lambda self: False,  # noqa: ARG005
    )

    # Defensive: other tests in the broader suite may leave the
    # ``_current_user_id_var`` ContextVar set OR leak ``_OVERLAY_ENTRY_CACHE``
    # entries that point at sandboxes from a prior tmp_path. Reset both so
    # this fixture is robust to whatever ordering pytest-xdist picks.
    from langflow.agentic.services.user_components_context import reset_current_user_id
    from langflow.agentic.services.user_components_overlay import _OVERLAY_ENTRY_CACHE

    reset_current_user_id()
    _OVERLAY_ENTRY_CACHE.clear()
    return tmp_path


class TestOverlayEntryCaching:
    """Overlay entries are cached by (path, mtime, size).

    Bug: every overlay lookup re-walked .components/ and re-ran
    build_custom_component_template (instantiate + introspect) for every
    file. SearchComponentTypes/Describe/Add/BuildFlow call the overlay
    many times per turn, so an unchanged file must be built once and the
    cache must invalidate when the file actually changes.
    """

    def test_overlay_built_once_then_rebuilt_when_file_changes(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        real_build = lfx_utils.build_custom_component_template

        register_user_component(user_id="user-alice", class_name="SumComponent", code=SAMPLE_CODE)

        with patch.object(lfx_utils, "build_custom_component_template", side_effect=real_build) as spy:
            load_registry_with_user_overlay(user_id="user-alice")
            load_registry_with_user_overlay(user_id="user-alice")
            # Second lookup hits the cache — no re-introspection.
            assert spy.call_count == 1

            # The file genuinely changes → cache invalidates → rebuild.
            register_user_component(
                user_id="user-alice",
                class_name="SumComponent",
                code=SAMPLE_CODE.replace("Adds two numbers", "Adds two numbers v2"),
            )
            load_registry_with_user_overlay(user_id="user-alice")
            assert spy.call_count == 2


class TestRegistryOverlay:
    def test_should_return_base_registry_when_no_user_components_exist(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        registry = load_registry_with_user_overlay(user_id="user-alice")
        # Base registry contains a known component.
        assert "ChatInput" in registry
        # Nothing user-overlaid yet.
        assert "SumComponent" not in registry

    def test_should_include_user_component_in_registry_after_registration(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        registry = load_registry_with_user_overlay(user_id="user-alice")

        assert "SumComponent" in registry
        # And the base entries are still there.
        assert "ChatInput" in registry

    def test_should_isolate_user_components_between_users(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        bob_registry = load_registry_with_user_overlay(user_id="user-bob")
        assert "SumComponent" not in bob_registry

        alice_registry = load_registry_with_user_overlay(user_id="user-alice")
        assert "SumComponent" in alice_registry

    def test_should_return_base_only_when_user_id_is_none(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
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

    def test_should_carry_user_code_into_overlay_template(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
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

    def test_should_mark_user_overlay_entry_as_custom(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # Bug #6 (PR-12575): a node the assistant builds from a user component
        # must land on the canvas as CustomComponent, else the frontend can't
        # resolve its type in the global template list and paints a spurious
        # "Update available" badge. The flow-builder keys that decision off the
        # ``custom`` flag the overlay stamps here.
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        registry = load_registry_with_user_overlay(user_id="user-alice")

        assert registry["SumComponent"].get("custom") is True

    def test_should_not_mark_base_builtin_entry_as_custom(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # Built-ins have a real /all template, so they must stay un-marked
        # (otherwise the flow-builder would relabel them as CustomComponent).
        registry = load_registry_with_user_overlay(user_id="user-alice")

        assert registry["ChatInput"].get("custom") is not True

    def test_overlay_outputs_match_the_user_classs_real_output(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # Production bug: a generated component whose output method/name is
        # NOT the CustomComponent default (`output`/`build_output`) builds a
        # node that declares `build_output`, so the run fails with
        # "Attribute build_output not found in <Class>". The overlay must
        # reflect the user class's ACTUAL outputs, not the base scaffold.
        code = (
            "from lfx.custom import Component\n"
            "from lfx.io import MessageTextInput, Output\n"
            "from lfx.schema import Message\n"
            "\n"
            "class PrimeChecker(Component):\n"
            "    display_name = 'PrimeChecker'\n"
            "    inputs = [MessageTextInput(name='value')]\n"
            "    outputs = [Output(name='verdict', display_name='R', method='build_result')]\n"
            "    def build_result(self) -> Message:\n"
            "        return Message(text='ok')\n"
        )
        register_user_component(user_id="user-alice", class_name="PrimeChecker", code=code)

        registry = load_registry_with_user_overlay(user_id="user-alice")
        entry = registry["PrimeChecker"]

        methods = {o.get("method") for o in entry.get("outputs", [])}
        names = {o.get("name") for o in entry.get("outputs", [])}
        # The node must call the method the user's class actually defines —
        # NOT the base CustomComponent default `build_output`.
        assert "build_result" in methods, f"overlay outputs lost the real method: {entry.get('outputs')}"
        assert "build_output" not in methods, (
            f"overlay still forces the base default build_output: {entry.get('outputs')}"
        )
        assert "verdict" in names

    def test_build_flow_node_uses_the_user_classs_real_output_method(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # End-to-end proof for the production crash: a flow built via
        # build_flow_from_spec with the user-aware registry must produce a
        # node whose output method is the one the user's class defines
        # (so the run engine doesn't raise "Attribute build_output not
        # found in <Class>").
        from lfx.graph.flow_builder.builder import build_flow_from_spec

        code = (
            "from lfx.custom import Component\n"
            "from lfx.io import MessageTextInput, Output\n"
            "from lfx.schema import Message\n"
            "\n"
            "class PrimeChecker(Component):\n"
            "    display_name = 'PrimeChecker'\n"
            "    inputs = [MessageTextInput(name='input_value')]\n"
            "    outputs = [Output(name='verdict', display_name='R', method='build_result')]\n"
            "    def build_result(self) -> Message:\n"
            "        return Message(text='ok')\n"
        )
        register_user_component(user_id="user-alice", class_name="PrimeChecker", code=code)
        registry = load_registry_with_user_overlay(user_id="user-alice")

        spec = (
            "name: T\n"
            "nodes:\n"
            "  A: ChatInput\n"
            "  B: PrimeChecker\n"
            "  C: ChatOutput\n"
            "edges:\n"
            "  A.message -> B.input_value\n"
            "  B.verdict -> C.input_value\n"
        )
        result = build_flow_from_spec(spec, registry=registry)
        assert "error" not in result, result

        nodes = result["flow"]["data"]["nodes"]
        # User components ride the canvas as CustomComponent (so the frontend
        # doesn't flag them "Update available"); find by display_name instead.
        prime = next(n for n in nodes if n["data"]["node"].get("display_name") == "PrimeChecker")
        methods = {o["method"] for o in prime["data"]["node"]["outputs"]}
        assert "build_result" in methods, prime["data"]["node"]["outputs"]
        assert "build_output" not in methods, prime["data"]["node"]["outputs"]

    async def test_registered_component_actually_runs_in_a_flow(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
        # THE production repro at the RUN level (not just the built node):
        # register a component, build a flow with it via the user-aware
        # registry, and actually execute it. Must NOT raise
        # "Attribute build_output not found in <Class>" — the run must
        # compile the node's real code and call a method that exists.
        import uuid

        from langflow.agentic.services.flow_run import run_working_flow
        from lfx.graph.flow_builder.builder import build_flow_from_spec

        code = (
            "from math import isqrt\n"
            "from lfx.custom import Component\n"
            "from lfx.io import MessageTextInput, Output\n"
            "from lfx.schema import Message\n"
            "\n"
            "class PrimeChecker(Component):\n"
            "    display_name = 'PrimeChecker'\n"
            "    inputs = [MessageTextInput(name='input_value', display_name='N', required=True)]\n"
            "    outputs = [Output(name='output', display_name='Output', method='build_output')]\n"
            "    def build_output(self) -> Message:\n"
            "        n = int(str(self.input_value).strip().strip(chr(34)).strip())\n"
            "        if n < 2:\n"
            "            return Message(text=f'{n} is not prime.')\n"
            "        for d in range(2, isqrt(n) + 1):\n"
            "            if n % d == 0:\n"
            "                return Message(text=f'{n} is not prime.')\n"
            "        return Message(text=f'{n} is prime.')\n"
        )
        register_user_component(user_id="user-alice", class_name="PrimeChecker", code=code)
        registry = load_registry_with_user_overlay(user_id="user-alice")

        spec = (
            "name: T\n"
            "nodes:\n"
            "  A: ChatInput\n"
            "  B: PrimeChecker\n"
            "  C: ChatOutput\n"
            "edges:\n"
            "  A.message -> B.input_value\n"
            "  B.output -> C.input_value\n"
            "config:\n"
            '  A.input_value: "14"\n'
            # Disable DB persistence so the test is independent of the
            # SQLAlchemy message-store schema. ChatInput / ChatOutput call
            # ``self.send_message`` on build when ``should_store_message=true``
            # (default); in batched suites that DB may lack the ``message``
            # table, surfacing as ``"(sqlite3.OperationalError) no such table"``.
            # The intent of this test is to verify the user-registered
            # ``PrimeChecker`` actually runs end-to-end — message persistence
            # is unrelated to that contract.
            "  A.should_store_message: false\n"
            "  C.should_store_message: false\n"
        )
        built = build_flow_from_spec(spec, registry=registry)
        assert "error" not in built, built

        out = await run_working_flow(
            flow_data=built["flow"],
            flow_id=str(uuid.uuid4()),
            user_id="user-alice",
        )

        assert "build_output not found" not in str(out), out
        assert "error" not in out, f"run errored: {out}"
        assert "is not prime" in out.get("result", ""), out

    async def test_overlay_template_reflects_real_inputs_and_runs_with_config(
        self,
        isolated_sandbox: Path,  # noqa: ARG002
    ) -> None:
        # The production bug: a component declaring its own input (e.g.
        # IntInput name='amount') got a generic scaffold node exposing only
        # 'input_value'. So `config: A.amount: 14` failed ("Unknown
        # parameter 'amount'"), the agent fell back to 'input_value' (which
        # the code ignores), and the component ran with its default → wrong
        # result. The overlay must introspect the REAL template.
        import uuid

        from langflow.agentic.services.flow_run import run_working_flow
        from lfx.graph.flow_builder.builder import build_flow_from_spec

        code = (
            "from math import isqrt\n"
            "from lfx.custom import Component\n"
            "from lfx.io import IntInput, Output\n"
            "from lfx.schema import Message\n"
            "\n"
            "class PrimeChecker(Component):\n"
            "    display_name = 'PrimeChecker'\n"
            "    inputs = [IntInput(name='amount', display_name='N', required=True, value=2)]\n"
            "    outputs = [Output(name='output', display_name='Out', method='build_output')]\n"
            "    def build_output(self) -> Message:\n"
            "        n = int(self.amount)\n"
            "        if n < 2:\n"
            "            return Message(text=f'{n} is not prime')\n"
            "        for d in range(2, isqrt(n) + 1):\n"
            "            if n % d == 0:\n"
            "                return Message(text=f'{n} is not prime')\n"
            "        return Message(text=f'{n} is prime')\n"
        )
        register_user_component(user_id="user-alice", class_name="PrimeChecker", code=code)
        registry = load_registry_with_user_overlay(user_id="user-alice")

        # The overlay entry's template must carry the REAL input field.
        template = registry["PrimeChecker"]["template"]
        assert "amount" in template, f"overlay lost the real input; has {list(template)}"

        spec = (
            "name: T\n"
            "nodes:\n"
            "  A: PrimeChecker\n"
            "  B: ChatOutput\n"
            "edges:\n"
            "  A.output -> B.input_value\n"
            "config:\n"
            "  A.amount: 14\n"
            # See sibling test above — ChatOutput's default
            # ``should_store_message=true`` triggers a DB write that the
            # batched suite environment may not have a schema for.
            "  B.should_store_message: false\n"
        )
        built = build_flow_from_spec(spec, registry=registry)
        assert "error" not in built, built

        out = await run_working_flow(flow_data=built["flow"], flow_id=str(uuid.uuid4()), user_id="user-alice")
        assert "error" not in out, out
        # 14 is not prime — must reflect the CONFIGURED 14, not the default 2.
        assert "14 is not prime" in out.get("result", ""), out

    def test_should_pick_up_overwritten_component(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
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

    def test_should_silently_skip_invalid_files(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
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
        (components_dir / "BrokenComponent.py").write_text("this is not valid python !!!", encoding="utf-8")

        registry = load_registry_with_user_overlay(user_id="user-alice")
        assert "SumComponent" in registry
        # Broken file is simply skipped — no exception, no entry.
        assert "BrokenComponent" not in registry

    def test_should_not_clobber_base_registry_with_user_name_collision(self, isolated_sandbox: Path) -> None:  # noqa: ARG002
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
