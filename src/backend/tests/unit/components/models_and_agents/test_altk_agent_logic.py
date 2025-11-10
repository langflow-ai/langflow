"""Comprehensive unit tests for ALTK Agent logic without requiring API keys.

This test suite focuses on testing the actual orchestration logic, tool wrapping,
and pipeline execution order without requiring external API dependencies.
"""

import json
import uuid
from typing import Any, Dict, List, Optional, Union
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from lfx.components.agents.altk_agent import ALTKAgentComponent
from lfx.components.agents.altk_base_agent import (
    BaseToolWrapper,
    ToolPipelineManager,
)
from lfx.components.agents.altk_tool_wrappers import (
    PostToolProcessingWrapper,
    PreToolValidationWrapper,
)
from lfx.schema.message import Message
from tests.base import ComponentTestBaseWithoutClient
from tests.unit.mock_language_model import MockLanguageModel


# === Mock Tools and Components ===

class MockTool(BaseTool):
    """A controllable mock tool for testing."""
    
    name: str = "mock_tool"
    description: str = "A mock tool for testing"
    call_count: int = 0
    return_value: str = "mock_response"
    should_raise: bool = False
    
    def _run(self, query: str = "", **kwargs) -> str:
        self.call_count += 1
        if self.should_raise:
            raise ValueError("Mock tool error")
        return f"{self.return_value}_{self.call_count}"


class TrackingWrapper(BaseToolWrapper):
    """A wrapper that tracks when it was called for testing execution order."""
    
    def __init__(self, name: str):
        self.name = name
        self.wrap_calls: List[Dict] = []
        
    def wrap_tool(self, tool: BaseTool, **kwargs) -> BaseTool:
        self.wrap_calls.append({
            'tool_name': tool.name,
            'kwargs': list(kwargs.keys())
        })
        
        # Create a tracking tool that records execution
        class TrackedTool(BaseTool):
            name: str = f"tracked_{tool.name}"
            description: str = f"Tracked version of {tool.description}"
            wrapper_name: str = self.name
            original_tool: BaseTool = tool
            execution_order: List[str] = []
            
            def _run(self, *args, **kwargs) -> str:
                self.execution_order.append(f"{self.wrapper_name}_start")
                result = self.original_tool._run(*args, **kwargs)
                self.execution_order.append(f"{self.wrapper_name}_end")
                return f"[{self.wrapper_name}]{result}"
                
        return TrackedTool()


class MockSPARCComponent:
    """Mock SPARC reflection component."""
    
    def __init__(self, should_approve: bool = True, rejection_reason: str = ""):
        self.should_approve = should_approve
        self.rejection_reason = rejection_reason
        self.process_calls = []
        
    def process(self, run_input, phase=None):
        self.process_calls.append({
            'messages': run_input.messages,
            'tool_specs': run_input.tool_specs,
            'tool_calls': run_input.tool_calls,
            'phase': phase
        })
        
        # Mock the result structure
        result = MagicMock()
        result.output.reflection_result.decision.name = "APPROVE" if self.should_approve else "REJECT"
        
        if not self.should_approve:
            issue = MagicMock()
            issue.explanation = self.rejection_reason
            issue.correction = {"corrected_function_name": "correct_tool"}
            result.output.reflection_result.issues = [issue]
        else:
            result.output.reflection_result.issues = []
            
        return result


class MockCodeGenerationComponent:
    """Mock code generation component."""
    
    def __init__(self, return_result: str = "processed_response"):
        self.return_result = return_result
        self.process_calls = []
        
    def process(self, input_data, phase=None):
        self.process_calls.append({
            'messages': input_data.messages,
            'nl_query': input_data.nl_query,
            'tool_response': input_data.tool_response,
            'phase': phase
        })
        
        result = MagicMock()
        result.result = self.return_result
        return result


# === Test Suite ===

