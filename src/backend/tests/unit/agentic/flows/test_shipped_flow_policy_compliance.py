"""The shipped Langflow Assistant flow must run under the hardened enterprise settings.

Reproduced from LE-2321 / LE-2322 (Verizon alpha feedback). ``LangflowAssistant.json``
is first-party content, but it was loaded through the same gates as tenant-supplied
flows and did not satisfy them:

* ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`` blocked the flow's own inline
  ``DataFrameKeywordSearch`` node, which has no registered server counterpart.
* ``LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true`` blocked the flow's own ``Directory``
  node, rewritten at load time to the installed lfx components directory.

Both settings are baked into the enterprise image (Dockerfile), so the assistant
returned the same error to every message, including "hi", for every user.

``lfx.utils.trusted_flow.packaged_flow_scope`` now marks the packaged artifact as
first-party. The containment tests below matter as much as the fix: the marker must
not become a general escape hatch for tenant content or for arbitrary server paths.
"""

import json
import uuid
from pathlib import Path

import pytest
from langflow.agentic.services.flow_preparation import load_and_prepare_flow
from lfx.interface.components import get_and_cache_all_types_dict
from lfx.services.deps import get_settings_service
from lfx.utils.file_path_security import LocalFileAccessError, enforce_local_file_access
from lfx.utils.flow_validation import CustomComponentValidationError, validate_flow_for_current_settings
from lfx.utils.trusted_flow import packaged_flow_scope

import lfx

FLOW_PATH = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows" / "LangflowAssistant.json"
LFX_COMPONENTS_DIR = str(Path(lfx.__file__).parent / "components")


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
    try:
        yield
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
        with packaged_flow_scope():
            validate_flow_for_current_settings(_prepared_flow())

    def test_should_read_its_own_component_library(self):
        """LE-2322: the Directory node's package path must be readable."""
        with packaged_flow_scope():
            enforce_local_file_access(LFX_COMPONENTS_DIR, scope_ids=(str(uuid.uuid4()),))


@pytest.mark.usefixtures("hardened_settings")
class TestPackagedFlowMarkerIsContained:
    """The marker must not become a general bypass. These are the security assertions."""

    async def test_should_still_block_the_same_flow_outside_the_marker(self):
        """A tenant flow with identical content stays blocked."""
        await get_and_cache_all_types_dict(get_settings_service())
        with pytest.raises(CustomComponentValidationError, match="custom components are not allowed"):
            validate_flow_for_current_settings(_prepared_flow())

    def test_should_still_block_package_reads_outside_the_marker(self):
        with pytest.raises(LocalFileAccessError):
            enforce_local_file_access(LFX_COMPONENTS_DIR, scope_ids=(str(uuid.uuid4()),))

    @pytest.mark.parametrize("forbidden", ["/etc/passwd", "/usr/bin", str(Path.home())])
    def test_should_still_block_arbitrary_server_paths_inside_the_marker(self, forbidden):
        """The file exemption is the package directory only, never a blanket unlock."""
        with packaged_flow_scope(), pytest.raises(LocalFileAccessError):
            enforce_local_file_access(forbidden, scope_ids=(str(uuid.uuid4()),))

    def test_should_still_block_reserved_secret_files_inside_the_marker(self, tmp_path):
        secret = tmp_path / "secret_key"
        secret.write_text("x", encoding="utf-8")
        with packaged_flow_scope(), pytest.raises(LocalFileAccessError):
            enforce_local_file_access(str(secret), scope_ids=(str(uuid.uuid4()),))

    def test_should_not_leak_the_marker_out_of_its_scope(self):
        with packaged_flow_scope():
            pass
        with pytest.raises(LocalFileAccessError):
            enforce_local_file_access(LFX_COMPONENTS_DIR, scope_ids=(str(uuid.uuid4()),))
