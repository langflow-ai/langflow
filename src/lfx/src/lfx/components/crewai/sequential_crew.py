from lfx.base.agents.crewai.crew import BaseCrewComponent
from lfx.io import HandleInput
from lfx.schema.message import Message


class SequentialCrewComponent(BaseCrewComponent):
    display_name: str = "Sequential Crew"
    description: str = "Represents a group of agents with tasks that are executed sequentially."
    documentation: str = "https://docs.crewai.com/how-to/Sequential/"
    icon = "CrewAI"
    legacy = True

    inputs = [
        *BaseCrewComponent._base_inputs,
        HandleInput(name="tasks", display_name="Tasks", input_types=["SequentialTask"], is_list=True),
    ]

    @property
    def agents(self: "SequentialCrewComponent") -> list:
        # Derive agents directly from linked tasks
        return [task.agent for task in self.tasks if hasattr(task, "agent")]

    def get_tasks_and_agents(self, agents_list=None) -> tuple[list, list]:
        # Use the agents property to derive agents
        if not agents_list:
            existing_agents = self.agents
            agents_list = existing_agents + (agents_list or [])

        return super().get_tasks_and_agents(agents_list=agents_list)

    def build_crew(self) -> Message:
        try:
            from crewai import Crew, Process
        except ImportError as e:
            msg = "CrewAI is not installed. Please install it with `uv pip install crewai`."
            raise ImportError(msg) from e

        tasks, agents = self.get_tasks_and_agents()

        return Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=self.verbose,
            memory=self.memory,
            cache=self.use_cache,
            max_rpm=self.max_rpm,
            share_crew=self.share_crew,
            function_calling_llm=self.function_calling_llm,
            step_callback=self.get_step_callback(),
            task_callback=self.get_task_callback(),
        )
