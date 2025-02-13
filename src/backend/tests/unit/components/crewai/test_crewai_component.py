import pytest
from langflow.components.crewai import CrewAIAgentComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCrewAIAgentComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CrewAIAgentComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "role": "Assistant",
            "goal": "Help users with their queries.",
            "backstory": "An AI trained to assist users.",
            "tools": [],
            "llm": "gpt-3.5-turbo",
            "memory": True,
            "verbose": False,
            "allow_delegation": True,
            "allow_code_execution": False,
            "kwargs": {},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "agents", "file_name": "CrewAIAgent"},
        ]

    async def test_build_output(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        agent = await component.build_output()
        assert agent is not None
        assert agent.role == default_kwargs["role"]
        assert agent.goal == default_kwargs["goal"]
        assert agent.backstory == default_kwargs["backstory"]
        assert agent.memory == default_kwargs["memory"]
        assert agent.verbose == default_kwargs["verbose"]
        assert agent.allow_delegation == default_kwargs["allow_delegation"]
        assert agent.allow_code_execution == default_kwargs["allow_code_execution"]

    async def test_agent_creation_with_tools(self, component_class):
        default_kwargs = {
            "role": "Assistant",
            "goal": "Help users with their queries.",
            "backstory": "An AI trained to assist users.",
            "tools": ["Tool1", "Tool2"],
            "llm": "gpt-3.5-turbo",
            "memory": True,
            "verbose": False,
            "allow_delegation": True,
            "allow_code_execution": False,
            "kwargs": {},
        }
        component = component_class(**default_kwargs)
        agent = await component.build_output()
        assert agent.tools == ["Tool1", "Tool2"]
