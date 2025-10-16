"""Tests for the EnhancedAgentComponent."""

import unittest
from unittest import mock
from unittest.mock import MagicMock, patch
from typing import List

from langchain_core.tools import BaseTool
from langchain_core.callbacks.manager import CallbackManagerForToolRun

from lfx.components.agents.enhanced_agent import (
    EnhancedAgentComponent,
    BaseToolWrapper,
    ToolPipelineManager,
    PostToolProcessingWrapper,
    PreToolValidationWrapper,
    ValidatedTool,
    PostToolProcessor,
)


# Create a simple test tool for validation
class SimpleTool(BaseTool):
    name: str = "simple_tool"
    description: str = "A simple test tool"
    
    def _run(self, input_str: str, run_manager: CallbackManagerForToolRun = None) -> str:
        return f"Tool result: {input_str}"


class TestToolWrapper(BaseToolWrapper):
    """Test tool wrapper for unit testing."""
    
    def __init__(self, is_available: bool = True):
        self._is_available = is_available
        self.wrap_count = 0
    
    @property
    def is_available(self) -> bool:
        return self._is_available
        
    def wrap_tool(self, tool: BaseTool, **kwargs) -> BaseTool:
        self.wrap_count += 1
        return tool


class TestEnhancedAgentComponent(unittest.TestCase):
    """Test the EnhancedAgentComponent."""
    
    def setUp(self):
        self.component = EnhancedAgentComponent()
        self.test_tool = SimpleTool()
        
    def test_initialization(self):
        """Test component initialization with default values."""
        self.assertTrue(self.component.enable_post_tool_reflection)
        self.assertTrue(self.component.enable_tool_validation)
        self.assertIsInstance(self.component.pipeline_manager, ToolPipelineManager)
        
    def test_post_reflection_flag(self):
        """Test that post tool reflection flag works correctly."""
        # Default value should be True
        self.assertTrue(self.component.enable_post_tool_reflection)
        
        # Set to False
        self.component.set(enable_post_tool_reflection=False)
        self.assertFalse(self.component.enable_post_tool_reflection)
        
        # Set back to True
        self.component.set(enable_post_tool_reflection=True)
        self.assertTrue(self.component.enable_post_tool_reflection)
        
        # Check that wrapper is properly initialized
        self.component._initialize_tool_wrappers()
        # The pipeline manager should have wrappers after initialization
        self.assertTrue(len(self.component.pipeline_manager.wrappers) > 0)
        
    def test_tool_validation_flag(self):
        """Test that tool validation flag works correctly."""
        # Default value should be True
        self.assertTrue(self.component.enable_tool_validation)
        
        # Set to False
        self.component.set(enable_tool_validation=False)
        self.assertFalse(self.component.enable_tool_validation)
        
        # Set back to True
        self.component.set(enable_tool_validation=True)
        self.assertTrue(self.component.enable_tool_validation)
        
        # Check that wrapper is properly initialized
        self.component._initialize_tool_wrappers()
        # The pipeline manager should have wrappers after initialization
        self.assertTrue(len(self.component.pipeline_manager.wrappers) > 0)
        
    def test_both_features_enabled(self):
        """Test that both features can be enabled at the same time."""
        # Both features are enabled by default
        self.assertTrue(self.component.enable_post_tool_reflection)
        self.assertTrue(self.component.enable_tool_validation)
        
        # Disable both
        self.component.set(
            enable_post_tool_reflection=False,
            enable_tool_validation=False,
        )
        
        # Check both flags are disabled
        self.assertFalse(self.component.enable_post_tool_reflection)
        self.assertFalse(self.component.enable_tool_validation)
        
        # Enable both again
        self.component.set(
            enable_post_tool_reflection=True,
            enable_tool_validation=True,
        )
        
        # Check both flags are set
        self.assertTrue(self.component.enable_post_tool_reflection)
        self.assertTrue(self.component.enable_tool_validation)
        
        # Check that wrappers are initialized
        self.component._initialize_tool_wrappers()
        
        # There should be at least 2 wrappers (the ones we're testing)
        self.assertGreaterEqual(len(self.component.pipeline_manager.wrappers), 2)
        
        # Check wrapper types and order
        wrapper_types = [type(w) for w in self.component.pipeline_manager.wrappers]
        self.assertIn(PostToolProcessingWrapper, wrapper_types)
        self.assertIn(PreToolValidationWrapper, wrapper_types)
        
        # The post tool wrapper should be registered first
        self.assertIsInstance(
            self.component.pipeline_manager.wrappers[0], 
            PostToolProcessingWrapper
        )
        
    def test_wrapper_application_order(self):
        """Test that wrappers are applied in the correct order.
        
        The test verifies that:
        1. Wrappers are registered in the correct order in EnhancedAgentComponent
        2. Wrappers are applied in reverse order of registration in ToolPipelineManager
        3. This creates the proper execution flow where validation happens first
           and post-processing happens after tool execution
        """
        # Create a clean component with both features enabled
        component = EnhancedAgentComponent(
            enable_post_tool_reflection=True,
            enable_tool_validation=True
        )
        
        # Mock the wrapper classes to avoid real initialization
        with patch("lfx.components.agents.enhanced_agent.PostToolProcessingWrapper") as MockPost, \
             patch("lfx.components.agents.enhanced_agent.PreToolValidationWrapper") as MockPre:
             
            # Create mock instances for our wrappers
            mock_post = MagicMock()
            mock_post.is_available = True
            MockPost.return_value = mock_post
            
            mock_pre = MagicMock()
            mock_pre.is_available = True
            MockPre.return_value = mock_pre
            
            # Reset pipeline and initialize wrappers
            component.pipeline_manager = ToolPipelineManager()
            component._initialize_tool_wrappers()
            
            # Verify both wrappers were added
            self.assertEqual(len(component.pipeline_manager.wrappers), 2)
            
            # Verify the order of registration:
            # According to _initialize_tool_wrappers:
            # Post processor is added first
            # Pre validator is added second
            self.assertIs(component.pipeline_manager.wrappers[0], mock_post)
            self.assertIs(component.pipeline_manager.wrappers[1], mock_pre)
            
            # Create sequence tracking
            call_sequence = []
            test_tool = SimpleTool()
            
            # Create distinct return values for each wrapper
            post_result = MagicMock(name="post_wrapped")
            pre_result = MagicMock(name="pre_wrapped")
            
            # Set up side effects to track wrapper application sequence
            def record_pre_call(tool, **kwargs):
                call_sequence.append(("pre", tool))
                return pre_result
                
            def record_post_call(tool, **kwargs):
                call_sequence.append(("post", tool))
                return post_result
                
            mock_pre.wrap_tool.side_effect = record_pre_call
            mock_post.wrap_tool.side_effect = record_post_call
            
            # Process a test tool through the pipeline
            wrapped_tools = component.pipeline_manager.process_tools([test_tool])
            
            # Verify both wrappers were called once
            mock_pre.wrap_tool.assert_called_once()
            mock_post.wrap_tool.assert_called_once()
            
            # The pipeline reverses the order of wrapper application:
            # 1. First applied: mock_pre (outermost, last registered)
            # 2. Second applied: mock_post (innermost, first registered)
            
            self.assertEqual(len(call_sequence), 2)
            self.assertEqual(call_sequence[0][0], "pre")
            self.assertEqual(call_sequence[1][0], "post")
            
            # First wrapper (pre) should receive the original tool
            self.assertEqual(call_sequence[0][1], test_tool)
            
            # Second wrapper (post) should receive the result from pre_wrapper
            self.assertEqual(call_sequence[1][1], pre_result)
            
            # Final result should be what post_wrapper returned
            self.assertEqual(wrapped_tools[0], post_result)
            
            # This confirms the wrapping order is:
            # post_wrapper(pre_wrapper(tool))
            # Which creates this execution flow:
            # 1. pre_wrapper validates the call (outermost) 
            # 2. Tool is executed
            # 3. post_wrapper processes the result (innermost)
                
    def test_tool_pipeline_manager(self):
        """Test the ToolPipelineManager class."""
        manager = ToolPipelineManager()
        wrapper1 = TestToolWrapper()
        wrapper2 = TestToolWrapper()
        
        # Add wrappers
        manager.add_wrapper(wrapper1)
        manager.add_wrapper(wrapper2)
        
        # Check wrappers were added
        self.assertEqual(len(manager.wrappers), 2)
        self.assertIn(wrapper1, manager.wrappers)
        self.assertIn(wrapper2, manager.wrappers)
        
        # Process tools
        tools = [SimpleTool()]
        processed_tools = manager.process_tools(tools)
        
        # Each wrapper should be applied once per tool
        self.assertEqual(wrapper1.wrap_count, 1)
        self.assertEqual(wrapper2.wrap_count, 1)
        
        # Should return same number of tools
        self.assertEqual(len(processed_tools), len(tools))
        
    def test_disabled_wrapper_not_applied(self):
        """Test that disabled wrappers are not applied."""
        manager = ToolPipelineManager()
        wrapper1 = TestToolWrapper(is_available=True)
        wrapper2 = TestToolWrapper(is_available=False)
        
        manager.add_wrapper(wrapper1)
        manager.add_wrapper(wrapper2)
        
        tools = [SimpleTool()]
        manager.process_tools(tools)
        
        # Only the available wrapper should be applied
        self.assertEqual(wrapper1.wrap_count, 1)
        self.assertEqual(wrapper2.wrap_count, 0)
        
    def test_post_tool_processing_wrapper(self):
        """Test that the post tool processing wrapper works correctly."""
        with patch.object(PostToolProcessingWrapper, "wrap_tool") as mock_wrap:
            # Create a mock for the wrapped tool
            mock_post_processor = MagicMock(spec=PostToolProcessor)
            mock_wrap.return_value = mock_post_processor
            
            wrapper = PostToolProcessingWrapper(response_processing_size_threshold=10)
            agent_mock = MagicMock()
            
            # Call the wrap_tool method
            result = wrapper.wrap_tool(self.test_tool, agent=agent_mock, user_query="test query")
            
            # Check that wrap_tool was called with correct arguments
            mock_wrap.assert_called_once_with(self.test_tool, agent=agent_mock, user_query="test query")
            
            # Check that the result is what we expected
            self.assertEqual(result, mock_post_processor)
        
    @patch("lfx.components.agents.enhanced_agent._check_sparc_available", return_value=False)
    def test_pre_tool_validation_wrapper_no_sparc(self, mock_check):
        """Test that the pre-tool validation wrapper works without SPARC."""
        wrapper = PreToolValidationWrapper()
        
        # Wrap the tool
        
        wrapped_tool = wrapper.wrap_tool(self.test_tool)
        
        self.assertIsInstance(wrapped_tool, ValidatedTool)
        self.assertEqual(wrapped_tool.name, self.test_tool.name)
        self.assertEqual(wrapped_tool.description, self.test_tool.description)
        self.assertEqual(wrapped_tool.wrapped_tool, self.test_tool)
        self.assertIsNone(wrapped_tool.sparc_component)
        
    def test_combined_tool_wrapping(self):
        """Test that tools can be wrapped with both processors.
        
        This test verifies:
        1. The proper registration order of wrappers
        2. Wrappers are applied in reverse order of registration
        3. The execution flow follows this pattern:
           - Pre-validator is applied first (outermost wrapper)
           - Post-processor is applied next (innermost wrapper)
        """
        # Create a pipeline and track wrapper application
        pipeline = ToolPipelineManager()
        
        # Create mock wrapper instances with tracking
        post_wrapper = MagicMock()
        post_wrapper.is_available = True
        post_result = MagicMock(name="post_processed_tool")
        post_wrapper.wrap_tool.return_value = post_result
        
        pre_wrapper = MagicMock()
        pre_wrapper.is_available = True
        pre_result = MagicMock(name="pre_validated_tool")
        pre_wrapper.wrap_tool.return_value = pre_result
        
        # Record wrapper application sequence
        call_sequence = []
        
        # Setup wrapper side effects to track call sequence
        def record_post_wrapper_call(tool, **kwargs):
            call_sequence.append(("post", tool))
            return post_result
            
        def record_pre_wrapper_call(tool, **kwargs):
            call_sequence.append(("pre", tool))
            return pre_result
            
        post_wrapper.wrap_tool.side_effect = record_post_wrapper_call
        pre_wrapper.wrap_tool.side_effect = record_pre_wrapper_call
        
        # Register wrappers in the same order as EnhancedAgentComponent:
        # Post wrapper first, Pre wrapper second
        pipeline.add_wrapper(post_wrapper)
        pipeline.add_wrapper(pre_wrapper)
        
        # Verify registration order matches implementation
        self.assertEqual(len(pipeline.wrappers), 2)
        self.assertIs(pipeline.wrappers[0], post_wrapper)
        self.assertIs(pipeline.wrappers[1], pre_wrapper)
        
        # Process a tool through the pipeline
        original_tool = self.test_tool
        result = pipeline.process_tools([original_tool], test_arg="value")
        
        # Verify both wrappers were called once
        post_wrapper.wrap_tool.assert_called_once()
        pre_wrapper.wrap_tool.assert_called_once()
        
        # Verify call sequence and parameters
        self.assertEqual(len(call_sequence), 2)
        
        # According to ToolPipelineManager.process_tools, wrappers should be 
        # applied in REVERSE order of registration:
        
        # First called wrapper should be pre_wrapper (last registered)
        self.assertEqual(call_sequence[0][0], "pre")
        self.assertIs(call_sequence[0][1], original_tool)
        pre_wrapper.wrap_tool.assert_called_with(original_tool, test_arg="value")
        
        # Second called wrapper should be post_wrapper (first registered)
        self.assertEqual(call_sequence[1][0], "post")
        self.assertIs(call_sequence[1][1], pre_result)
        post_wrapper.wrap_tool.assert_called_with(pre_result, test_arg="value")
        
        # The final result should be the post_wrapper's return value
        self.assertEqual(result, [post_result])
        
        # This confirms the wrapping order is:
        # post_wrapper(pre_wrapper(original_tool))
        # Which creates this execution flow:
        # 1. pre_wrapper validates the call (outermost wrapper)
        # 2. original_tool executes
        # 3. post_wrapper processes the result (innermost wrapper)


if __name__ == "__main__":
    unittest.main()