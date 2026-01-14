"""Comprehensive unit tests for PraisonAI Langflow components.

Tests cover:
- Component structure and inputs/outputs
- Helper function behavior
- Import error handling
- Edge cases and validation
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestPraisonAIAgentComponent:
    """Tests for PraisonAIAgentComponent."""

    def test_component_display_name(self):
        """Test component has correct display name."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        assert PraisonAIAgentComponent.display_name == "PraisonAI Agent"

    def test_component_icon(self):
        """Test component has PraisonAI icon."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        assert PraisonAIAgentComponent.icon == "PraisonAI"

    def test_component_documentation_url(self):
        """Test component has correct documentation URL."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        assert "praison.ai" in PraisonAIAgentComponent.documentation

    def test_component_has_core_inputs(self):
        """Test component has all core identity inputs."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        input_names = [inp.name for inp in PraisonAIAgentComponent.inputs]
        assert "name" in input_names
        assert "role" in input_names
        assert "goal" in input_names
        assert "backstory" in input_names
        assert "instructions" in input_names

    def test_component_has_llm_inputs(self):
        """Test component has LLM configuration inputs."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        input_names = [inp.name for inp in PraisonAIAgentComponent.inputs]
        assert "llm" in input_names
        assert "llm_handle" in input_names
        assert "base_url" in input_names
        assert "api_key" in input_names

    def test_component_has_tool_inputs(self):
        """Test component has tool-related inputs."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        input_names = [inp.name for inp in PraisonAIAgentComponent.inputs]
        assert "tools" in input_names
        assert "allow_delegation" in input_names
        assert "allow_code_execution" in input_names
        assert "code_execution_mode" in input_names

    def test_component_has_handoffs_input(self):
        """Test component has handoffs input for agent collaboration."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        input_names = [inp.name for inp in PraisonAIAgentComponent.inputs]
        assert "handoffs" in input_names

        handoffs_input = next(inp for inp in PraisonAIAgentComponent.inputs if inp.name == "handoffs")
        assert handoffs_input.is_list is True
        assert "Agent" in handoffs_input.input_types

    def test_component_has_memory_inputs(self):
        """Test component has memory configuration inputs."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        input_names = [inp.name for inp in PraisonAIAgentComponent.inputs]
        assert "memory" in input_names
        assert "memory_provider" in input_names
        assert "memory_config" in input_names

    def test_component_has_knowledge_inputs(self):
        """Test component has knowledge/RAG inputs."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        input_names = [inp.name for inp in PraisonAIAgentComponent.inputs]
        assert "knowledge_files" in input_names
        assert "knowledge_urls" in input_names

    def test_component_has_guardrails_input(self):
        """Test component has guardrails input."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        input_names = [inp.name for inp in PraisonAIAgentComponent.inputs]
        assert "guardrails" in input_names

    def test_component_has_execution_inputs(self):
        """Test component has execution option inputs."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        input_names = [inp.name for inp in PraisonAIAgentComponent.inputs]
        assert "verbose" in input_names
        assert "markdown" in input_names
        assert "self_reflect" in input_names
        assert "max_iter" in input_names

    def test_component_has_required_outputs(self):
        """Test component has all required outputs."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        output_names = [out.name for out in PraisonAIAgentComponent.outputs]
        assert "response" in output_names
        assert "agent" in output_names

    def test_llm_dropdown_has_multiple_providers(self):
        """Test LLM dropdown has options from multiple providers."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        llm_input = next(inp for inp in PraisonAIAgentComponent.inputs if inp.name == "llm")

        providers = set()
        for option in llm_input.options:
            if "/" in option:
                providers.add(option.split("/")[0])

        # Should have at least OpenAI, Anthropic, Google
        assert "openai" in providers
        assert "anthropic" in providers
        assert "google" in providers

    def test_import_error_handling(self):
        """Test graceful handling when praisonaiagents not installed."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        component = PraisonAIAgentComponent()

        with (
            patch.object(
                component,
                "_import_agent",
                side_effect=ImportError("PraisonAI Agents is not installed. Install with: pip install praisonaiagents"),
            ),
            pytest.raises(ImportError, match="praisonaiagents"),
        ):
            component.build_agent()


class TestPraisonAIAgentsComponent:
    """Tests for PraisonAIAgentsComponent."""

    def test_component_display_name(self):
        """Test component has correct display name."""
        from lfx.components.praisonai.agents import PraisonAIAgentsComponent

        assert PraisonAIAgentsComponent.display_name == "PraisonAI Agents"

    def test_component_has_name_input(self):
        """Test component has name input."""
        from lfx.components.praisonai.agents import PraisonAIAgentsComponent

        input_names = [inp.name for inp in PraisonAIAgentsComponent.inputs]
        assert "name" in input_names

    def test_component_has_core_inputs(self):
        """Test component has all core inputs."""
        from lfx.components.praisonai.agents import PraisonAIAgentsComponent

        input_names = [inp.name for inp in PraisonAIAgentsComponent.inputs]
        assert "agents" in input_names
        assert "tasks" in input_names
        assert "process" in input_names
        assert "input_value" in input_names

    def test_component_has_variables_input(self):
        """Test component has variables input."""
        from lfx.components.praisonai.agents import PraisonAIAgentsComponent

        input_names = [inp.name for inp in PraisonAIAgentsComponent.inputs]
        assert "variables" in input_names

    def test_component_has_guardrails_input(self):
        """Test component has guardrails input."""
        from lfx.components.praisonai.agents import PraisonAIAgentsComponent

        input_names = [inp.name for inp in PraisonAIAgentsComponent.inputs]
        assert "guardrails" in input_names

    def test_component_has_advanced_features(self):
        """Test component has advanced feature inputs."""
        from lfx.components.praisonai.agents import PraisonAIAgentsComponent

        input_names = [inp.name for inp in PraisonAIAgentsComponent.inputs]
        assert "planning" in input_names
        assert "reflection" in input_names
        assert "caching" in input_names

    def test_process_options(self):
        """Test process dropdown has correct options."""
        from lfx.components.praisonai.agents import PraisonAIAgentsComponent

        process_input = next(inp for inp in PraisonAIAgentsComponent.inputs if inp.name == "process")
        assert "sequential" in process_input.options
        assert "hierarchical" in process_input.options
        assert "workflow" in process_input.options

    def test_component_has_required_outputs(self):
        """Test component has all required outputs."""
        from lfx.components.praisonai.agents import PraisonAIAgentsComponent

        output_names = [out.name for out in PraisonAIAgentsComponent.outputs]
        assert "response" in output_names
        assert "agents_instance" in output_names


class TestPraisonAITaskComponent:
    """Tests for PraisonAITaskComponent."""

    def test_component_display_name(self):
        """Test component has correct display name."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        assert PraisonAITaskComponent.display_name == "PraisonAI Task"

    def test_component_has_core_inputs(self):
        """Test component has all core inputs."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        input_names = [inp.name for inp in PraisonAITaskComponent.inputs]
        assert "name" in input_names
        assert "description" in input_names
        assert "expected_output" in input_names
        assert "agent" in input_names

    def test_component_has_structured_output_inputs(self):
        """Test component has structured output inputs."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        input_names = [inp.name for inp in PraisonAITaskComponent.inputs]
        assert "output_json" in input_names
        assert "output_file" in input_names
        assert "create_directory" in input_names

    def test_component_has_file_inputs(self):
        """Test component has file I/O inputs."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        input_names = [inp.name for inp in PraisonAITaskComponent.inputs]
        assert "input_file" in input_names
        assert "images" in input_names

    def test_component_has_guardrail_inputs(self):
        """Test component has guardrail and retry inputs."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        input_names = [inp.name for inp in PraisonAITaskComponent.inputs]
        assert "guardrail" in input_names
        assert "max_retries" in input_names
        assert "quality_check" in input_names

    def test_component_has_workflow_inputs(self):
        """Test component has workflow/branching inputs."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        input_names = [inp.name for inp in PraisonAITaskComponent.inputs]
        assert "task_type" in input_names
        assert "condition" in input_names
        assert "next_tasks" in input_names
        assert "is_start" in input_names

    def test_task_type_options(self):
        """Test task_type dropdown has correct options."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        task_type_input = next(inp for inp in PraisonAITaskComponent.inputs if inp.name == "task_type")
        assert "task" in task_type_input.options
        assert "decision" in task_type_input.options
        assert "loop" in task_type_input.options

    def test_component_has_variables_input(self):
        """Test component has variables input."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        input_names = [inp.name for inp in PraisonAITaskComponent.inputs]
        assert "variables" in input_names

    def test_component_has_task_output(self):
        """Test component has task output."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        output_names = [out.name for out in PraisonAITaskComponent.outputs]
        assert "task" in output_names


