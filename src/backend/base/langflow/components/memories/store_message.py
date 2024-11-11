from langflow.custom import Component
from langflow.inputs import HandleInput, MessageInput
from langflow.inputs.inputs import MessageTextInput
from langflow.memory import get_messages, store_message
from langflow.schema.message import Message
from langflow.template import Output
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI


class StoreMessageComponent(Component):
    display_name = "Store Message"
    description = "Stores a chat message or text into Langflow tables or an external memory."
    icon = "save"
    name = "StoreMessage"

    inputs = [
        MessageInput(name="message", display_name="Message", info="The chat message to be stored.", required=True),
        HandleInput(
            name="memory",
            display_name="External Memory",
            input_types=["BaseChatMessageHistory"],
            info="The external memory to store the message. If empty, it will use the Langflow tables.",
        ),
        MessageTextInput(
            name="sender",
            display_name="Sender",
            info="The sender of the message. Might be Machine or User. "
            "If empty, the current sender parameter will be used.",
            advanced=True,
        ),
        MessageTextInput(
            name="sender_name",
            display_name="Sender Name",
            info="The name of the sender. Might be AI or User. If empty, the current sender parameter will be used.",
            advanced=True,
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID of the chat. If empty, the current session ID parameter will be used.",
            value="",
        ),
    ]

    outputs = [
        Output(display_name="Stored Messages", name="stored_messages", method="store_message"),
    ]

    def store_message(self) -> Message:
        message = self.message

        message.session_id = self.session_id or message.session_id
        message.sender = self.sender or message.sender or MESSAGE_SENDER_AI
        message.sender_name = self.sender_name or message.sender_name or MESSAGE_SENDER_NAME_AI

        if self.memory:
            # override session_id
            self.memory.session_id = message.session_id
            lc_message = message.to_lc_message()
            self.memory.add_messages([lc_message])
            stored = self.memory.messages
            stored = [Message.from_lc_message(m) for m in stored]
            if message.sender:
                stored = [m for m in stored if m.sender == message.sender]
        else:
            store_message(message, flow_id=self.graph.flow_id)
            stored = get_messages(session_id=message.session_id, sender_name=message.sender_name, sender=message.sender)
        self.status = stored
        return stored
