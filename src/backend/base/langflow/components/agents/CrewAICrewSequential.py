from crewai import Crew, Process  # type: ignore

from langflow.custom import Component
from langflow.io import BoolInput, HandleInput, IntInput, Output
from langflow.schema.message import Message


class CrewAICrewSequential(Component):
    display_name: str = "CrewAICrew (Sequential)"
    description: str = (
        "Represents a group of agents, defining how they should collaborate and the tasks they should perform."
    )
    documentation: str = "https://docs.crewai.com/how-to/LLM-Connections/"
    icon = "CrewAI"

    inputs = [
        HandleInput(name="tasks", display_name="Tasks", input_types=["SequentialTask"], is_list=True),
        IntInput(name="verbose", display_name="Verbose", value=0, advanced=True),
        BoolInput(name="memory", display_name="Memory", value=False, advanced=True),
        BoolInput(name="use_cache", display_name="Cache", value=True, advanced=True),
        IntInput(name="max_rpm", display_name="Max RPM", value=100, advanced=True),
        HandleInput(
            name="function_calling_llm",
            display_name="Function Calling LLM",
            input_types=["LanguageModel"],
            required=False,
            advanced=True,
        ),
        BoolInput(name="share_crew", display_name="Share Crew", value=False, advanced=True),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Message:
        agents = [task.agent for task in self.tasks]
        crew = Crew(
            agents=agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=self.verbose,
            memory=self.memory,
            cache=self.use_cache,
            max_rpm=self.max_rpm,
            share_crew=self.share_crew,
            function_calling_llm=self.function_calling_llm,
        )
        result = await crew.kickoff_async()
        message = Message(text=result)
        self.status = message
        return message
