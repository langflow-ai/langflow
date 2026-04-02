"""AG2 GroupChat component for Langflow."""

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, HandleInput, IntInput, MultilineInput, Output
from lfx.schema.message import Message


class AG2GroupChatComponent(Component):
    display_name = "AG2 GroupChat"
    description = "Run an AG2 multi-agent GroupChat where agents collaborate to produce an answer."
    icon = "AG2"
    name = "AG2GroupChat"

    inputs = [
        HandleInput(
            name="agents",
            display_name="Agents",
            input_types=["Data"],
            info="List of AG2 agents to participate in the GroupChat.",
            is_list=True,
        ),
        HandleInput(
            name="llm_config",
            display_name="Manager LLM Config",
            input_types=["Data"],
            info="LLM config for the GroupChatManager (selects speakers).",
        ),
        MultilineInput(
            name="message",
            display_name="Message",
            info="The user message to send to the agent team.",
            value="",
        ),
        IntInput(
            name="max_rounds",
            display_name="Max Rounds",
            info="Maximum number of conversation rounds.",
            value=8,
            advanced=True,
        ),
        DropdownInput(
            name="speaker_selection",
            display_name="Speaker Selection",
            info="How the next speaker is chosen.",
            options=["auto", "round_robin", "random"],
            value="auto",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="run_groupchat", types=["Message"]),
    ]

    def run_groupchat(self) -> Message:
        if not self.agents:
            msg = "At least one AG2 Agent must be connected."
            raise ValueError(msg)

        if not self.message.strip():
            msg = "Message cannot be empty."
            raise ValueError(msg)

        try:
            from autogen import GroupChat, GroupChatManager, UserProxyAgent
        except ImportError as e:
            msg = 'AG2 is not installed. Run: pip install "ag2[openai]>=0.11.4,<1.0"'
            raise ImportError(msg) from e

        user_proxy = UserProxyAgent(
            name="User",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=0,
            code_execution_config=False,
        )

        group_chat = GroupChat(
            agents=[user_proxy, *list(self.agents)],
            messages=[],
            max_round=self.max_rounds,
            speaker_selection_method=self.speaker_selection,
        )

        manager = GroupChatManager(
            groupchat=group_chat,
            llm_config=self.llm_config,
        )

        user_proxy.run(manager, message=self.message).process()

        # Extract the final non-user message as the answer
        answer = ""
        for msg in reversed(group_chat.messages):
            content = msg.get("content", "").strip()
            name = msg.get("name", "")
            if content and name != "User":
                answer = content.replace("TERMINATE", "").strip()
                if answer:
                    break

        self.status = f"GroupChat completed: {len(group_chat.messages)} messages"

        return Message(text=answer or "No answer generated.", session_id=self.message)