class TestHelpers:
    """Tests for PraisonAI helper functions."""

    def test_convert_tools_with_none(self):
        """Test convert_tools returns None for None input."""
        from lfx.base.agents.praisonai.helpers import convert_tools

        assert convert_tools(None) is None
        assert convert_tools([]) is None

    def test_convert_tools_with_callables(self):
        """Test convert_tools handles plain callables."""
        from lfx.base.agents.praisonai.helpers import convert_tools

        def my_tool():
            return "result"

        result = convert_tools([my_tool])
        assert result is not None
        assert len(result) == 1
        assert result[0] == my_tool

    def test_convert_tools_with_langchain_style(self):
        """Test convert_tools handles LangChain-style tools with .run method."""
        from lfx.base.agents.praisonai.helpers import convert_tools

        mock_tool = MagicMock()
        mock_tool.run = lambda x: f"processed {x}"

        result = convert_tools([mock_tool])
        assert result is not None
        assert len(result) == 1
        assert result[0] == mock_tool.run

    def test_convert_tools_with_underscore_run(self):
        """Test convert_tools handles tools with _run method."""
        from lfx.base.agents.praisonai.helpers import convert_tools

        mock_tool = MagicMock(spec=["_run"])
        run_func = lambda x: f"processed {x}"  # noqa: E731
        mock_tool._run = run_func

        result = convert_tools([mock_tool])
        assert result is not None
        assert len(result) == 1
        assert callable(result[0])

    def test_convert_tools_filters_none(self):
        """Test convert_tools filters out None values."""
        from lfx.base.agents.praisonai.helpers import convert_tools

        def my_tool():
            return "result"

        result = convert_tools([my_tool, None, my_tool])
        assert result is not None
        assert len(result) == 2

    def test_convert_llm_with_string(self):
        """Test convert_llm returns string as-is."""
        from lfx.base.agents.praisonai.helpers import convert_llm

        assert convert_llm("openai/gpt-4o-mini") == "openai/gpt-4o-mini"
        assert convert_llm("anthropic/claude-3-sonnet") == "anthropic/claude-3-sonnet"
        assert convert_llm(None) is None

    def test_convert_llm_with_langchain_model(self):
        """Test convert_llm extracts model info from LangChain model."""
        from lfx.base.agents.praisonai.helpers import convert_llm

        mock_llm = MagicMock()
        mock_llm.model_name = "gpt-4o"
        mock_llm.get_lc_namespace = lambda: ["langchain_openai"]

        result = convert_llm(mock_llm)
        assert result == "openai/gpt-4o"

    def test_convert_llm_with_model_attribute(self):
        """Test convert_llm handles model attribute."""
        from lfx.base.agents.praisonai.helpers import convert_llm

        mock_llm = MagicMock(spec=["model"])
        mock_llm.model = "claude-3-sonnet"
        mock_llm.model_name = None

        result = convert_llm(mock_llm)
        assert "claude-3-sonnet" in result

    def test_build_memory_config_simple(self):
        """Test build_memory_config with simple bool."""
        from lfx.base.agents.praisonai.helpers import build_memory_config

        assert build_memory_config(memory=False) is False
        assert build_memory_config(memory=True) is True

    def test_build_memory_config_with_provider(self):
        """Test build_memory_config with provider."""
        from lfx.base.agents.praisonai.helpers import build_memory_config

        result = build_memory_config(memory=True, memory_provider="rag")
        assert result == {"provider": "rag"}

        result = build_memory_config(memory=True, memory_provider="mem0")
        assert result == {"provider": "mem0"}

    def test_build_memory_config_with_dict(self):
        """Test build_memory_config with full config dict."""
        from lfx.base.agents.praisonai.helpers import build_memory_config

        config = {"provider": "mem0", "collection": "test", "embedding_model": "text-embedding-3-small"}
        result = build_memory_config(memory=True, memory_config_dict=config)
        assert result == config

    def test_build_memory_config_dict_takes_precedence(self):
        """Test that memory_config_dict takes precedence over provider."""
        from lfx.base.agents.praisonai.helpers import build_memory_config

        config = {"provider": "mem0"}
        result = build_memory_config(memory=True, memory_provider="rag", memory_config_dict=config)
        assert result == config  # Dict wins over provider


