"""The shipped Langflow Assistant flow must run under the hardened enterprise settings.

``LangflowAssistant.json`` is first-party content, but it loads through the same gates as
tenant-supplied flows and used to fail them:

* ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`` blocked the flow's own inline keyword-search
  node, which had no registered server counterpart.
* ``LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true`` blocked the flow's ``Directory`` node, which
  read the installed component library -- a path outside every user's storage scope.

Both settings are baked into the enterprise image, so the assistant returned the same error
to every message, including "hi", for every user.

The fix removes the two nodes that needed exemptions rather than exempting them: one
registered ``ComponentLibrarySearch`` component reads its own package source directly. It
takes no path input, so no tenant-controlled path exists for ``enforce_local_file_access``
to gate, and it resolves through the ordinary registered-component path.

``test_shipped_flow_builds_under_hardened_settings`` is the regression test that matters:
validation alone passed even while the build gate rejected the flow, so a test that only
validates cannot catch this class of bug.
"""

import json
from pathlib import Path

import pytest
from langflow.agentic.helpers.validation import validate_component_runtime
from langflow.agentic.services.flow_preparation import (
    CUSTOM_COMPONENTS_DISABLED_NOTICE,
    inject_component_policy_into_flow,
    load_and_prepare_flow,
)
from lfx.components.processing import component_library_search
from lfx.interface.components import get_and_cache_all_types_dict
from lfx.load import aload_flow_from_json
from lfx.services.deps import get_settings_service
from lfx.utils.flow_validation import get_component_hash_lookups_for_validation

FLOWS_DIR = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows"
FLOW_PATH = FLOWS_DIR / "LangflowAssistant.json"


@pytest.fixture
def hardened_settings():
    """The settings the enterprise image bakes in."""
    settings = get_settings_service().settings
    saved = (
        settings.allow_custom_components,
        settings.block_code_interpreter_components,
        settings.restrict_local_file_access,
    )
    settings.allow_custom_components = False
    settings.block_code_interpreter_components = True
    settings.restrict_local_file_access = True
    try:
        yield settings
    finally:
        (
            settings.allow_custom_components,
            settings.block_code_interpreter_components,
            settings.restrict_local_file_access,
        ) = saved


def _prepared(flow_path: Path) -> dict:
    return json.loads(load_and_prepare_flow(flow_path, None, None, None))


@pytest.mark.usefixtures("hardened_settings")
class TestShippedAssistantFlowRunsHardened:
    async def test_shipped_flow_builds_under_hardened_settings(self):
        """Builds, not just validates -- the build gate is a second, separate check.

        ``Graph.from_payload`` runs code substitution, validation, and component
        instantiation. Instantiation calls ``resolve_trusted_code_for_build``, which fails
        closed for any code with no registered server counterpart. A flow can clear
        validation and still be refused here, which is exactly how the assistant broke.
        """
        await get_and_cache_all_types_dict(get_settings_service())
        graph = await aload_flow_from_json(_prepared(FLOW_PATH), disable_logs=True)
        assert graph.vertices, "shipped flow built no vertices"

    async def test_search_component_reads_the_library_with_no_scope_or_exemption(self):
        """No user scope, no flow scope, no graph marker -- and no exemption needed."""
        await get_and_cache_all_types_dict(get_settings_service())
        graph = await aload_flow_from_json(_prepared(FLOW_PATH), disable_logs=True)
        component = next(v.custom_component for v in graph.vertices if v.id.startswith("ComponentLibrarySearch"))
        component.column = "text"
        component.keywords = ["ChatInput"]
        component.match_type = "any"
        component.case_sensitive = False
        component.number_candidates = 5

        results = component.search()
        assert len(results) > 0, "component library search returned nothing"
        assert set(results.columns) >= {"file_path", "text"}


class TestShippedFlowsStayRegistered:
    """Fails loudly if a shipped flow regains a component the server does not know.

    Keyed to the registry rather than to a component name, so it catches *any* future inline
    node -- the previous guard tested for one hardcoded type and would have missed a second.
    """

    async def test_shipped_flows_carry_no_unregistered_component_types(self):
        known = await get_and_cache_all_types_dict(get_settings_service()) and (
            get_component_hash_lookups_for_validation() or {}
        )
        unregistered = []
        for flow_file in sorted(FLOWS_DIR.glob("*.json")):
            data = json.loads(flow_file.read_text(encoding="utf-8"))
            for node in data.get("data", data).get("nodes", []):
                node_data = node.get("data", {})
                code = (node_data.get("node", {}).get("template", {}).get("code") or {}).get("value")
                component_type = node_data.get("type")
                if code and component_type not in known:
                    unregistered.append(f"{flow_file.name}: {component_type}")

        assert not unregistered, (
            "shipped flows carry component types with no registered server counterpart; they will be "
            "blocked under LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false:\n" + "\n".join(unregistered)
        )

    def test_search_node_embeds_the_installed_component_source(self):
        """The flow's stored copy must equal the component on disk.

        Only restricted mode substitutes the server's copy at build time; with custom
        components allowed (the default) the node's *stored* bytes are what execute. A
        previous fix edited the component and left the flow's embedded copy behind, so the
        change never ran in the deployment it targeted.
        """
        installed = Path(component_library_search.__file__).read_text(encoding="utf-8")
        flow = json.loads(FLOW_PATH.read_text(encoding="utf-8"))
        embedded = next(
            node["data"]["node"]["template"]["code"]["value"]
            for node in flow["data"]["nodes"]
            if node["data"].get("type") == "ComponentLibrarySearch"
        )
        assert embedded == installed, (
            f"{FLOW_PATH.name} embeds a stale copy of component_library_search.py; "
            "re-copy the file into the node's template.code.value"
        )


