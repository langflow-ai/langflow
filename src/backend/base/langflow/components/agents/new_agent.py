from loguru import logger

from langflow.components.agents.agent_action_router import AgentActionRouter
from langflow.components.agents.decide_action import DecideActionComponent
from langflow.components.agents.execute_action import ExecuteActionComponent
from langflow.components.agents.generate_thought import GenerateThoughtComponent
from langflow.components.agents.write_final_answer import ProvideFinalAnswerComponent
from langflow.components.inputs.chat import ChatInput
from langflow.components.outputs import ChatOutput
from langflow.components.prompts import PromptComponent
from langflow.custom import Component
from langflow.graph.graph.base import Graph
from langflow.graph.state.model import create_state_model
from langflow.io import BoolInput, HandleInput, IntInput, MessageTextInput, MultilineInput, Output
from langflow.schema.message import Message


class LangflowAgent(Component):
    display_name = "Langflow Agent"
    description = "Customizable Agent component"

    inputs = [
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=True),
        HandleInput(name="tools", display_name="Tools", input_types=["Tool"], is_list=True, required=True),
        IntInput(name="max_iterations", display_name="Max Iterations", value=5),
        BoolInput(name="verbose", display_name="Verbose", value=False),
        MultilineInput(name="system_prompt", display_name="System Prompt", value="You are a helpful assistant."),
        MultilineInput(name="user_prompt", display_name="User Prompt", value="{input}"),
        MultilineInput(
            name="loop_prompt",
            display_name="Loop Prompt",
            value="Last Action Result: {last_action_result}\nBased on the actions taken, here's the final answer:",
        ),
        MessageTextInput(
            name="decide_action_prompt",
            display_name="Decide Action Prompt",
            value="Based on your thought, decide the best action to take next.",
            advanced=True,
        ),
        MessageTextInput(
            name="final_answer_prompt",
            display_name="Final Answer Prompt",
            value="Considering all observations, provide the final answer to the user's query.",
            advanced=True,
        ),
    ]
    outputs = [Output(name="response", display_name="Response", method="get_response")]

    async def get_response(self) -> Message:
        # Chat input initialization
        chat_input = ChatInput().set(input_value=self.user_prompt)

        # Generate Thought
        generate_thought = GenerateThoughtComponent().set(
            prompt="Based on the provided context, generate your next thought.",
        )

        # Decide Action
        decide_action = DecideActionComponent().set(
            agent_context=generate_thought.generate_thought,
            prompt=self.decide_action_prompt,
        )

        # Agent Action Router
        action_router = AgentActionRouter().set(
            agent_context=decide_action.decide_action,
            max_iterations=self.max_iterations,
        )

        # Execute Action
        execute_action = ExecuteActionComponent().set(agent_context=action_router.route_to_execute_tool)
        # Loop Prompt
        loop_prompt = PromptComponent().set(
            template=self.loop_prompt,
            answer=execute_action.execute_action,
        )

        generate_thought.set(prompt=loop_prompt.build_prompt)

        # Final Answer
        final_answer = ProvideFinalAnswerComponent().set(
            agent_context=action_router.route_to_final_answer,
            prompt=self.final_answer_prompt,
        )

        # Chat output
        chat_output = ChatOutput().set(input_value=final_answer.get_final_answer)
        agent_output_model = create_state_model("AgentOutput", output=chat_output.message_response)
        output_model = agent_output_model()

        # Build the graph
        graph = Graph(chat_input, chat_output)
        # Initialize the context
        graph.context = {
            "llm": self.llm,
            "tools": self.tools,
            "initial_message": chat_input.message_response,
            "system_prompt": self.system_prompt,
            "max_iterations": self.max_iterations,
            "iteration": 0,
            "thought": "",
            "last_action": None,
            "last_action_result": None,
            "final_answer": "",
        }

        async for result in graph.async_start(max_iterations=self.max_iterations):
            if self.verbose:
                logger.info(result)

        return output_model.output
