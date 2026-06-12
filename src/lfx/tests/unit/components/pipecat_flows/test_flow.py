"""Tests for PipecatFlowComponent."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPipecatFlowComponentMetadata:
    """PipecatFlowComponent metadata and output structure."""

    def test_metadata(self):
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        assert PipecatFlowComponent.display_name == "Pipecat Flow"
        assert PipecatFlowComponent.name == "PipecatFlow"
        assert PipecatFlowComponent.category == "pipecat"

    def test_outputs_include_flow_manager_and_task(self):
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        output_names = {o.name for o in PipecatFlowComponent.outputs}
        assert "flow_manager" in output_names
        assert "pipeline_task" in output_names

    def test_has_required_inputs(self):
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        names = {i.name for i in PipecatFlowComponent.inputs}
        assert "task" in names
        assert "llm" in names
        assert "context_aggregator_pair" in names
        assert "flow_config" in names


class TestPipecatFlowComponentParseNode:
    """_parse_initial_node validates JSON and raises on bad input."""

    def test_valid_node_config_is_returned(self):
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        comp = PipecatFlowComponent.__new__(PipecatFlowComponent)
        config = {"name": "start", "task_messages": [{"role": "user", "content": "hi"}], "functions": []}
        comp.flow_config = json.dumps(config)

        result = comp._parse_initial_node()
        assert result["name"] == "start"
        assert "task_messages" in result

    def test_empty_config_raises(self):
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        comp = PipecatFlowComponent.__new__(PipecatFlowComponent)
        comp.flow_config = ""

        with pytest.raises(ValueError, match="flow_config is empty"):
            comp._parse_initial_node()

    def test_invalid_json_raises(self):
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        comp = PipecatFlowComponent.__new__(PipecatFlowComponent)
        comp.flow_config = "{not valid"

        with pytest.raises(ValueError, match="not valid JSON"):
            comp._parse_initial_node()

    def test_non_dict_json_raises_type_error(self):
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        comp = PipecatFlowComponent.__new__(PipecatFlowComponent)
        comp.flow_config = '["list", "not", "dict"]'

        with pytest.raises(TypeError, match="JSON object"):
            comp._parse_initial_node()

    def test_missing_task_messages_raises(self):
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        comp = PipecatFlowComponent.__new__(PipecatFlowComponent)
        comp.flow_config = json.dumps({"name": "start", "functions": []})

        with pytest.raises(ValueError, match="task_messages"):
            comp._parse_initial_node()


class TestPipecatFlowComponentGetTask:
    """get_task re-emits the upstream PipelineTask unchanged."""

    def test_get_task_returns_upstream_task(self):
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        comp = PipecatFlowComponent.__new__(PipecatFlowComponent)
        mock_task = MagicMock()
        comp.task = mock_task

        assert comp.get_task() is mock_task


class TestPipecatFlowComponentRegisterTools:
    """_register_global_tools wires tools onto the LLM idempotently."""

    def test_registers_tools_on_llm(self):
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        comp = PipecatFlowComponent.__new__(PipecatFlowComponent)

        schema = MagicMock()
        schema.name = "tool_a"
        handler = MagicMock()
        comp.tools = [(schema, handler)]

        llm = MagicMock()
        llm._function_handlers = {}
        comp.llm = llm

        comp._register_global_tools()
        llm.register_function.assert_called_once_with("tool_a", handler)

    def test_skips_already_registered_tools(self):
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        comp = PipecatFlowComponent.__new__(PipecatFlowComponent)

        schema = MagicMock()
        schema.name = "tool_a"
        handler = MagicMock()
        comp.tools = [(schema, handler)]

        llm = MagicMock()
        llm._function_handlers = {"tool_a": handler}
        comp.llm = llm

        comp._register_global_tools()
        llm.register_function.assert_not_called()

    def test_no_op_when_tools_empty(self):
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        comp = PipecatFlowComponent.__new__(PipecatFlowComponent)
        comp.tools = []
        comp.llm = MagicMock()

        comp._register_global_tools()
        comp.llm.register_function.assert_not_called()


class TestPipecatFlowComponentBuildFlowManager:
    """build_flow_manager constructs and initializes FlowManager."""

    @pytest.mark.asyncio
    async def test_build_flow_manager_initializes_and_caches(self):
        pytest.importorskip("pipecat_flows")
        from lfx.components.pipecat_flows.pipecat_flow import PipecatFlowComponent

        comp = PipecatFlowComponent.__new__(PipecatFlowComponent)
        comp._flow_manager = None
        comp.tools = []
        comp.transport = None
        comp.context_strategy = "append"
        comp.flow_config = json.dumps({
            "name": "start",
            "task_messages": [{"role": "user", "content": "hi"}],
            "functions": [],
        })

        mock_task = MagicMock()
        mock_llm = MagicMock()
        mock_llm._function_handlers = {}
        mock_llm.register_function = MagicMock()
        comp.task = mock_task
        comp.llm = mock_llm
        comp.context_aggregator_pair = MagicMock()

        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock()

        with patch("pipecat_flows.FlowManager", return_value=mock_manager):
            result = await comp.build_flow_manager()

        assert result is mock_manager
        mock_manager.initialize.assert_awaited_once()
        # Second call returns cached instance without re-initializing
        result2 = await comp.build_flow_manager()
        assert result2 is mock_manager
        mock_manager.initialize.assert_awaited_once()  # still once