class TestComponentInitRegistry:
    """Tests for component registration and discovery."""

    def test_dynamic_imports_registered(self):
        """Test components are registered in dynamic imports."""
        from lfx.components.praisonai import _dynamic_imports

        assert "PraisonAIAgentComponent" in _dynamic_imports
        assert "PraisonAIAgentsComponent" in _dynamic_imports
        assert "PraisonAITaskComponent" in _dynamic_imports

    def test_module_all_exports(self):
        """Test __all__ exports correct symbols."""
        from lfx.components.praisonai import __all__

        assert "PraisonAIAgentComponent" in __all__
        assert "PraisonAIAgentsComponent" in __all__
        assert "PraisonAITaskComponent" in __all__

    def test_lazy_import_works(self):
        """Test lazy import mechanism works."""
        from lfx.components import praisonai

        # Should not raise
        assert hasattr(praisonai, "PraisonAIAgentComponent")
        assert hasattr(praisonai, "PraisonAIAgentsComponent")
        assert hasattr(praisonai, "PraisonAITaskComponent")


class TestAsyncMethods:
    """Tests for async execution methods."""

    def test_agent_has_async_method(self):
        """Test agent component has async method."""
        import asyncio

        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        assert hasattr(PraisonAIAgentComponent, "build_response_async")
        # Verify it's actually async
        component = PraisonAIAgentComponent()
        method = component.build_response_async
        assert asyncio.iscoroutinefunction(method)

    def test_agents_has_async_method(self):
        """Test agents component has async method."""
        import asyncio

        from lfx.components.praisonai.agents import PraisonAIAgentsComponent

        assert hasattr(PraisonAIAgentsComponent, "build_response_async")
        # Verify it's actually async
        component = PraisonAIAgentsComponent()
        method = component.build_response_async
        assert asyncio.iscoroutinefunction(method)
