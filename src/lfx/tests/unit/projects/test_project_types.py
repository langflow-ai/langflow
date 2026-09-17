"""Project types are a vocabulary both runtimes can read.

The module lives in lfx so the standalone runtime can name a folder's type without langflow
installed, which is what these tests hold onto: the registry, the two shipped types, and the
one property that makes the design work, that every form field's write-through target is a
real input on a real component.
"""

import pytest
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.inputs.inputs import StrInput

from lfx.projects import (
    CORE_PROJECT_TYPES,
    DEFAULT_PROJECT_TYPE,
    FieldTarget,
    ProjectType,
    ProjectTypeField,
    all_project_types,
    get_project_type,
    register_project_type,
    registered_project_types,
)

# The components a write-through target may name today. A target pointing anywhere else is a
# typo until the component is added here on purpose.
TARGETABLE_COMPONENTS = {AgentComponent.name: AgentComponent}


class TestRegistry:
    def test_shipped_types_are_registered_on_import(self):
        assert registered_project_types() == ("agent-harness", "eval-suite", "flows", "skill-pack", "tool-pack")

    def test_default_type_is_registered(self):
        assert get_project_type(DEFAULT_PROJECT_TYPE).name == DEFAULT_PROJECT_TYPE

    def test_core_types_are_the_shipped_ones(self):
        assert set(registered_project_types()) == CORE_PROJECT_TYPES

    def test_unknown_type_names_what_is_available(self):
        with pytest.raises(ValueError, match="agent-harness"):
            get_project_type("not-a-type")

    def test_registering_returns_the_type_so_it_can_be_bound(self):
        project_type = ProjectType(name="test-bound", display_name="Bound", icon="Box")

        assert register_project_type(project_type) is project_type

    def test_re_registering_the_same_object_is_allowed(self):
        """Re-importing a module that registers a type must not explode."""
        project_type = ProjectType(name="test-reimport", display_name="Re", icon="Box")

        register_project_type(project_type)
        register_project_type(project_type)

        assert get_project_type("test-reimport") is project_type

    def test_a_different_type_cannot_take_a_registered_name(self):
        register_project_type(ProjectType(name="test-taken", display_name="First", icon="Box"))

        with pytest.raises(ValueError, match="already registered"):
            register_project_type(ProjectType(name="test-taken", display_name="Second", icon="Box"))

    def test_all_project_types_matches_the_name_order(self):
        assert [t.name for t in all_project_types()] == list(registered_project_types())

    @pytest.fixture(autouse=True)
    def _keep_the_registry_clean(self):
        """Tests here register throwaway types; the shipped ones must survive them."""
        from lfx.projects import registry

        before = dict(registry._PROJECT_TYPES)
        yield
        registry._PROJECT_TYPES.clear()
        registry._PROJECT_TYPES.update(before)


class TestFlows:
    def test_flows_renders_no_form(self):
        """A plain project has nothing to configure, which is what makes it the default."""
        assert get_project_type("flows").fields == ()
        assert get_project_type("flows").to_template() == {}


class TestAgentHarness:
    @pytest.fixture
    def harness(self):
        return get_project_type("agent-harness")

    def test_the_form_is_the_harness_builder(self, harness):
        assert harness.field_names() == (
            "system_prompt",
            "model",
            "tools",
            "tool_packs",
            "n_messages",
            "skill_packs",
            "tool_policy",
            "context_strategy",
            "context_turns",
            "compaction",
            "compaction_trigger_tokens",
            "compaction_keep_messages",
            "max_iterations",
            "hooks",
        )

    def test_the_form_reads_as_sections(self, harness):
        """The type decides how its own form is grouped, so the UI does not hardcode the order."""
        assert harness.sections() == ("Instructions", "Model", "Tools", "Runtime", "Skills", "Hooks")

    def test_every_field_belongs_to_a_section(self, harness):
        assert all(field.section for field in harness.fields)

    def test_tools_asks_the_ui_for_a_project_scoped_widget(self, harness):
        """No canvas widget can pick flows out of a project, so the type names the one that can."""
        assert harness.to_template()["tools"]["renders"] == "project_flows"

    def test_instructions_asks_for_a_real_editor(self, harness):
        """A node-sized one-line input with a modal is the wrong shape for the main field."""
        assert harness.to_template()["system_prompt"]["renders"] == "long_text"

    def test_visible_fields_use_the_available_page_widgets(self, harness):
        """Everything else must render with a shipped canvas widget, or the form is bespoke."""
        bespoke = {f.name: f.renders for f in harness.fields if f.renders and f.input.show}

        assert bespoke == {
            "system_prompt": "long_text",
            "tools": "project_flows",
            "tool_packs": "project_refs",
            "skill_packs": "skill_pack_refs",
            "hooks": "hook_flows",
        }

    def test_every_field_renders_with_a_shipped_widget(self, harness):
        """The form reuses the canvas field renderer, so each field must carry a real input type."""
        for name, rendered in harness.to_template().items():
            assert rendered["type"], f"{name} has no input type to render with"
            assert rendered["name"] == name
            assert rendered["display_name"], f"{name} has no label"
            assert rendered["info"], f"{name} has no help text"

    def test_nothing_is_required_so_a_new_harness_is_valid_empty(self, harness):
        """Creating a typed project must not fail validation before the user fills the form."""
        required = [name for name, r in harness.to_template().items() if r.get("required")]

        assert required == []

    def test_defaults_match_the_runtime_defaults(self, harness):
        """An untouched harness must behave like an Agent dropped on a blank canvas."""
        agent_defaults = {i.name: i for i in AgentComponent.inputs}
        template = harness.to_template()

        for field in harness.fields:
            if field.writes_to is None:
                continue
            agent_input = agent_defaults[field.writes_to.input_name]
            if agent_input.value in (None, ""):
                continue
            assert template[field.name]["value"] == agent_input.value, (
                f"{field.name} defaults differently from {field.writes_to.input_name} on Agent"
            )

    def test_compaction_offers_only_what_the_runtime_honours(self, harness):
        """Every offered mode has a tested middleware implementation."""
        assert harness.to_template()["compaction"]["options"] == ["off", "summarize"]
        assert harness.to_template()["compaction"]["supports_flow_binding"] is True