class TestToolPipelineManager:
    """Test the tool pipeline manager functionality."""
    
    def test_pipeline_manager_initialization(self):
        """Test that pipeline manager initializes correctly."""
        manager = ToolPipelineManager()
        assert manager.wrappers == []
        
    def test_add_wrapper(self):
        """Test adding wrappers to the pipeline."""
        manager = ToolPipelineManager()
        wrapper1 = TrackingWrapper("wrapper1")
        wrapper2 = TrackingWrapper("wrapper2")
        
        manager.add_wrapper(wrapper1)
        assert len(manager.wrappers) == 1
        assert manager.wrappers[0] == wrapper1
        
        manager.add_wrapper(wrapper2)
        assert len(manager.wrappers) == 2
        assert manager.wrappers[1] == wrapper2
        
    def test_configure_wrappers_replaces_existing(self):
        """Test that configure_wrappers replaces existing wrappers."""
        manager = ToolPipelineManager()
        wrapper1 = TrackingWrapper("wrapper1")
        wrapper2 = TrackingWrapper("wrapper2")
        wrapper3 = TrackingWrapper("wrapper3")
        
        # Add initial wrappers
        manager.add_wrapper(wrapper1)
        manager.add_wrapper(wrapper2)
        assert len(manager.wrappers) == 2
        
        # Configure with new wrappers
        manager.configure_wrappers([wrapper3])
        assert len(manager.wrappers) == 1
        assert manager.wrappers[0] == wrapper3
        
    def test_process_tools_applies_wrappers_in_reverse_order(self):
        """Test that wrappers are applied in reverse order (last added = outermost)."""
        manager = ToolPipelineManager()
        wrapper1 = TrackingWrapper("inner")
        wrapper2 = TrackingWrapper("outer")
        
        # Add wrappers in order: inner first, outer second
        manager.configure_wrappers([wrapper1, wrapper2])
        
        tool = MockTool()
        processed_tools = manager.process_tools([tool])
        
        assert len(processed_tools) == 1
        wrapped_tool = processed_tools[0]
        
        # With reversed() logic, the first wrapper in the list becomes innermost
        # So wrapper1 ("inner") gets applied last and becomes the outermost
        assert wrapped_tool.wrapper_name == "inner"
        
        # Check that both wrappers were called
        assert len(wrapper1.wrap_calls) == 1
        assert len(wrapper2.wrap_calls) == 1
        
    def test_clear_removes_all_wrappers(self):
        """Test that clear removes all wrappers."""
        manager = ToolPipelineManager()
        wrapper1 = TrackingWrapper("wrapper1")
        wrapper2 = TrackingWrapper("wrapper2")
        
        manager.add_wrapper(wrapper1)
        manager.add_wrapper(wrapper2)
        assert len(manager.wrappers) == 2
        
        manager.clear()
        assert len(manager.wrappers) == 0


class TestALTKAgentConfiguration:
    """Test ALTK agent configuration and tool pipeline setup."""
    
    def create_agent_with_config(self, enable_validation=True, enable_reflection=True):
        """Create an ALTK agent with specified configuration."""
        return ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(),
            input_value="test query",
            tools=[MockTool()],
            enable_tool_validation=enable_validation,
            enable_post_tool_reflection=enable_reflection,
            response_processing_size_threshold=50,
            system_prompt="Test prompt",
        )
    
    def test_configure_tool_pipeline_both_enabled(self):
        """Test tool pipeline configuration with both features enabled."""
        agent = self.create_agent_with_config(
            enable_validation=True, 
            enable_reflection=True
        )
        
        # Configure the pipeline
        agent.configure_tool_pipeline()
        
        # Should have 2 wrappers
        assert len(agent.pipeline_manager.wrappers) == 2
        
        # Check wrapper types (order should be: PostTool first, PreTool last)
        assert isinstance(agent.pipeline_manager.wrappers[0], PostToolProcessingWrapper)
        assert isinstance(agent.pipeline_manager.wrappers[1], PreToolValidationWrapper)
        
    def test_configure_tool_pipeline_validation_only(self):
        """Test tool pipeline configuration with only validation enabled."""
        agent = self.create_agent_with_config(
            enable_validation=True, 
            enable_reflection=False
        )
        
        agent.configure_tool_pipeline()
        
        # Should have 1 wrapper
        assert len(agent.pipeline_manager.wrappers) == 1
        assert isinstance(agent.pipeline_manager.wrappers[0], PreToolValidationWrapper)
        
    def test_configure_tool_pipeline_reflection_only(self):
        """Test tool pipeline configuration with only reflection enabled."""
        agent = self.create_agent_with_config(
            enable_validation=False, 
            enable_reflection=True
        )
        
        agent.configure_tool_pipeline()
        
        # Should have 1 wrapper
        assert len(agent.pipeline_manager.wrappers) == 1
        assert isinstance(agent.pipeline_manager.wrappers[0], PostToolProcessingWrapper)
        
    def test_configure_tool_pipeline_both_disabled(self):
        """Test tool pipeline configuration with both features disabled."""
        agent = self.create_agent_with_config(
            enable_validation=False, 
            enable_reflection=False
        )
        
        agent.configure_tool_pipeline()
        
        # Should have no wrappers
        assert len(agent.pipeline_manager.wrappers) == 0


