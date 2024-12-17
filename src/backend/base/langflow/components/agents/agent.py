from langchain_core.tools import StructuredTool

from langflow.base.agents.agent import LangflowAgent
from langflow.base.models.model_utils import get_model_name
from langflow.components.helpers import CurrentDateComponent
from langflow.components.helpers.memory import MemoryComponent
from langflow.custom import Component
from langflow.io import Output
from langflow.logging import logger
from langflow.schema.data import Data
from langflow.schema.message import Message


def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input



class AgentComponent(LangflowAgent,Component):
    display_name: str = "Agent"
    description: str = "Define the agent's instructions, then enter a task to complete using tools."
    icon = "bot"
    beta = False
    name = "Agent"

    memory_inputs = [set_advanced_true(component_input) for component_input in MemoryComponent().inputs]

    inputs = [
        *LangflowAgent._agentbase_inputs,
        *memory_inputs,
    ]
    outputs = [Output(name="response", display_name="Response", method="message_response")]

    async def message_response(self) -> Message:
        try:
            llm_model, display_name = self.get_llm()
            if llm_model is None:
                msg = "No language model selected"
                raise ValueError(msg)
            self.model_name = get_model_name(llm_model, display_name=display_name)
        except Exception as e:
            logger.error(f"Error retrieving language model: {e}")
            raise

        try:
            self.chat_history = await self.get_memory_data()
        except Exception as e:
            logger.error(f"Error retrieving chat history: {e}")
            raise

        if self.add_current_date_tool:
            try:
                if not isinstance(self.tools, list):  # type: ignore[has-type]
                    self.tools = []
                # Convert CurrentDateComponent to a StructuredTool
                current_date_tool = CurrentDateComponent().to_toolkit()[0]
                if isinstance(current_date_tool, StructuredTool):
                    self.tools.append(current_date_tool)
                else:
                    msg = "CurrentDateComponent must be converted to a StructuredTool"
                    raise TypeError(msg)
            except Exception as e:
                logger.error(f"Error adding current date tool: {e}")
                raise

        if not self.tools:
            msg = "Tools are required to run the agent."
            logger.error(msg)
            raise ValueError(msg)

        try:
            self.set(
                llm=llm_model,
                tools=self.tools,
                chat_history=self.chat_history,
                input_value=self.input_value,
                system_prompt=self.system_prompt,
            )
            agent = self.create_agent_runnable()
        except Exception as e:
            logger.error(f"Error setting up the agent: {e}")
            raise

        try:
            # Execute the agent and capture any errors during tool execution
            return await self.run_agent(agent)
        except Exception as e:
            logger.error(f"Error during tool execution: {e}")
            raise

    async def get_memory_data(self):
        try:
            memory_kwargs = {
                component_input.name: getattr(self, f"{component_input.name}") for component_input in self.memory_inputs
            }
            return await MemoryComponent().set(**memory_kwargs).retrieve_messages()
        except (AttributeError, ValueError, RuntimeError) as e:
            logger.error(f"Error retrieving memory data: {e}")
            return None

    def get_chat_history_data(self) -> list[Data] | None:
        return self.chat_history