class TestSearchNodeCanvasDefaults:
    """The node has to make sense to a human who opens it, not only to the agent.

    ``column`` and ``keywords`` are ``tool_mode`` inputs, so the agent supplies both on every
    call and the stored values never run in the assistant's own turns. They are still what the
    canvas renders and what someone inspecting or hand-running the node gets, which is the
    only path these two guards cover.
    """

    @staticmethod
    def _search_node_template() -> dict:
        flow = json.loads(FLOW_PATH.read_text(encoding="utf-8"))
        return next(
            node["data"]["node"]["template"]
            for node in flow["data"]["nodes"]
            if node["data"].get("type") == "ComponentLibrarySearch"
        )

    def test_keywords_is_declared_required(self):
        """``search`` raises without keywords, so the canvas must mark the field before the run.

        Declared on the component; asserted on the shipped node because the flow JSON carries
        its own serialized copy of the template, which is what the UI actually reads.
        """
        assert self._search_node_template()["keywords"]["required"] is True, (
            "ComponentLibrarySearch.keywords is required at runtime but renders as optional; "
            "the shipped node's template is out of sync with the component declaration"
        )

    def test_stored_keyword_default_matches_the_installed_library(self):
        """A required field ships with a value, and that value has to find something.

        The node inherited ``composio`` from the inline component it replaced. The installed
        ``lfx/components/composio`` package holds only an ``__init__`` re-export, which the
        search skips, so the shipped default returned zero rows for anyone running the node
        by hand -- which reads as "the library has no such component".
        """
        template = self._search_node_template()
        component = component_library_search.ComponentLibrarySearch()
        component.column = template["column"]["value"]
        component.keywords = template["keywords"]["value"]
        component.match_type = template["match_type"]["value"]
        component.case_sensitive = template["case_sensitive"]["value"]
        component.number_candidates = template["number_candidates"]["value"]

        assert len(component.search()) > 0, (
            f"the shipped node's stored keywords {template['keywords']['value']!r} match no "
            f"component in the installed library on column {template['column']['value']!r}"
        )


class TestAdvertisedCapabilitiesFollowServerPolicy:
    """A capability the server forbids must not be offered in the greeting.

    The shipped prompt tells the assistant to "mention all three capabilities", one of which
    is generating custom components. Under ``allow_custom_components=false`` that offer costs
    the user a turn to reach a refusal it could have avoided making.
    """

    @staticmethod
    def _agent_prompts(flow: dict) -> list[str]:
        return [
            node["data"]["node"]["template"]["system_prompt"]["value"]
            for node in flow["data"]["nodes"]
            if node["data"].get("type") == "Agent"
        ]

    def test_permissive_settings_leave_the_prompt_untouched(self):
        """The default deployment can honor all three, so nothing is added."""
        settings = get_settings_service().settings
        saved = settings.allow_custom_components
        settings.allow_custom_components = True
        try:
            prompts = self._agent_prompts(_prepared(FLOW_PATH))
        finally:
            settings.allow_custom_components = saved

        assert prompts, "shipped flow has no Agent with a system prompt"
        assert all(CUSTOM_COMPONENTS_DISABLED_NOTICE not in p for p in prompts)

    @pytest.mark.usefixtures("hardened_settings")
    def test_hardened_settings_withdraw_the_offer_on_every_agent(self):
        prompts = self._agent_prompts(_prepared(FLOW_PATH))
        assert prompts, "shipped flow has no Agent with a system prompt"
        assert all(CUSTOM_COMPONENTS_DISABLED_NOTICE in p for p in prompts)

    @pytest.mark.usefixtures("hardened_settings")
    def test_preparing_twice_does_not_stack_the_notice(self):
        """``load_and_prepare_flow`` runs per request; the notice must not accumulate."""
        flow = _prepared(FLOW_PATH)
        inject_component_policy_into_flow(inject_component_policy_into_flow(flow))
        for prompt in self._agent_prompts(flow):
            assert prompt.count(CUSTOM_COMPONENTS_DISABLED_NOTICE) == 1


class TestPolicyDenialsAddressTheUser:
    """Denials an end user reads name the administrator, not the operator-only setting.

    Same rule the file-access and SSRF denials follow in
    ``lfx/tests/unit/utils/test_denial_messages_hide_settings.py``. This one was missed: it
    returned the raw ``allow_custom_components=false`` to the chat (LE-2322 finding 1).
    """

    @pytest.mark.usefixtures("hardened_settings")
    async def test_custom_component_denial_names_no_setting(self):
        message = await validate_component_runtime("class X:\n    pass\n")
        assert message is not None
        assert "allow_custom_components" not in message
        assert "LANGFLOW_" not in message

    @pytest.mark.usefixtures("hardened_settings")
    async def test_custom_component_denial_keeps_its_remediation(self):
        message = await validate_component_runtime("class X:\n    pass\n")
        assert message is not None
        assert "administrator" in message
        assert "build what you need from the components already in the library" in message
