"""Integration tests for PraisonAI Langflow components.

These tests verify end-to-end behavior with mocked praisonaiagents.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestAgentComponentIntegration:
    """Integration tests for PraisonAIAgentComponent."""

    @pytest.fixture
    def mock_agent_class(self):
        """Create a mock Agent class."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.start.return_value = "Hello! I'm a helpful assistant."

        mock_class = MagicMock(return_value=mock_agent_instance)
        return mock_class, mock_agent_instance

    def test_build_agent_creates_agent_correctly(self, mock_agent_class):
        """Test build_agent creates Agent with correct parameters."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        mock_class, _mock_agent = mock_agent_class

        component = PraisonAIAgentComponent()
        component.name = "TestAgent"
        component.role = "Tester"
        component.goal = "Test things"
        component.backstory = "An experienced tester"
        component.instructions = "You are a test agent."
        component.llm = "openai/gpt-4o-mini"
        component.llm_handle = None
        component.tools = None
        component.memory = False
        component.memory_provider = ""
        component.memory_config = None
        component.knowledge_files = None
        component.knowledge_urls = None
        component.handoffs = None
        component.guardrails = False
        component.verbose = True
        component.markdown = True
        component.self_reflect = False
        component.allow_delegation = False
        component.allow_code_execution = False
        component.code_execution_mode = "safe"
        component.base_url = None
        component.api_key = None
        component.max_iter = 20

        with patch.object(component, "_import_agent", return_value=mock_class):
            component.build_agent()

        # Verify Agent was called with correct kwargs
        mock_class.assert_called_once()
        call_kwargs = mock_class.call_args[1]

        assert call_kwargs["name"] == "TestAgent"
        assert call_kwargs["role"] == "Tester"
        assert call_kwargs["goal"] == "Test things"
        assert call_kwargs["instructions"] == "You are a test agent."
        assert call_kwargs["llm"] == "openai/gpt-4o-mini"
        # Note: verbose is now passed via output= config, not directly
        assert "output" in call_kwargs

    def test_build_response_returns_message(self, mock_agent_class):
        """Test build_response returns proper Message."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent
        from lfx.schema.message import Message

        mock_class, mock_agent = mock_agent_class

        component = PraisonAIAgentComponent()
        component.name = "TestAgent"
        component.role = None
        component.goal = None
        component.backstory = None
        component.instructions = "You are helpful."
        component.llm = "openai/gpt-4o-mini"
        component.llm_handle = None
        component.tools = None
        component.memory = False
        component.memory_provider = ""
        component.memory_config = None
        component.knowledge_files = None
        component.knowledge_urls = None
        component.handoffs = None
        component.guardrails = False
        component.verbose = False
        component.markdown = True
        component.self_reflect = False
        component.allow_delegation = False
        component.allow_code_execution = False
        component.code_execution_mode = "safe"
        component.base_url = None
        component.api_key = None
        component.max_iter = 20
        component.input_value = "Hello!"

        with patch.object(component, "_import_agent", return_value=mock_class):
            result = component.build_response()

        assert isinstance(result, Message)
        assert result.text == "Hello! I'm a helpful assistant."
        mock_agent.start.assert_called_once_with("Hello!")

    def test_build_response_handles_message_input(self, mock_agent_class):
        """Test build_response handles Message input correctly."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        mock_class, mock_agent = mock_agent_class

        component = PraisonAIAgentComponent()
        component.name = "TestAgent"
        component.role = None
        component.goal = None
        component.backstory = None
        component.instructions = "You are helpful."
        component.llm = "openai/gpt-4o-mini"
        component.llm_handle = None
        component.tools = None
        component.memory = False
        component.memory_provider = ""
        component.memory_config = None
        component.knowledge_files = None
        component.knowledge_urls = None
        component.handoffs = None
        component.guardrails = False
        component.verbose = False
        component.markdown = True
        component.self_reflect = False
        component.allow_delegation = False
        component.allow_code_execution = False
        component.code_execution_mode = "safe"
        component.base_url = None
        component.api_key = None
        component.max_iter = 20

        # Use a Message object as input
        input_message = MagicMock()
        input_message.text = "What is 2+2?"
        component.input_value = input_message

        with patch.object(component, "_import_agent", return_value=mock_class):
            _result = component.build_response()

        mock_agent.start.assert_called_once_with("What is 2+2?")

    def test_knowledge_config_from_urls(self):
        """Test knowledge configuration built from URLs."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        component = PraisonAIAgentComponent()
        component.knowledge_files = None
        component.knowledge_urls = "https://example.com/doc1\nhttps://example.com/doc2"

        result = component._build_knowledge_config()

        assert result == ["https://example.com/doc1", "https://example.com/doc2"]

    def test_knowledge_config_from_files(self):
        """Test knowledge configuration built from files."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        component = PraisonAIAgentComponent()
        component.knowledge_files = ["/path/to/doc1.pdf", "/path/to/doc2.txt"]
        component.knowledge_urls = None

        result = component._build_knowledge_config()

        assert result == ["/path/to/doc1.pdf", "/path/to/doc2.txt"]

    def test_handoffs_configured_correctly(self, mock_agent_class):
        """Test handoffs are passed to Agent correctly."""
        from lfx.components.praisonai.agent import PraisonAIAgentComponent

        mock_class, _mock_agent = mock_agent_class

        # Mock another agent for handoff
        other_agent = MagicMock()

        component = PraisonAIAgentComponent()
        component.name = "MainAgent"
        component.role = None
        component.goal = None
        component.backstory = None
        component.instructions = "You are helpful."
        component.llm = "openai/gpt-4o-mini"
        component.llm_handle = None
        component.tools = None
        component.memory = False
        component.memory_provider = ""
        component.memory_config = None
        component.knowledge_files = None
        component.knowledge_urls = None
        component.handoffs = [other_agent]
        component.guardrails = False
        component.verbose = False
        component.markdown = True
        component.self_reflect = False
        component.allow_delegation = False
        component.allow_code_execution = False
        component.code_execution_mode = "safe"
        component.base_url = None
        component.api_key = None
        component.max_iter = 20

        with patch.object(component, "_import_agent", return_value=mock_class):
            component.build_agent()

        call_kwargs = mock_class.call_args[1]
        assert "handoffs" in call_kwargs
        assert call_kwargs["handoffs"] == [other_agent]


class TestAgentsComponentIntegration:
    """Integration tests for PraisonAIAgentsComponent."""

    @pytest.fixture
    def mock_agents_class(self):
        """Create a mock Agents class."""
        mock_agents = MagicMock()
        mock_agents.start.return_value = "Final result from agents"

        mock_class = MagicMock(return_value=mock_agents)
        return mock_class, mock_agents

    def test_build_agents_requires_agents(self):
        """Test build_agents raises error without agents."""
        from lfx.components.praisonai.agents import PraisonAIAgentsComponent

        component = PraisonAIAgentsComponent()
        component.agents = []
        component.tasks = None
        component.process = "sequential"
        component.manager_agent = None
        component.manager_llm = "openai/gpt-4o"
        component.name = "AgentTeam"
        component.variables = None
        component.memory = False
        component.guardrails = False
        component.verbose = False
        component.full_output = False
        component.planning = False
        component.reflection = False
        component.caching = False

        with patch.object(
            component, "_import_agents", return_value=MagicMock()
        ), pytest.raises(ValueError, match="At least one agent is required"):
            component.build_agents()

    def test_build_agents_creates_agents_correctly(self, mock_agents_class):
        """Test build_agents creates Agents with correct parameters."""
        from lfx.components.praisonai.agents import PraisonAIAgentsComponent

        mock_class, _mock_agents = mock_agents_class

        agent1 = MagicMock()
        agent2 = MagicMock()

        component = PraisonAIAgentsComponent()
        component.agents = [agent1, agent2]
        component.tasks = None
        component.process = "hierarchical"
        component.manager_agent = None
        component.manager_llm = "openai/gpt-4o"
        component.name = "ResearchTeam"
        component.variables = {"topic": "AI"}
        component.memory = True
        component.guardrails = True
        component.verbose = True
        component.full_output = False
        component.planning = True
        component.reflection = False
        component.caching = False
        component.input_value = "Research AI"

        with patch.object(component, "_import_agents", return_value=mock_class):
            component.build_agents()

        call_kwargs = mock_class.call_args[1]
        assert len(call_kwargs["agents"]) == 2
        assert call_kwargs["process"] == "hierarchical"
        assert call_kwargs["manager_llm"] == "openai/gpt-4o"
        assert call_kwargs["name"] == "ResearchTeam"
        assert call_kwargs["variables"] == {"topic": "AI"}
        assert call_kwargs["memory"] is True
        assert call_kwargs["guardrails"] is True
        assert call_kwargs["planning"] is True


class TestTaskComponentIntegration:
    """Integration tests for PraisonAITaskComponent."""

    @pytest.fixture
    def mock_task_class(self):
        """Create a mock Task class."""
        mock_task = MagicMock()
        mock_class = MagicMock(return_value=mock_task)
        return mock_class, mock_task

    def test_build_task_creates_task_correctly(self, mock_task_class):
        """Test build_task creates Task with correct parameters."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        mock_class, _mock_task = mock_task_class

        mock_agent = MagicMock()

        component = PraisonAITaskComponent()
        component.name = "ResearchTask"
        component.description = "Research the topic thoroughly"
        component.expected_output = "A comprehensive report"
        component.agent = mock_agent
        component.tools = None
        component.context = None
        component.async_execution = False
        component.output_json = None
        component.output_file = None
        component.create_directory = False
        component.input_file = None
        component.images = None
        component.guardrail = True
        component.max_retries = 5
        component.quality_check = True
        component.rerun = False
        component.retain_full_context = False
        component.task_type = "task"
        component.condition = None
        component.next_tasks = None
        component.is_start = False
        component.variables = {"topic": "AI"}

        with patch.object(component, "_import_task", return_value=mock_class):
            component.build_task()

        call_kwargs = mock_class.call_args[1]
        assert call_kwargs["name"] == "ResearchTask"
        assert call_kwargs["description"] == "Research the topic thoroughly"
        assert call_kwargs["expected_output"] == "A comprehensive report"
        assert call_kwargs["agent"] == mock_agent
        assert call_kwargs["guardrail"] is True
        assert call_kwargs["max_retries"] == 5
        assert call_kwargs["variables"] == {"topic": "AI"}

    def test_parse_output_json_simple_schema(self):
        """Test parsing simple JSON schema."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        component = PraisonAITaskComponent()
        component.output_json = '{"title": "string", "score": "int", "approved": "bool"}'

        result = component._parse_output_json()

        assert result is not None
        # Verify it's a Pydantic model
        assert hasattr(result, "__fields__") or hasattr(result, "model_fields")

    def test_parse_output_json_invalid_json(self):
        """Test parsing invalid JSON returns None."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        component = PraisonAITaskComponent()
        component.output_json = "not valid json"

        result = component._parse_output_json()
        assert result is None

    def test_workflow_task_configuration(self, mock_task_class):
        """Test decision task with conditions."""
        from lfx.components.praisonai.task import PraisonAITaskComponent

        mock_class, _mock_task = mock_task_class

        component = PraisonAITaskComponent()
        component.name = "ApprovalTask"
        component.description = "Decide on approval"
        component.expected_output = "Approval decision"
        component.agent = MagicMock()
        component.tools = None
        component.context = None
        component.async_execution = False
        component.output_json = None
        component.output_file = None
        component.create_directory = False
        component.input_file = None
        component.images = None
        component.guardrail = False
        component.max_retries = 3
        component.quality_check = True
        component.rerun = False
        component.retain_full_context = False
        component.task_type = "decision"
        component.condition = {"approved": ["process_task"], "rejected": ["review_task"]}
        component.next_tasks = "process_task, review_task"
        component.is_start = True
        component.variables = None

        with patch.object(component, "_import_task", return_value=mock_class):
            component.build_task()

        call_kwargs = mock_class.call_args[1]
        assert call_kwargs["task_type"] == "decision"
        assert call_kwargs["condition"] == {"approved": ["process_task"], "rejected": ["review_task"]}
        assert call_kwargs["next_tasks"] == ["process_task", "review_task"]
        assert call_kwargs["is_start"] is True