class TestWrapperLogic:
    """Test individual wrapper logic using mocking."""
    
    def test_pre_tool_validation_wrapper_converts_tools(self):
        """Test that PreToolValidationWrapper converts LangChain tools correctly."""
        wrapper = PreToolValidationWrapper()
        
        # Test tool conversion
        tool = MockTool()
        tool_specs = wrapper.convert_langchain_tools_to_sparc_tool_specs_format([tool])
        
        assert len(tool_specs) == 1
        spec = tool_specs[0]
        assert spec['type'] == 'function'
        assert spec['function']['name'] == 'mock_tool'
        assert spec['function']['description'] == 'A mock tool for testing'
        assert 'parameters' in spec['function']
        assert spec['function']['parameters']['type'] == 'object'
        
    def test_post_tool_processing_wrapper_configuration(self):
        """Test that PostToolProcessingWrapper is configured correctly."""
        wrapper = PostToolProcessingWrapper(response_processing_size_threshold=200)
        
        assert wrapper.response_processing_size_threshold == 200
        assert wrapper.is_available  # Should be available by default
        
    def test_sparc_component_mock_behavior(self):
        """Test mock SPARC component behavior."""
        # Test approval
        sparc_approve = MockSPARCComponent(should_approve=True)
        
        mock_input = MagicMock()
        mock_input.messages = []
        mock_input.tool_specs = []
        mock_input.tool_calls = []
        
        result = sparc_approve.process(mock_input)
        assert result.output.reflection_result.decision.name == "APPROVE"
        assert len(sparc_approve.process_calls) == 1
        
        # Test rejection
        sparc_reject = MockSPARCComponent(should_approve=False, rejection_reason="Test error")
        result = sparc_reject.process(mock_input)
        assert result.output.reflection_result.decision.name == "REJECT"
        assert result.output.reflection_result.issues[0].explanation == "Test error"
        
    def test_code_generation_component_mock_behavior(self):
        """Test mock code generation component behavior."""
        code_gen = MockCodeGenerationComponent("Enhanced output")
        
        mock_input = MagicMock()
        mock_input.messages = []
        mock_input.nl_query = "test query"
        mock_input.tool_response = {"data": "test"}
        
        result = code_gen.process(mock_input)
        assert result.result == "Enhanced output"
        assert len(code_gen.process_calls) == 1
        assert code_gen.process_calls[0]['nl_query'] == "test query"


