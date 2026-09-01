"""The shipped Langflow Assistant flow must run under the hardened enterprise settings.

``LangflowAssistant.json`` is first-party content, but it was loaded through the same
gates as tenant-supplied flows and did not satisfy them:

* ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`` blocked the flow's own inline
  ``DataFrameKeywordSearch`` node, which has no registered server counterpart.
* ``LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true`` blocked the flow's own ``Directory``
  node, rewritten at load time to the installed lfx components directory.

Both settings are baked into the enterprise image, so the assistant returned the same
error to every message, including "hi", for every user.

Both exemptions are keyed to identity, never to a time window or a caller:
``PACKAGED_FLOW_TRUSTED_CODE`` names one exact (type, source-hash) pair, and the file
read requires the component's own ``Graph`` object to carry the packaged marker. The
containment tests below are the point of this file -- a bypass is the failure mode, and
no positive test would notice one.
"""

import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from langflow.agentic.services.flow_preparation import load_and_prepare_flow
from lfx.interface.components import get_and_cache_all_types_dict
from lfx.services.deps import get_settings_service
from lfx.utils.file_path_security import (
    PACKAGED_FIRST_PARTY_GRAPH_ATTR,
    LocalFileAccessError,
    component_may_read_package_resources,
    enforce_local_file_access,
)
from lfx.utils.flow_validation import (
    CODE_EXECUTION_COMPONENT_TYPES,
    PACKAGED_FLOW_TRUSTED_CODE,
    CustomComponentValidationError,
    _compute_code_hash,
    validate_flow_for_current_settings,
)

import lfx

FLOWS_DIR = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows"
FLOW_PATH = FLOWS_DIR / "LangflowAssistant.json"
LFX_COMPONENTS_DIR = str(Path(lfx.__file__).parent / "components")
SCOPE = str(uuid.uuid4())

TENANT_CODE = "class TenantWritten:\n    pass\n"


def _tenant_flow(component_type: str = "TenantWritten", code: str = TENANT_CODE) -> dict:
    return {
        "nodes": [
            {
                "id": "Custom-abc12",
                "data": {
                    "id": "Custom-abc12",
                    "type": component_type,
                    "node": {"display_name": "Tenant", "template": {"code": {"value": code}}},
                },
            }
        ],
        "edges": [],
    }


def _prepared_flow() -> dict:
    return json.loads(load_and_prepare_flow(FLOW_PATH, None, None, None)).get("data", {})


def _component(*, packaged: bool):
    graph = SimpleNamespace(flow_id=None, source_flow_id=None)
    if packaged:
        setattr(graph, PACKAGED_FIRST_PARTY_GRAPH_ATTR, True)
    return SimpleNamespace(_vertex=SimpleNamespace(graph=graph))


@pytest.fixture
def hardened_settings(tmp_path):
    """The three settings the enterprise image bakes in."""
    settings = get_settings_service().settings
    saved = (
        settings.allow_custom_components,
        settings.block_code_interpreter_components,
        settings.restrict_local_file_access,
        settings.config_dir,
    )
    settings.allow_custom_components = False
    settings.block_code_interpreter_components = True
    settings.restrict_local_file_access = True
    settings.config_dir = str(tmp_path)
    (tmp_path / SCOPE).mkdir(parents=True, exist_ok=True)
    try:
        yield tmp_path
    finally:
        (
            settings.allow_custom_components,
            settings.block_code_interpreter_components,
            settings.restrict_local_file_access,
            settings.config_dir,
        ) = saved


@pytest.mark.usefixtures("hardened_settings")
class TestShippedAssistantFlowRunsHardened:
    async def test_should_build_the_shipped_flow(self):
        """No scope, no marker, no caller privilege -- the allowlisted source is enough."""
        await get_and_cache_all_types_dict(get_settings_service())
        validate_flow_for_current_settings(_prepared_flow())

    def test_should_read_its_own_component_library(self):
        enforce_local_file_access(
            LFX_COMPONENTS_DIR,
            scope_ids=(SCOPE,),
            allow_package_read=component_may_read_package_resources(_component(packaged=True)),
        )


