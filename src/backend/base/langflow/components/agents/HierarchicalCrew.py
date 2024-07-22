from crewai import Crew, Process  # type: ignore

from langflow.base.agents.crewai.crew import BaseCrewComponent
from langflow.io import HandleInput


class HierarchicalCrewComponent(BaseCrewComponent):
    display_name: str = "Hierarchical Crew"
    description: str = (
        "Represents a group of agents, defining how they should collaborate and the tasks they should perform."
    )
    documentation: str = "https://docs.crewai.com/how-to/Hierarchical/"
    icon = "CrewAI"

    inputs = BaseCrewComponent._base_inputs + [
        HandleInput(name="agents", display_name="Agents", input_types=["Agent"], is_list=True),
        HandleInput(name="tasks", display_name="Tasks", input_types=["HierarchicalTask"], is_list=True),
        HandleInput(name="manager_llm", display_name="Manager LLM", input_types=["LanguageModel"], required=False),
        HandleInput(name="manager_agent", display_name="Manager Agent", input_types=["Agent"], required=False),
    ]

    def build_crew(self) -> Crew:
        tasks, agents = self.get_tasks_and_agents()
        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=Process.hierarchical,
            verbose=self.verbose,
            memory=self.memory,
            cache=self.use_cache,
            max_rpm=self.max_rpm,
            share_crew=self.share_crew,
            function_calling_llm=self.function_calling_llm,
            manager_agent=self.manager_agent,
            manager_llm=self.manager_llm,
            step_callback=self.get_step_callback(),
            task_callback=self.get_task_callback(),
        )
        return crew
