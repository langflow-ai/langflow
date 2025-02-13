import pytest

from langflow.components.crewai import SequentialTaskAgentComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSequentialTaskAgentComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SequentialTaskAgentComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "role": "Assistant",
            "goal": "Help users with their queries.",
            "backstory": "An AI designed to assist users.",
            "tools": [],
            "llm": "GPT-3",
            "memory": True,
            "verbose": True,
            "allow_delegation": False,
            "allow_code_execution": False,
            "agent_kwargs": {},
            "task_description": "Answer user questions.",
            "expected_output": "A helpful response.",
            "async_execution": False,
            "previous_task": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "agents", "file_name": "SequentialTaskAgent"},
            {"version": "1.1.0", "module": "agents", "file_name": "sequential_task_agent"},
        ]

    async def test_build_agent_and_task(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build_agent_and_task()
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].description == "Answer user questions."
        assert result[0].expected_output == "A helpful response."

    async def test_build_agent_with_previous_task(self, component_class, default_kwargs):
        default_kwargs["previous_task"] = [{"description": "Initial task", "expected_output": "Initial output."}]
        component = component_class(**default_kwargs)
        result = await component.build_agent_and_task()
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[1].description == "Answer user questions."
        assert result[0].description == "Initial task"

    async def test_component_latest_version(self, component_class, default_kwargs):
        result = await component_class(**default_kwargs).build_agent_and_task()
        assert result is not None
