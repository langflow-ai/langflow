import pytest
from langflow.components.crewai import HierarchicalTaskComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestHierarchicalTaskComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return HierarchicalTaskComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "task_description": "Prepare a report on quarterly sales.",
            "expected_output": "A detailed report with graphs and analysis.",
            "tools": ["SalesTool", "GraphTool"],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "agents.crewai", "file_name": "HierarchicalTask"},
        ]

    def test_build_task(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.build_task()
        assert result is not None
        assert result.description == default_kwargs["task_description"]
        assert result.expected_output == default_kwargs["expected_output"]
        assert result.tools == default_kwargs["tools"]

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
