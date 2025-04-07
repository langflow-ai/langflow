import pytest
from langflow.components.crewai import HierarchicalCrewComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestHierarchicalCrewComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return HierarchicalCrewComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "agents": ["agent1", "agent2"],
            "tasks": ["task1", "task2"],
            "manager_llm": "manager_llm_instance",
            "manager_agent": "manager_agent_instance",
            "verbose": True,
            "memory": "some_memory",
            "use_cache": False,
            "max_rpm": 10,
            "share_crew": True,
            "function_calling_llm": "function_calling_llm_instance",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "crewai", "file_name": "HierarchicalCrew"},
            {"version": "1.1.0", "module": "crewai", "file_name": "hierarchical_crew"},
        ]

    async def test_build_crew(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        crew = component.build_crew()

        assert crew is not None
        assert len(crew.agents) == 2
        assert len(crew.tasks) == 2
        assert crew.process == Process.hierarchical
        assert crew.manager_llm == default_kwargs["manager_llm"]
        assert crew.manager_agent == default_kwargs["manager_agent"]

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None