class TestAllowlistTracksTheShippedSource:
    """Fails loudly if the shipped flow is edited without updating the allowlist."""

    def test_packaged_flow_inline_components_are_allowlisted(self):
        unlisted = []
        for flow_file in sorted(FLOWS_DIR.glob("*.json")):
            data = json.loads(flow_file.read_text(encoding="utf-8"))
            for node in data.get("data", data).get("nodes", []):
                node_data = node.get("data", {})
                code = (node_data.get("node", {}).get("template", {}).get("code") or {}).get("value")
                if not code:
                    continue
                entry = (node_data.get("type"), _compute_code_hash(code))
                # A registered server type needs no entry; only unregistered inline code does.
                if entry[0] == "DataFrameKeywordSearch" and entry not in PACKAGED_FLOW_TRUSTED_CODE:
                    unlisted.append(f"{flow_file.name}: {entry}")
        assert not unlisted, "shipped inline component changed; update PACKAGED_FLOW_TRUSTED_CODE:\n" + "\n".join(
            unlisted
        )


@pytest.mark.usefixtures("hardened_settings")
class TestComponentExemptionIsKeyedToIdentity:
    async def test_should_block_tenant_code(self):
        await get_and_cache_all_types_dict(get_settings_service())
        with pytest.raises(CustomComponentValidationError):
            validate_flow_for_current_settings(_tenant_flow())

    async def test_should_block_the_allowlisted_type_carrying_different_code(self):
        """The type name alone grants nothing -- the source must match."""
        await get_and_cache_all_types_dict(get_settings_service())
        with pytest.raises(CustomComponentValidationError):
            validate_flow_for_current_settings(_tenant_flow(component_type="DataFrameKeywordSearch"))

    async def test_should_block_allowlisted_code_under_a_different_type(self):
        """And the source alone grants nothing -- the pair must match."""
        await get_and_cache_all_types_dict(get_settings_service())
        shipped_code = next(
            n["data"]["node"]["template"]["code"]["value"]
            for n in _prepared_flow()["nodes"]
            if n["data"].get("type") == "DataFrameKeywordSearch"
        )
        with pytest.raises(CustomComponentValidationError):
            validate_flow_for_current_settings(_tenant_flow(component_type="SomethingElse", code=shipped_code))

    async def test_should_still_block_code_interpreters(self):
        """Catalog policy and the code-interpreter block are not part of the exemption."""
        await get_and_cache_all_types_dict(get_settings_service())
        interpreter_flow = _tenant_flow(component_type="PythonCodeStructuredTool")
        with pytest.raises(Exception, match="code-execution"):
            validate_flow_for_current_settings(interpreter_flow)

    def test_shipped_flow_carries_no_code_interpreter(self):
        types = {n.get("data", {}).get("type") for n in _prepared_flow().get("nodes", [])}
        assert not (types & CODE_EXECUTION_COMPONENT_TYPES)


@pytest.mark.usefixtures("hardened_settings")
class TestFileExemptionIsKeyedToTheGraphObject:
    def test_a_tenant_graph_cannot_read_the_package(self):
        """The marker lives on one Graph object; another graph is simply a different object."""
        assert component_may_read_package_resources(_component(packaged=False)) is False
        with pytest.raises(LocalFileAccessError):
            enforce_local_file_access(
                LFX_COMPONENTS_DIR,
                scope_ids=(SCOPE,),
                allow_package_read=component_may_read_package_resources(_component(packaged=False)),
            )

    def test_a_component_with_no_graph_cannot_read_the_package(self):
        assert component_may_read_package_resources(SimpleNamespace()) is False

    def test_write_is_refused_even_for_the_packaged_graph(self):
        with pytest.raises(LocalFileAccessError):
            enforce_local_file_access(LFX_COMPONENTS_DIR, scope_ids=(SCOPE,), allow_package_read=True, for_write=True)

    @pytest.mark.parametrize("forbidden", ["/etc/passwd", "/usr/bin", str(Path.home())])
    def test_arbitrary_server_paths_stay_blocked(self, forbidden):
        with pytest.raises(LocalFileAccessError):
            enforce_local_file_access(forbidden, scope_ids=(SCOPE,), allow_package_read=True)

    def test_reserved_secret_files_stay_blocked(self, hardened_settings):
        secret = hardened_settings / "secret_key"
        secret.write_text("x", encoding="utf-8")
        with pytest.raises(LocalFileAccessError):
            enforce_local_file_access(str(secret), scope_ids=(SCOPE,), allow_package_read=True)
