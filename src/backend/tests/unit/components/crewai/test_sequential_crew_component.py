import pytest

from langflow.components.crewai import SequentialCrewComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSequentialCrewComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SequentialCrewComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "tasks": [{"agent": "Agent1"}, {"agent": "Agent2"}],
            "verbose": True,
            "memory": None,
            "use_cache": False,
            "max_rpm": 5,
            "share_crew": False,
            "function_calling_llm": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_agents_property(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        agents = component.agents
        assert len(agents) == 2
        assert agents[0] == "Agent1"
        assert agents[1] == "Agent2"

    def test_get_tasks_and_agents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tasks, agents = component.get_tasks_and_agents()
        assert len(tasks) == 2
        assert len(agents) == 2

    async def test_build_crew(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        crew_message = component.build_crew()
        assert crew_message is not None
        assert crew_message.agents == ["Agent1", "Agent2"]
        assert crew_message.process == Process.sequential