class TestSections:
    def test_a_type_with_no_fields_has_no_sections(self):
        assert get_project_type("flows").sections() == ()

    def test_sections_keep_the_order_their_first_field_declares(self):
        project_type = ProjectType(
            name="test-sections",
            display_name="Sections",
            icon="Box",
            fields=(
                ProjectTypeField(name="b", section="Second", input=StrInput(name="b", display_name="B")),
                ProjectTypeField(name="a", section="First", input=StrInput(name="a", display_name="A")),
                ProjectTypeField(name="c", section="Second", input=StrInput(name="c", display_name="C")),
            ),
        )

        assert project_type.sections() == ("Second", "First")

    def test_a_field_without_a_section_does_not_emit_one(self):
        """An ungrouped field leaves the key out, so the UI can tell it apart from a named group."""
        field = ProjectTypeField(name="f", input=StrInput(name="f", display_name="F"))

        assert "section" not in field.to_template()

    def test_a_field_without_a_widget_hint_does_not_emit_one(self):
        field = ProjectTypeField(name="f", input=StrInput(name="f", display_name="F"))

        assert "renders" not in field.to_template()


class TestWriteThroughTargetsAreReal:
    """The form writes through to the flow, so a target that does not exist is a broken promise."""

    def _targets(self):
        for project_type in all_project_types():
            for field in project_type.fields:
                if field.writes_to is not None:
                    yield project_type.name, field.name, field.writes_to

    def test_at_least_one_type_writes_through(self):
        assert list(self._targets())

    def test_every_target_component_is_known(self):
        for type_name, field_name, target in self._targets():
            assert target.component_type in TARGETABLE_COMPONENTS, (
                f"{type_name}.{field_name} targets unknown component {target.component_type!r}"
            )

    def test_every_target_input_exists_on_its_component(self):
        for type_name, field_name, target in self._targets():
            component = TARGETABLE_COMPONENTS[target.component_type]
            names = {i.name for i in component.inputs}
            assert target.input_name in names, (
                f"{type_name}.{field_name} targets {target.component_type}.{target.input_name}, which does not exist"
            )


class TestStandaloneImport:
    """The vocabulary lives in lfx precisely so the standalone runtime can read it."""

    def test_project_types_import_without_langflow(self):
        import builtins as py_builtins
        import importlib
        import sys

        purged = {name: mod for name, mod in sys.modules.items() if name.startswith("lfx.projects")}
        for name in purged:
            del sys.modules[name]

        real_import = py_builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name == "langflow" or name.startswith("langflow."):
                msg = f"No module named {name!r}"
                raise ModuleNotFoundError(msg, name=name)
            return real_import(name, *args, **kwargs)

        py_builtins.__import__ = guarded_import
        try:
            module = importlib.import_module("lfx.projects")
            assert "agent-harness" in module.registered_project_types()
        finally:
            py_builtins.__import__ = real_import
            for name in [n for n in sys.modules if n.startswith("lfx.projects")]:
                del sys.modules[name]
            sys.modules.update(purged)


class TestFieldSerialisation:
    def test_the_field_name_wins_over_the_input_name(self):
        """``project_config`` is keyed by field name, so that is what the API must emit."""
        field = ProjectTypeField(name="outer", input=StrInput(name="inner", display_name="Inner"))

        assert field.to_template()["name"] == "outer"

    def test_info_falls_back_to_the_field_when_the_input_has_none(self):
        field = ProjectTypeField(name="f", input=StrInput(name="f", display_name="F"), info="from the field")

        assert field.to_template()["info"] == "from the field"

    def test_the_input_keeps_its_own_info(self):
        field = ProjectTypeField(
            name="f",
            input=StrInput(name="f", display_name="F", info="from the input"),
            info="from the field",
        )

        assert field.to_template()["info"] == "from the input"

    def test_a_target_is_a_component_and_an_input(self):
        target = FieldTarget("Agent", "system_prompt")

        assert (target.component_type, target.input_name) == ("Agent", "system_prompt")
