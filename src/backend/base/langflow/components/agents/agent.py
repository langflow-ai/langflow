from loguru import logger

from langflow.components.agents import (
    AgentActionRouter,
    AgentContextBuilder,
    DecideActionComponent,
    ExecuteActionComponent,
    GenerateThoughtComponent,
    ProvideFinalAnswerComponent,
)
from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.outputs import ChatOutput
from langflow.components.prompts import PromptComponent
from langflow.custom import Component
from langflow.graph.graph.base import Graph
from langflow.graph.state.model import create_state_model
from langflow.io import BoolInput, HandleInput, IntInput, MessageTextInput, MultilineInput, Output
from langflow.schema.message import Message


class Agent(Component):
    display_name = "Agent"
    description = "Customizable Agent component"

    inputs = [
        HandleInput(name="agent_context", display_name="Agent Context", input_types=["AgentContext"], required=True),
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

    def get_response(self) -> Message:
        # Chat input initialization
        chat_input = ChatInput().set(input_value=self.user_prompt)

        # Agent Context Builder
        agent_context = AgentContextBuilder().set(
            initial_context=chat_input.message_response,
            tools=self.tools,
            llm=self.llm,
            max_iterations=self.max_iterations,
        )

        # Generate Thought
        generate_thought = GenerateThoughtComponent().set(
            agent_context=agent_context.build_context,
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
        output_model = create_state_model("AgentOutput", output=chat_output.message_response)

        # Build the graph
        graph = Graph(chat_input, chat_output)
        for result in graph.start():
            if self.verbose:
                logger.info(result)

        return output_model.output