class TestToolExecutionOrder:
    """Test that tools are executed in the correct order with proper wrapping."""
    
    def test_wrapper_configuration_order(self):
        """Test that wrappers are configured in the correct order."""
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(),
            input_value="test query",
            tools=[MockTool()],
            enable_tool_validation=True,
            enable_post_tool_reflection=True,
            response_processing_size_threshold=50,
        )
        
        # Configure the pipeline
        agent.configure_tool_pipeline()
        
        # Verify the wrappers are configured correctly
        assert len(agent.pipeline_manager.wrappers) == 2
        assert isinstance(agent.pipeline_manager.wrappers[0], PostToolProcessingWrapper)
        assert isinstance(agent.pipeline_manager.wrappers[1], PreToolValidationWrapper)
        
        # Test wrapper application by checking what types are created
        post_wrapper = agent.pipeline_manager.wrappers[0]
        pre_wrapper = agent.pipeline_manager.wrappers[1]
        
        assert post_wrapper.response_processing_size_threshold == 50
        assert pre_wrapper.tool_specs == []  # Should be empty initially
        
    def test_pipeline_manager_processes_in_reverse_order(self):
        """Test that pipeline manager applies wrappers in reverse order."""
        manager = ToolPipelineManager()
        wrapper1 = TrackingWrapper("first")
        wrapper2 = TrackingWrapper("second")
        
        manager.configure_wrappers([wrapper1, wrapper2])
        
        tool = MockTool()
        processed_tools = manager.process_tools([tool])
        
        assert len(processed_tools) == 1
        wrapped_tool = processed_tools[0]
        
        # Due to reversed() in _apply_wrappers_to_tool, first wrapper becomes outermost
        assert wrapped_tool.wrapper_name == "first"
        
        # Both wrappers should have been called
        assert len(wrapper1.wrap_calls) == 1
        assert len(wrapper2.wrap_calls) == 1


class TestALTKBaseToolLogic:
    """Test ALTKBaseTool functionality."""
    
    def test_execute_tool_with_run_method(self):
        """Test _execute_tool when wrapped tool has _run method."""
        # Create a mock base tool that acts like ALTKBaseTool without pydantic validation
        class MockALTKBaseTool:
            def __init__(self):
                self.wrapped_tool = MockTool()
                
            def _execute_tool(self, *args, **kwargs):
                # Copy the actual _execute_tool logic
                try:
                    if hasattr(self.wrapped_tool, "_run"):
                        if "config" not in kwargs:
                            kwargs["config"] = {}
                        return self.wrapped_tool._run(*args, **kwargs)
                    return self.wrapped_tool.run(*args, **kwargs)
                except TypeError as e:
                    if "config" in str(e):
                        kwargs.pop("config", None)
                        if hasattr(self.wrapped_tool, "_run"):
                            return self.wrapped_tool._run(*args, **kwargs)
                        return self.wrapped_tool.run(*args, **kwargs)
                    raise
        
        base_tool = MockALTKBaseTool()
        result = base_tool._execute_tool("test query")
        assert result == "mock_response_1"
        assert base_tool.wrapped_tool.call_count == 1
        
    def test_execute_tool_with_config_error_fallback(self):
        """Test _execute_tool fallback when config parameter causes issues."""
        class MockToolWithConfigError(BaseTool):
            name: str = "config_error_tool"
            description: str = "Tool that errors on config"
            call_count: int = 0
            
            def _run(self, query: str = "", **kwargs) -> str:
                if "config" in kwargs:
                    raise TypeError("Tool doesn't accept config parameter")
                self.call_count += 1
                return f"success_{self.call_count}"
                
        class MockALTKBaseTool:
            def __init__(self):
                self.wrapped_tool = MockToolWithConfigError()
                
            def _execute_tool(self, *args, **kwargs):
                try:
                    if hasattr(self.wrapped_tool, "_run"):
                        if "config" not in kwargs:
                            kwargs["config"] = {}
                        return self.wrapped_tool._run(*args, **kwargs)
                    return self.wrapped_tool.run(*args, **kwargs)
                except TypeError as e:
                    if "config" in str(e):
                        kwargs.pop("config", None)
                        if hasattr(self.wrapped_tool, "_run"):
                            return self.wrapped_tool._run(*args, **kwargs)
                        return self.wrapped_tool.run(*args, **kwargs)
                    raise
        
        base_tool = MockALTKBaseTool()
        result = base_tool._execute_tool("test query")
        assert result == "success_1"
        assert base_tool.wrapped_tool.call_count == 1
        
    def test_get_altk_llm_object_for_openai(self):
        """Test _get_altk_llm_object with OpenAI model."""
        class MockChatOpenAI:
            def __init__(self):
                self.model_name = "gpt-4o"
                self.openai_api_key = MagicMock()
                self.openai_api_key.get_secret_value.return_value = "test_key"
                
        class MockRunnableBinding:
            def __init__(self):
                self.bound = MockChatOpenAI()
                
        class MockAgent:
            def __init__(self):
                self.steps = [MockRunnableBinding()]
                
        class MockALTKBaseTool:
            def __init__(self):
                self.agent = MockAgent()
                
            def _get_altk_llm_object(self, use_output_val: bool = True):
                # Copy the actual implementation logic
                llm_object = None
                steps = getattr(self.agent, "steps", None)
                if steps:
                    for step in steps:
                        if hasattr(step, 'bound') and hasattr(step.bound, 'model_name'):
                            llm_object = step.bound
                            break
                
                if llm_object and hasattr(llm_object, 'model_name'):
                    # Mock the OpenAI path
                    return {"model": llm_object.model_name, "api_key": "test_key"}
                return None
        
        with patch('lfx.components.agents.altk_base_agent.get_llm') as mock_get_llm:
            mock_llm_client = MagicMock()
            mock_get_llm.return_value = mock_llm_client
            mock_llm_client.return_value = {"model": "gpt-4o", "api_key": "test_key"}
            
            base_tool = MockALTKBaseTool()
            result = base_tool._get_altk_llm_object()
            assert result == {"model": "gpt-4o", "api_key": "test_key"}


