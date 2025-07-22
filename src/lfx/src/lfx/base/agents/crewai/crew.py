from collections.abc import Callable
from typing import Any, cast

import litellm
from pydantic import SecretStr

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import HandleInput, InputTypes
from lfx.io import BoolInput, IntInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI


def _find_api_key(model):
    """Attempts to find the API key attribute for a LangChain LLM model instance using partial matching.

    Args:
        model: LangChain LLM model instance.

    Returns:
        The API key if found, otherwise None.
    """
    # Define the possible API key attribute patterns
    key_patterns = ["key", "token"]

    # Iterate over the model attributes
    for attr in dir(model):
        attr_lower = attr.lower()

        # Check if the attribute name contains any of the key patterns
        if any(pattern in attr_lower for pattern in key_patterns):
            value = getattr(model, attr, None)

            # Check if the value is a non-empty string
            if isinstance(value, str):
                return value
            if isinstance(value, SecretStr):
                return value.get_secret_value()

    return None


def convert_llm(llm: Any, excluded_keys=None):
    """Converts a LangChain LLM object to a CrewAI-compatible LLM object.

    Args:
        llm: A LangChain LLM object.
        excluded_keys: A set of keys to exclude from the conversion.

    Returns:
        A CrewAI-compatible LLM object
    """
    try:
        from crewai import LLM
    except ImportError as e:
        msg = "CrewAI is not installed. Please install it with `uv pip install crewai`."
        raise ImportError(msg) from e

    if not llm:
        return None

    # Check if this is already an LLM object
    if isinstance(llm, LLM):
        return llm

    # Check if we should use model_name model, or something else
    if hasattr(llm, "model_name") and llm.model_name:
        model_name = llm.model_name
    elif hasattr(llm, "model") and llm.model:
        model_name = llm.model
    elif hasattr(llm, "deployment_name") and llm.deployment_name:
        model_name = llm.deployment_name
    else:
        msg = "Could not find model name in the LLM object"
        raise ValueError(msg)

    # Normalize to the LLM model name
    # Remove langchain_ prefix if present
    provider = llm.get_lc_namespace()[0]
    api_base = None
    if provider.startswith("langchain_"):
        provider = provider[10:]
        model_name = f"{provider}/{model_name}"
    elif hasattr(llm, "azure_endpoint"):
        api_base = llm.azure_endpoint
        model_name = f"azure/{model_name}"

    # Retrieve the API Key from the LLM
    if excluded_keys is None:
        excluded_keys = {"model", "model_name", "_type", "api_key", "azure_deployment"}

    # Find the API key in the LLM
    api_key = _find_api_key(llm)

    # Convert Langchain LLM to CrewAI-compatible LLM object
    return LLM(
        model=model_name,
        api_key=api_key,
        api_base=api_base,
        **{k: v for k, v in llm.dict().items() if k not in excluded_keys},
    )


def convert_tools(tools):
    """Converts LangChain tools to CrewAI-compatible tools.

    Args:
        tools: A LangChain tools list.

    Returns:
        A CrewAI-compatible tools list.
    """
    try:
        from crewai.tools.base_tool import Tool
    except ImportError as e:
        msg = "CrewAI is not installed. Please install it with `uv pip install crewai`."
        raise ImportError(msg) from e

    if not tools:
        return []

    return [Tool.from_langchain(tool) for tool in tools]


class BaseCrewComponent(Component):
    description: str = (
        "Represents a group of agents, defining how they should collaborate and the tasks they should perform."
    )
    icon = "CrewAI"

    _base_inputs: list[InputTypes] = [
        IntInput(name="verbose", display_name="Verbose", value=0, advanced=True),
        BoolInput(name="memory", display_name="Memory", value=False, advanced=True),
        BoolInput(name="use_cache", display_name="Cache", value=True, advanced=True),
        IntInput(name="max_rpm", display_name="Max RPM", value=100, advanced=True),
        BoolInput(name="share_crew", display_name="Share Crew", value=False, advanced=True),
        HandleInput(
            name="function_calling_llm",
            display_name="Function Calling LLM",
            input_types=["LanguageModel"],
            info="Turns the ReAct CrewAI agent into a function-calling agent",
            required=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    # Model properties to exclude when creating a CrewAI LLM object
    manager_llm = None

    def task_is_valid(self, task_data: Data, crew_type) -> bool:
        return "task_type" in task_data and task_data.task_type == crew_type

    def get_tasks_and_agents(self, agents_list=None) -> tuple[list, list]:
        # Allow passing a custom list of agents
        if not agents_list:
            agents_list = self.agents or []

        # Set all the agents llm attribute to the crewai llm
        for agent in agents_list:
            # Convert Agent LLM and Tools to proper format
            agent.llm = convert_llm(agent.llm)
            agent.tools = convert_tools(agent.tools)

        return self.tasks, agents_list

    def get_manager_llm(self):
        if not self.manager_llm:
            return None

        self.manager_llm = convert_llm(self.manager_llm)

        return self.manager_llm

    def build_crew(self):
        msg = "build_crew must be implemented in subclasses"
        raise NotImplementedError(msg)

    def get_task_callback(
        self,
    ) -> Callable:
        try:
            from crewai.task import TaskOutput
        except ImportError as e:
            msg = "CrewAI is not installed. Please install it with `uv pip install crewai`."
            raise ImportError(msg) from e

        def task_callback(task_output: TaskOutput) -> None:
            vertex_id = self._vertex.id if self._vertex else self.display_name or self.__class__.__name__
            self.log(task_output.model_dump(), name=f"Task (Agent: {task_output.agent}) - {vertex_id}")

        return task_callback

    def get_step_callback(
        self,
    ) -> Callable:
        try:
            from langchain_core.agents import AgentFinish
        except ImportError as e:
            msg = "langchain_core is not installed. Please install it with `uv pip install langchain-core`."
            raise ImportError(msg) from e

        def step_callback(agent_output) -> None:
            id_ = self._vertex.id if self._vertex else self.display_name
            if isinstance(agent_output, AgentFinish):
                messages = agent_output.messages
                self.log(cast("dict", messages[0].to_json()), name=f"Finish (Agent: {id_})")
            elif isinstance(agent_output, list):
                messages_dict_ = {f"Action {i}": action.messages for i, (action, _) in enumerate(agent_output)}
                # Serialize the messages with to_json() to avoid issues with circular references
                serializable_dict = {k: [m.to_json() for m in v] for k, v in messages_dict_.items()}
                messages_dict = {k: v[0] if len(v) == 1 else v for k, v in serializable_dict.items()}
                self.log(messages_dict, name=f"Step (Agent: {id_})")

        return step_callback

    async def build_output(self) -> Message:
        try:
            crew = self.build_crew()
            result = await crew.kickoff_async()
            message = Message(text=result.raw, sender=MESSAGE_SENDER_AI)
        except litellm.exceptions.BadRequestError as e:
            raise ValueError(e) from e

        self.status = message

        return message
