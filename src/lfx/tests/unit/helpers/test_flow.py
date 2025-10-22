"""Unit tests for the lfx.helpers.flow module."""

import pytest
from lfx.utils.langflow_utils import has_langflow_memory

# Globals

_LFX_HELPER_MODULE_FLOW = "lfx.helpers.flow"

# Helper Functions


def is_helper_module(module, module_name):
    return module.__module__ == module_name


# Test Scenarios


class TestDynamicImport:
    """Test dynamic imports of the lfx implementation."""

    def test_langflow_available(self):
        """Test whether the langflow implementation is available."""
        # Langflow implementation should not be available
        if has_langflow_memory():
            pytest.fail("Langflow implementation is available")

    def test_helpers_import_build_schema_from_inputs(self):
        """Test the lfx.helpers.build_schema_from_inputs import."""
        try:
            from lfx.helpers import build_schema_from_inputs
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to dynamically import lfx.helpers.build_schema_from_inputs: {e}")

        # Helper module should be the lfx implementation
        assert is_helper_module(build_schema_from_inputs, _LFX_HELPER_MODULE_FLOW)

    def test_helpers_import_get_arg_names(self):
        """Test the lfx.helpers.get_arg_names import."""
        try:
            from lfx.helpers import get_arg_names
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to dynamically import lfx.helpers.get_arg_names: {e}")

        # Helper module should be the lfx implementation
        assert is_helper_module(get_arg_names, _LFX_HELPER_MODULE_FLOW)

    def test_helpers_import_get_flow_inputs(self):
        """Test the lfx.helpers.get_flow_inputs import."""
        try:
            from lfx.helpers import get_flow_inputs
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to dynamically import lfx.helpers.get_flow_inputs: {e}")

        # Helper module should be the lfx implementation
        assert is_helper_module(get_flow_inputs, _LFX_HELPER_MODULE_FLOW)

    def test_helpers_import_list_flows(self):
        """Test the lfx.helpers.list_flows import."""
        try:
            from lfx.helpers import list_flows
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to dynamically import lfx.helpers.list_flows: {e}")

        # Helper module should be the lfx implementation
        assert is_helper_module(list_flows, _LFX_HELPER_MODULE_FLOW)

    def test_helpers_import_load_flow(self):
        """Test the lfx.helpers.load_flow import."""
        try:
            from lfx.helpers import load_flow
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to dynamically import lfx.helpers.load_flow: {e}")

        # Helper module should be the lfx implementation
        assert is_helper_module(load_flow, _LFX_HELPER_MODULE_FLOW)

    def test_helpers_import_run_flow(self):
        """Test the lfx.helpers.run_flow import."""
        try:
            from lfx.helpers import run_flow
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to dynamically import lfx.helpers.run_flow: {e}")

        # Helper module should be the lfx implementation
        assert is_helper_module(run_flow, _LFX_HELPER_MODULE_FLOW)
