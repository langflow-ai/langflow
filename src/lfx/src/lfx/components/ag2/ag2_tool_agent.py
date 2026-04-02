"""AG2 Tool-Using Agent component for Langflow."""

import json
from datetime import datetime, timezone

from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, MultilineInput, Output
from lfx.schema.message import Message


class AG2ToolAgentComponent(Component):
    display_name = "AG2 Tool Agent"
    description = "Run an AG2 agent with built-in tools (current time, calculator)."
    icon = "AG2"
    name = "AG2ToolAgent"

    inputs = [
        HandleInput(
            name="llm_config",
            display_name="LLM Config",
            input_types=["Data"],
            info="AG2 LLM configuration.",
        ),
        MultilineInput(
            name="message",
            display_name="Message",
            info="The user message to send to the tool-using agent.",
            value="",
        ),
        MultilineInput(
            name="system_message",
            display_name="System Message",
            info="Instructions for the agent.",
            value="You are a helpful assistant with access to tools.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="run_tool_agent", types=["Message"]),
    ]

    def run_tool_agent(self) -> Message:
        if not self.message.strip():
            msg = "Message cannot be empty."
            raise ValueError(msg)

        try:
            from autogen import AssistantAgent, UserProxyAgent
        except ImportError as e:
            msg = 'AG2 is not installed. Run: pip install "ag2[openai]>=0.11.4,<1.0"'
            raise ImportError(msg) from e

        assistant = AssistantAgent(
            name="ToolAssistant",
            system_message=self.system_message,
            llm_config=self.llm_config,
        )

        user_proxy = UserProxyAgent(
            name="User",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=10,
            code_execution_config=False,
        )

        # Register built-in tools
        @user_proxy.register_for_execution()
        @assistant.register_for_llm(description="Get current date and time in ISO format")
        def get_current_time() -> str:
            return datetime.now(tz=timezone.utc).isoformat()

        @user_proxy.register_for_execution()
        @assistant.register_for_llm(description="Evaluate a mathematical expression safely")
        def calculate(expression: str) -> str:
            allowed = set("0123456789+-*/.() ")
            if not all(c in allowed for c in expression):
                return json.dumps({"error": "Only basic math operations allowed"})
            result = eval(expression)  # noqa: S307
            return json.dumps({"expression": expression, "result": result})

        user_proxy.run(assistant, message=self.message).process()

        # Extract last assistant message
        messages = assistant.chat_messages.get(user_proxy, [])
        answer = ""
        for msg in reversed(messages):
            content = msg.get("content", "").strip()
            if content:
                answer = content.replace("TERMINATE", "").strip()
                if answer:
                    break

        self.status = f"Tool Agent completed: {len(messages)} messages"
        return Message(text=answer or "No answer generated.")
