from langflow.custom import Component
from langflow.inputs import HandleInput
from langflow.inputs.inputs import MessageTextInput
from langflow.memory import aget_messages, astore_message
from langflow.schema.message import Message
from langflow.template import Output
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI


class MessageStoreComponent(Component):
    display_name = "Message Store"
    description = "Stores a chat message or text into Langflow tables or an external memory."
    icon = "message-square-text"
    name = "StoreMessage"

    inputs = [
        MessageTextInput(
            name="message", display_name="Message", info="The chat message to be stored.", required=True, tool_mode=True
        ),
        HandleInput(
            name="memory",
            display_name="External Memory",
            input_types=["Memory"],
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
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Stored Messages", name="stored_messages", method="store_message", hidden=True),
    ]

    async def store_message(self) -> Message:
        message = Message(text=self.message) if isinstance(self.message, str) else self.message

        message.session_id = self.session_id or message.session_id
        message.sender = self.sender or message.sender or MESSAGE_SENDER_AI
        message.sender_name = self.sender_name or message.sender_name or MESSAGE_SENDER_NAME_AI

        if self.memory:
            # override session_id
            self.memory.session_id = message.session_id
            lc_message = message.to_lc_message()
            await self.memory.aadd_messages([lc_message])
            stored_message = await self.memory.aget_messages()
            stored_message = [Message.from_lc_message(m) for m in stored_message]
            if message.sender:
                stored_message = [m for m in stored_message if m.sender == message.sender]
        else:
            await astore_message(message, flow_id=self.graph.flow_id)
            stored_messages = await aget_messages(
                session_id=message.session_id, sender_name=message.sender_name, sender=message.sender
            )
        if not stored_messages:
            msg = "No messages were stored. Please ensure that the session ID and sender are properly set."
            raise ValueError(msg)
        stored_message = stored_messages[0]

        self.status = stored_message
        return stored_message
