"""Unit tests for the langflow.helpers.flow module."""

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from lfx.utils.langflow_utils import has_langflow_memory

# Globals

_LANGFLOW_HELPER_MODULE_FLOW = "langflow.helpers.flow"

# Helper Functions


def is_helper_module(module, module_name):
    return module.__module__ == module_name


# Test Scenarios


class TestDynamicImport:
    """Test dynamic imports of the langflow implementation."""

    def test_langflow_available(self):
        """Test whether the langflow implementation is available."""
        # Langflow implementation should be available
        if not has_langflow_memory():
            pytest.fail("Langflow implementation is not available")

    def test_helpers_import_build_schema_from_inputs(self):
        """Test the lfx.helpers.build_schema_from_inputs import."""
        try:
            from lfx.helpers import build_schema_from_inputs
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to dynamically import lfx.helpers.build_schema_from_inputs: {e}")

        # Helper module should be the langflow implementation
        assert is_helper_module(build_schema_from_inputs, _LANGFLOW_HELPER_MODULE_FLOW)

    def test_helpers_import_get_arg_names(self):
        """Test the lfx.helpers.get_arg_names import."""
        try:
            from lfx.helpers import get_arg_names
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to dynamically import lfx.helpers.get_arg_names: {e}")

        # Helper module should be the langflow implementation
        assert is_helper_module(get_arg_names, _LANGFLOW_HELPER_MODULE_FLOW)

    def test_helpers_import_get_flow_inputs(self):
        """Test the lfx.helpers.get_flow_inputs import."""
        try:
            from lfx.helpers import get_flow_inputs
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to dynamically import lfx.helpers.get_flow_inputs: {e}")

        # Helper module should be the langflow implementation
        assert is_helper_module(get_flow_inputs, _LANGFLOW_HELPER_MODULE_FLOW)

    def test_helpers_import_list_flows(self):
        """Test the lfx.helpers.list_flows import."""
        try:
            from lfx.helpers import list_flows
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to dynamically import lfx.helpers.list_flows: {e}")

        # Helper module should be the langflow implementation
        assert is_helper_module(list_flows, _LANGFLOW_HELPER_MODULE_FLOW)

    def test_helpers_import_load_flow(self):
        """Test the lfx.helpers.load_flow import."""
        try:
            from lfx.helpers import load_flow
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to dynamically import lfx.helpers.load_flow: {e}")

        # Helper module should be the langflow implementation
        assert is_helper_module(load_flow, _LANGFLOW_HELPER_MODULE_FLOW)

    def test_helpers_import_run_flow(self):
        """Test the lfx.helpers.run_flow import."""
        try:
            from lfx.helpers import run_flow
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to dynamically import lfx.helpers.run_flow: {e}")

        # Helper module should be the langflow implementation
        assert is_helper_module(run_flow, _LANGFLOW_HELPER_MODULE_FLOW)


async def test_generate_function_for_flow_sanitizes_and_preserves_distinct_inputs(monkeypatch):
    from langflow.helpers import flow as flow_helpers

    inputs = [
        SimpleNamespace(
            id="malicious-input",
            display_name='value"; __import__("os").system("id"); #',
            base_name="ChatInput",
            description="malicious",
        ),
        SimpleNamespace(id="keyword-input", display_name="class", base_name="TextInput", description="keyword"),
        SimpleNamespace(id="debug-input", display_name="__debug__", base_name="TextInput", description="debug"),
        SimpleNamespace(id="json-input", display_name="value", base_name="JSONInput", description="json"),
        SimpleNamespace(id="chat-input", display_name="value", base_name="ChatInput", description="chat"),
    ]
    flow_id = "flow-'quoted\nidentifier"
    user_id = "user-'quoted\nidentifier"
    run_flow = AsyncMock(return_value=[])
    monkeypatch.setattr(flow_helpers, "run_flow", run_flow)

    function = flow_helpers.generate_function_for_flow(inputs, flow_id, user_id=user_id)
    parameter_names = list(inspect.signature(function).parameters)

    assert len(parameter_names) == len(inputs)
    assert len(set(parameter_names)) == len(inputs)
    assert all(name.isidentifier() for name in parameter_names)
    assert "class" not in parameter_names
    assert "__debug__" not in parameter_names

    values = ["malicious-value", "keyword-value", "debug-value", '{"json": true}', "chat-value"]
    await function(*values)

    assert run_flow.await_args.kwargs == {
        "tweaks": {input_.id: {"input_value": value} for input_, value in zip(inputs, values, strict=True)},
        "flow_id": flow_id,
        "user_id": user_id,
    }

    schema = flow_helpers.build_schema_from_inputs("FlowInputs", inputs)
    assert list(schema.schema()["properties"]) == parameter_names
    assert flow_helpers.get_arg_names(inputs) == [
        {"component_name": input_.id, "arg_name": arg_name}
        for input_, arg_name in zip(inputs, parameter_names, strict=True)
    ]