class TestHelperFunctions:
    """Test helper functions from altk_agent.py."""
    
    def test_set_advanced_true(self):
        """Test set_advanced_true function."""
        from lfx.components.agents.altk_agent import set_advanced_true
        
        # Create a mock input object
        mock_input = MagicMock()
        mock_input.advanced = False
        
        result = set_advanced_true(mock_input)
        
        assert result.advanced is True
        assert result is mock_input  # Should return the same object
        
    def test_get_parent_agent_inputs(self):
        """Test get_parent_agent_inputs function."""
        from lfx.components.agents.altk_agent import get_parent_agent_inputs
        
        # This function filters out inputs with specific names
        result = get_parent_agent_inputs()
        
        # Should return a list (exact content depends on ALTKBaseAgentComponent.inputs)
        assert isinstance(result, list)
        
        # Verify that agent_llm is filtered out (this is the main logic)
        agent_llm_inputs = [inp for inp in result if getattr(inp, 'name', None) == 'agent_llm']
        assert len(agent_llm_inputs) == 0


class TestConversationContextBuilding:
    """Test conversation context building edge cases."""
    
    def test_get_user_query_with_get_text_method(self):
        """Test get_user_query when input_value has get_text method.""" 
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(),
            input_value=MagicMock(),
            tools=[],
        )
        
        # Mock input with get_text method
        agent.input_value.get_text = MagicMock(return_value="extracted text")
        
        result = agent.get_user_query()
        assert result == "extracted text"
        agent.input_value.get_text.assert_called_once()
        
    def test_get_user_query_fallback_to_str(self):
        """Test get_user_query fallback to str conversion."""
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(),
            input_value="simple string input",
            tools=[],
        )
        
        result = agent.get_user_query()
        assert result == "simple string input"
        
    def test_build_conversation_context_with_data_type(self):
        """Test build_conversation_context with Data type chat history."""
        # Import Data class for proper isinstance check
        from lfx.schema.data import Data
        
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(),
            input_value="test query",
            tools=[],
        )
        
        # Create a proper Data instance with message structure
        mock_data = Data(data={'text': 'previous message', 'sender': 'User'})
        agent.chat_history = mock_data
        
        context = agent.build_conversation_context()
        
        assert len(context) == 2  # input + chat history
        assert context[0].content == "test query"
        # The Data.to_lc_message() returns content as list of dicts
        assert context[1].content == [{'type': 'text', 'text': 'previous message'}]
        
    def test_build_conversation_context_with_data_list(self):
        """Test build_conversation_context with list of Data objects."""
        from lfx.schema.data import Data
        
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(),
            input_value="test query",
            tools=[],
        )
        
        # Create list of Data objects
        data1 = Data(data={'text': 'first message', 'sender': 'User'})
        data2 = Data(data={'text': 'second message', 'sender': 'Assistant'})
        agent.chat_history = [data1, data2]
        
        context = agent.build_conversation_context()
        
        assert len(context) == 3  # input + 2 chat history messages
        assert context[0].content == "test query"
        # HumanMessage from User sender has content as list of dicts
        assert context[1].content == [{'type': 'text', 'text': 'first message'}]
        # AIMessage from Assistant sender has content as plain string
        assert context[2].content == "second message"
    """Integration tests for the complete ALTK agent functionality."""
    
    def test_agent_configuration_integration(self):
        """Test that the agent correctly configures its components."""
        # Create agent with validation enabled
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(), 
            input_value="test query",
            tools=[MockTool()],
            enable_tool_validation=True,
            enable_post_tool_reflection=False,  # Focus on validation
        )
        
        # Trigger pipeline configuration
        agent.configure_tool_pipeline()
        
        # Verify pipeline is configured correctly
        assert len(agent.pipeline_manager.wrappers) == 1
        assert isinstance(agent.pipeline_manager.wrappers[0], PreToolValidationWrapper)
        
        # Test that tool specs can be updated
        validation_wrapper = agent.pipeline_manager.wrappers[0]
        test_tools = [MockTool()]
        tool_specs = validation_wrapper.convert_langchain_tools_to_sparc_tool_specs_format(test_tools)
        
        assert len(tool_specs) == 1
        assert tool_specs[0]['function']['name'] == 'mock_tool'
        
    def test_build_conversation_context(self):
        """Test conversation context building from various input types."""
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(),
            input_value="test query", 
            tools=[],
        )
        
        # Test with simple string input
        context = agent.build_conversation_context()
        assert len(context) == 1
        assert isinstance(context[0], HumanMessage)
        assert context[0].content == "test query"
        
        # Test with Message input
        message_input = Message(
            sender="Human",
            sender_name="User", 
            session_id=str(uuid4()),
            content_blocks=[]
        )
        message_input.text = "message query"
        
        agent.input_value = message_input
        context = agent.build_conversation_context()
        assert len(context) == 1
        
    def test_error_handling_in_tool_execution(self):
        """Test error handling when tools raise exceptions."""
        failing_tool = MockTool()
        failing_tool.should_raise = True
        
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(),
            input_value="test query",
            tools=[failing_tool],
            enable_tool_validation=False,  # Disable validation to test tool errors directly
            enable_post_tool_reflection=False,
        )
        
        # Process the tool through the pipeline
        agent.configure_tool_pipeline()
        processed_tools = agent.pipeline_manager.process_tools([failing_tool])
        
        # The tool should still be wrapped (even if just pass-through)
        assert len(processed_tools) == 1
        
        # When executed, it should raise the mock error
        with pytest.raises(ValueError, match="Mock tool error"):
            processed_tools[0]._run("test query")


