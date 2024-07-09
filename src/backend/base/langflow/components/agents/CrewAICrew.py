from typing import Any

from crewai import Crew, Process

from langflow.custom import Component
from langflow.io import BoolInput, DropdownInput, HandleInput, IntInput, MessageTextInput, NestedDictInput, Output
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message


class CrewAICrew(Component):
    display_name: str = "CrewAICrew"
    description: str = (
        "Represents a group of agents, defining how they should collaborate and the tasks they should perform."
    )
    documentation: str = "https://docs.crewai.com/how-to/LLM-Connections/"
    icon = "CrewAI"

    inputs = [
        HandleInput(name="tasks", display_name="Tasks", input_types=["Task"], is_list=True),
        HandleInput(
            name="agents", display_name="Agents", input_types=["Agent"], is_list=True, required=False, advanced=True
        ),
        MessageTextInput(name="topic", display_name="Topic"),
        IntInput(name="verbose", display_name="Verbose", value=0, advanced=True),
        BoolInput(name="memory", display_name="Memory", value=False, advanced=True),
        BoolInput(name="use_cache", display_name="Cache", value=True, advanced=True),
        IntInput(name="max_rpm", display_name="Max RPM", value=100, advanced=True),
        DropdownInput(
            name="process",
            display_name="Process",
            value=Process.sequential,
            options=[Process.sequential, Process.hierarchical],
        ),
        BoolInput(name="share_crew", display_name="Share Crew", value=False, advanced=True),
        NestedDictInput(name="input", display_name="Input", value={"topic": ""}, is_list=True),
        HandleInput(
            name="manager_llm", display_name="Manager LLM", input_types=["LanguageModel"], required=False, advanced=True
        ),
        HandleInput(
            name="manager_agent", display_name="Manager Agent", input_types=["Agent"], required=False, advanced=True
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "process" and field_value is not None:
            is_sequential = field_value == Process.sequential
            build_config["process"]["value"] = field_value
            build_config["manager_llm"]["advanced"] = is_sequential
            build_config["manager_agent"]["advanced"] = is_sequential

    async def build_output(self) -> Message:
        if not self.agents:
            if not self.tasks:
                raise ValueError("No agents or tasks have been added.")
            self.agents = [task.agent for task in self.tasks]

        response = Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=self.process,
            verbose=self.verbose,
            memory=self.memory,
            cache=self.use_cache,
            max_rpm=self.max_rpm,
            share_crew=self.share_crew,
        )
        message = await response.kickoff_async(inputs=self.input)
        self.status = message
        return message
