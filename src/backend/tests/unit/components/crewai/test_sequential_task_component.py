import pytest
from langflow.components.crewai import SequentialTaskComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSequentialTaskComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SequentialTaskComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "task_description": "Complete the project report.",
            "expected_output": "A finalized project report.",
            "agent": "Agent1",
            "tools": ["Tool1", "Tool2"],
            "task": None,
            "async_execution": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "agents", "file_name": "SequentialTask"},
        ]

    async def test_build_task(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build_task()
        assert result is not None
        assert len(result) == 1
        assert result[0].description == "Complete the project report."
        assert result[0].expected_output == "A finalized project report."
        assert result[0].agent == "Agent1"
        assert result[0].async_execution is False

    async def test_build_task_with_existing_tasks(self, component_class, default_kwargs):
        existing_task = SequentialTask(
            description="Existing task.",
            expected_output="Existing output.",
            tools=["Tool3"],
            async_execution=False,
            agent="Agent2",
        )
        default_kwargs["task"] = [existing_task]
        component = component_class(**default_kwargs)
        result = await component.build_task()
        assert result is not None
        assert len(result) == 2
        assert result[0].description == "Existing task."
        assert result[1].description == "Complete the project report."