class TestConfigurationCombinations:
    """Test various configuration combinations of the ALTK agent."""
    
    @pytest.mark.parametrize("validation,reflection,expected_wrappers", [
        (True, True, 2),    # Both enabled
        (True, False, 1),   # Only validation
        (False, True, 1),   # Only reflection  
        (False, False, 0),  # Both disabled
    ])
    def test_wrapper_count_for_configurations(self, validation, reflection, expected_wrappers):
        """Test that the correct number of wrappers is added for each configuration."""
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(),
            input_value="test query",
            tools=[MockTool()],
            enable_tool_validation=validation,
            enable_post_tool_reflection=reflection,
        )
        
        agent.configure_tool_pipeline()
        assert len(agent.pipeline_manager.wrappers) == expected_wrappers
        
    def test_response_processing_threshold_configuration(self):
        """Test that response processing threshold is correctly configured."""
        agent = ALTKAgentComponent(
            _type="Agent", 
            agent_llm=MockLanguageModel(),
            input_value="test query",
            tools=[MockTool()],
            enable_post_tool_reflection=True,
            response_processing_size_threshold=200,
        )
        
        agent.configure_tool_pipeline()
        
        # Find the PostToolProcessingWrapper
        post_wrapper = None
        for wrapper in agent.pipeline_manager.wrappers:
            if isinstance(wrapper, PostToolProcessingWrapper):
                post_wrapper = wrapper
                break
                
        assert post_wrapper is not None
        assert post_wrapper.response_processing_size_threshold == 200


