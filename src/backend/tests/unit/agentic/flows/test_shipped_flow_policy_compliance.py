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
from langflow.agentic.services.flow_preparation import load_and_prepare_flow
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
