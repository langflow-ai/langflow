"""The shipped Langflow Assistant flow must run under the hardened enterprise settings.

Reproduced from LE-2321 / LE-2322 (Verizon alpha feedback). ``LangflowAssistant.json``
is first-party content, but it was loaded through the same gates as tenant-supplied
flows and did not satisfy them:

* ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`` blocked the flow's own inline
  ``DataFrameKeywordSearch`` node, which has no registered server counterpart.
* ``LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true`` blocked the flow's own ``Directory``
  node, rewritten at load time to the installed lfx components directory.

Both settings are baked into the enterprise image, so the assistant returned the same
error to every message, including "hi", for every user.

Half of this file is containment. The exemptions must stay narrower than the bug:
scoped to graph construction (not the agent's whole turn), to the unregistered-component
gate (not catalog policy or the code-interpreter block), and to package reads (not
writes). Each of those is asserted negatively below, because the failure mode is a
bypass that no positive test would notice.
"""

import json
import uuid
from pathlib import Path

import pytest
from langflow.agentic.services.flow_preparation import load_and_prepare_flow
from lfx.interface.components import get_and_cache_all_types_dict
from lfx.services.deps import get_settings_service
from lfx.utils.file_path_security import LocalFileAccessError, enforce_local_file_access
from lfx.utils.flow_validation import (
    CODE_EXECUTION_COMPONENT_TYPES,
    CustomComponentValidationError,
    validate_flow_for_current_settings,
)
from lfx.utils.trusted_flow import packaged_flow_load_scope, packaged_flow_run_scope

import lfx

FLOW_PATH = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows" / "LangflowAssistant.json"
LFX_COMPONENTS_DIR = str(Path(lfx.__file__).parent / "components")
SCOPE = str(uuid.uuid4())

# A tenant flow carrying unregistered code -- the thing the component gate exists to stop.
TENANT_FLOW = {
    "nodes": [
        {
            "id": "Custom-abc12",
            "data": {
                "id": "Custom-abc12",
                "type": "TenantWritten",
                "node": {
                    "display_name": "Tenant Written",
                    "template": {"code": {"value": "class TenantWritten:\n    pass\n"}},
                },
            },
        }
    ],
    "edges": [],
}


def _prepared_flow() -> dict:
    """The flow exactly as production prepares it (both path injections applied)."""
    return json.loads(load_and_prepare_flow(FLOW_PATH, None, None, None)).get("data", {})


@pytest.fixture
def hardened_settings(tmp_path):
    """The three settings the enterprise image bakes in (Dockerfile:362-364)."""
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
        """LE-2321: the assistant must not be blocked by its own component policy."""
        await get_and_cache_all_types_dict(get_settings_service())
        with packaged_flow_load_scope():
            validate_flow_for_current_settings(_prepared_flow())

    def test_should_read_its_own_component_library(self):
        """LE-2322: the Directory node's package path must be readable during the run."""
        with packaged_flow_run_scope():
            enforce_local_file_access(LFX_COMPONENTS_DIR, scope_ids=(SCOPE,))


@pytest.mark.usefixtures("hardened_settings")
class TestExemptionIsScopedToConstruction:
    """The component gate must not stay lifted for the agent's whole turn.

    The assistant builds and runs tenant flows mid-turn (``run_working_flow``,
    ``flow_graph_build_check``), each reaching this validator via ``Graph.from_payload``.
    """

    async def test_should_still_block_tenant_code_during_the_run(self):
        await get_and_cache_all_types_dict(get_settings_service())
        with packaged_flow_run_scope(), pytest.raises(CustomComponentValidationError):
            validate_flow_for_current_settings(TENANT_FLOW)

    async def test_should_still_block_tenant_code_outside_every_scope(self):
        await get_and_cache_all_types_dict(get_settings_service())
        with pytest.raises(CustomComponentValidationError):
            validate_flow_for_current_settings(TENANT_FLOW)

    async def test_should_still_block_the_shipped_flow_outside_the_load_scope(self):
        """The identical artifact is not exempt just because it is the assistant's."""
        await get_and_cache_all_types_dict(get_settings_service())
        with pytest.raises(CustomComponentValidationError, match="custom components are not allowed"):
            validate_flow_for_current_settings(_prepared_flow())


@pytest.mark.usefixtures("hardened_settings")
class TestExemptionIsScopedToTheComponentGate:
    """Catalog policy and the code-interpreter block still apply to packaged flows."""

    async def test_should_still_block_code_interpreters_inside_the_load_scope(self):
        await get_and_cache_all_types_dict(get_settings_service())
        interpreter_flow = {
            "nodes": [
                {
                    "id": "PythonREPLComponent-x1",
                    "data": {
                        "id": "PythonREPLComponent-x1",
                        "type": "PythonCodeStructuredTool",
                        "node": {"display_name": "Python Code Structured", "template": {}},
                    },
                }
            ],
            "edges": [],
        }
        with packaged_flow_load_scope(), pytest.raises(Exception, match="code-execution"):
            validate_flow_for_current_settings(interpreter_flow)

    def test_shipped_flow_carries_no_code_interpreter(self):
        """Keeps the exemption's blast radius where it was put."""
        types = {n.get("data", {}).get("type") for n in _prepared_flow().get("nodes", [])}
        assert not (types & CODE_EXECUTION_COMPONENT_TYPES)


@pytest.mark.usefixtures("hardened_settings")
class TestFileExemptionIsContained:
    def test_should_refuse_writes_into_the_package_even_inside_the_marker(self):
        """A write into site-packages is code execution on the next component discovery."""
        with packaged_flow_run_scope(), pytest.raises(LocalFileAccessError):
            enforce_local_file_access(LFX_COMPONENTS_DIR, scope_ids=(SCOPE,), for_write=True)

    def test_should_still_block_package_reads_outside_the_marker(self):
        with pytest.raises(LocalFileAccessError):
            enforce_local_file_access(LFX_COMPONENTS_DIR, scope_ids=(SCOPE,))

    @pytest.mark.parametrize("forbidden", ["/etc/passwd", "/usr/bin", str(Path.home())])
    def test_should_still_block_arbitrary_server_paths_inside_the_marker(self, forbidden):
        with packaged_flow_run_scope(), pytest.raises(LocalFileAccessError):
            enforce_local_file_access(forbidden, scope_ids=(SCOPE,))

    def test_should_still_block_reserved_secret_files_inside_the_marker(self, hardened_settings):
        secret = hardened_settings / "secret_key"
        secret.write_text("x", encoding="utf-8")
        with packaged_flow_run_scope(), pytest.raises(LocalFileAccessError):
            enforce_local_file_access(str(secret), scope_ids=(SCOPE,))

    def test_should_not_leak_either_marker_out_of_its_scope(self):
        with packaged_flow_run_scope():
            pass
        with pytest.raises(LocalFileAccessError):
            enforce_local_file_access(LFX_COMPONENTS_DIR, scope_ids=(SCOPE,))