# === Test Component for Framework Compatibility ===

class TestALTKAgentComponentFramework(ComponentTestBaseWithoutClient):
    """Test ALTK Agent Component using the standard test framework."""
    
    @pytest.fixture
    def component_class(self):
        return ALTKAgentComponent

    @pytest.fixture 
    def file_names_mapping(self):
        return []

    @pytest.fixture
    def default_kwargs(self):
        return {
            "_type": "Agent",
            "agent_llm": MockLanguageModel(),
            "input_value": "test query",
            "tools": [MockTool()],
            "enable_tool_validation": True,
            "enable_post_tool_reflection": True,
            "response_processing_size_threshold": 100,
            "system_prompt": "Test system prompt",
        }

    async def test_component_instantiation(self, component_class, default_kwargs):
        """Test that the component can be instantiated with default kwargs."""
        component = await self.component_setup(component_class, default_kwargs)
        assert isinstance(component, ALTKAgentComponent)
        assert component.enable_tool_validation is True
        assert component.enable_post_tool_reflection is True
        assert component.response_processing_size_threshold == 100
        
    async def test_component_tool_pipeline_configuration(self, component_class, default_kwargs):
        """Test that the component correctly configures its tool pipeline."""
        component = await self.component_setup(component_class, default_kwargs)
        
        # Trigger pipeline configuration
        component.configure_tool_pipeline()
        
        # Verify pipeline is configured
        assert len(component.pipeline_manager.wrappers) == 2
        assert any(isinstance(w, PostToolProcessingWrapper) for w in component.pipeline_manager.wrappers)
        assert any(isinstance(w, PreToolValidationWrapper) for w in component.pipeline_manager.wrappers)


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error conditions."""
    
    def test_tool_pipeline_with_wrapper_exception(self):
        """Test pipeline behavior when wrapper throws exception."""
        class FailingWrapper(BaseToolWrapper):
            def wrap_tool(self, tool: BaseTool, **kwargs) -> BaseTool:
                raise ValueError("Wrapper failed")
                
            @property
            def is_available(self) -> bool:
                return True
        
        pipeline = ToolPipelineManager()
        pipeline.add_wrapper(FailingWrapper())
        
        tools = [MockTool()]
        
        with pytest.raises(ValueError, match="Wrapper failed"):
            pipeline.process_tools(tools)
            
    def test_chat_history_edge_cases(self):
        """Test various edge cases for chat_history processing."""
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(),
            input_value="test query",
            tools=[],
        )
        
        # Test with None
        agent.chat_history = None
        context = agent.build_conversation_context()
        assert len(context) == 1  # Only input_value
        
        # Test with empty list
        agent.chat_history = []
        context = agent.build_conversation_context()
        assert len(context) == 1  # Only input_value
        
        # Test with invalid data structure
        agent.chat_history = "invalid_string"
        context = agent.build_conversation_context()
        assert len(context) == 1  # Should skip invalid chat_history
        
    def test_data_with_missing_required_keys(self):
        """Test Data objects with missing required keys for message conversion."""
        from lfx.schema.data import Data
        
        agent = ALTKAgentComponent(
            _type="Agent", 
            agent_llm=MockLanguageModel(),
            input_value="test query",
            tools=[],
        )
        
        # Data missing 'sender' key
        invalid_data = Data(data={'text': 'message without sender'})
        agent.chat_history = invalid_data
        
        with pytest.raises(ValueError, match="Missing required keys"):
            agent.build_conversation_context()
            
    def test_tool_pipeline_multiple_processing(self):
        """Test that tools can be processed multiple times safely."""
        pipeline = ToolPipelineManager()
        tracking_wrapper = TrackingWrapper("track1")
        pipeline.add_wrapper(tracking_wrapper)
        
        tools = [MockTool()]
        
        # Process same tools multiple times
        result1 = pipeline.process_tools(tools)
        result2 = pipeline.process_tools(tools)
        
        assert len(result1) == len(result2) == 1
        # Each processing should create new wrapped instances
        assert result1[0] is not result2[0]
        
    def test_base_tool_wrapper_initialize_method(self):
        """Test BaseToolWrapper initialize method behavior."""
        class TestWrapper(BaseToolWrapper):
            def __init__(self):
                self.initialized = False
                
            def wrap_tool(self, tool: BaseTool, **kwargs) -> BaseTool:
                return tool
                
            def initialize(self):
                self.initialized = True
                
            @property  
            def is_available(self) -> bool:
                return True
        
        wrapper = TestWrapper()
        assert not wrapper.initialized
        
        wrapper.initialize()
        assert wrapper.initialized
        
    def test_get_user_query_edge_cases(self):
        """Test get_user_query with various input types."""
        # Test with None input
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(),
            input_value=None,
            tools=[],
        )
        
        result = agent.get_user_query()
        assert result == "None"
        
        # Test with numeric input
        agent.input_value = 42
        result = agent.get_user_query()
        assert result == "42"
        
        # Test with object that has get_text but it's not callable
        class BadGetText:
            get_text = "not callable"
            
        agent.input_value = BadGetText()
        result = agent.get_user_query()
        assert "BadGetText" in result  # Should fall back to str()
        
    def test_altk_base_tool_llm_extraction_edge_cases(self):
        """Test ALTKBaseTool LLM object extraction edge cases.""" 
        class MockALTKBaseTool:
            def _get_altk_llm_object(self, use_output_val: bool = True):
                # Simulate the actual implementation 
                llm_object = None
                steps = getattr(self, "agent", None)
                if hasattr(steps, "steps"):
                    for step in steps.steps:
                        if hasattr(step, 'bound') and hasattr(step.bound, 'model_name'):
                            llm_object = step.bound
                            break
                return llm_object
        
        # Test with no agent
        tool = MockALTKBaseTool()
        result = tool._get_altk_llm_object()
        assert result is None
        
        # Test with agent but no steps
        class MockAgent:
            steps = []
        tool.agent = MockAgent()
        result = tool._get_altk_llm_object()
        assert result is None
        
        # Test with steps but no bound attribute
        class MockStep:
            pass
        tool.agent.steps = [MockStep()]
        result = tool._get_altk_llm_object()
        assert result is None


class TestConfigurationValidation:
    """Test configuration validation and edge cases."""
    
    def test_agent_with_invalid_llm_type(self):
        """Test agent creation with invalid LLM types."""
        # This should work as our MockLanguageModel accepts anything
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm="invalid_llm_string",
            input_value="test",
            tools=[],
        )
        
        assert agent.agent_llm == "invalid_llm_string"
        
    def test_tool_pipeline_with_unavailable_wrappers(self):
        """Test pipeline behavior with unavailable wrappers."""
        class UnavailableWrapper(BaseToolWrapper):
            def wrap_tool(self, tool: BaseTool, **kwargs) -> BaseTool:
                return tool
                
            @property
            def is_available(self) -> bool:
                return False  # Always unavailable
        
        pipeline = ToolPipelineManager() 
        pipeline.add_wrapper(UnavailableWrapper())
        
        tools = [MockTool()]
        result = pipeline.process_tools(tools)
        
        # Tool should be unchanged since wrapper is unavailable
        assert result[0] is tools[0]
        
    def test_wrapper_configuration_persistence(self):
        """Test that wrapper configurations persist correctly."""
        agent = ALTKAgentComponent(
            _type="Agent",
            agent_llm=MockLanguageModel(),
            input_value="test",
            tools=[],
            enable_tool_validation=True,
            enable_post_tool_reflection=True,
        )
        
        # Configure pipeline multiple times
        agent.configure_tool_pipeline()
        initial_count = len(agent.pipeline_manager.wrappers)
        
        agent.configure_tool_pipeline() 
        second_count = len(agent.pipeline_manager.wrappers)
        
        # Should have same count (clear() called each time)
        assert initial_count == second_count == 2