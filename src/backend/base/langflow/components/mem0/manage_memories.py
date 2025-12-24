import asyncio
from typing import Any

from mem0 import AsyncMemoryClient, MemoryClient

from langflow.custom import Component
from langflow.io import (
    BoolInput,
    DropdownInput,
    MessageTextInput,
    Output,
    SecretStrInput,
)
from langflow.schema import Data


class ManageMemoriesComponent(Component):
    display_name = "Manage Memories"
    description = "Manage memories in Mem0: add, update, get, or delete memories."
    icon: str = "Mem0"
    name = "manage_memories"
    documentation = "https://docs.mem0.com/"

    inputs = [
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=["Add", "Update", "Get", "Delete"],
            value="Add",
            info="Select the operation to perform on memories.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="memory_id",
            display_name="Memory ID",
            info="The ID of the memory to get, update, or delete.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="messages",
            display_name="Messages",
            info="Message string to add or update as knowledge.",
            is_list=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="mem0_user_id",
            display_name="User ID",
            info="The unique identifier of the user associated with this memory.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="agent_id",
            display_name="Agent ID",
            info="The unique identifier of the agent associated with this memory.",
            tool_mode=True,
            advanced=True,
        ),
        MessageTextInput(
            name="app_id",
            display_name="App ID",
            info="The unique identifier of the application associated with this memory.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID for the memory. Uses Langflow's session ID if not provided.",
            tool_mode=True,
            advanced=True,
        ),
        BoolInput(
            name="async_mode",
            display_name="Use Async",
            info="Enable asynchronous operation.",
            value=False,
            tool_mode=True,
            advanced=True,
        ),
        BoolInput(
            name="infer",
            display_name="Infer",
            info="Enable inference for the Add operation.",
            value=False,
            tool_mode=True,
            advanced=True,
        ),
        SecretStrInput(name="api_key", display_name="API Key", info="Your Mem0 API Key.", required=True),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Result",
            info="Result of the memory operation as a Data object.",
            method="manage_memory_response",
        ),
    ]

    def validate_inputs(self) -> None:
        if not self.api_key:
            error_message = "API Key is required."
            raise ValueError(error_message)
        if self.operation in ["Add", "Update"] and not self.messages:
            error_message = "Messages are required for Add and Update operations."
            raise ValueError(error_message)
        if self.operation in ["Get", "Update", "Delete"] and not self.memory_id:
            error_message = "Memory ID is required for Get, Update, and Delete operations."
            raise ValueError(error_message)

    def parse_messages(self) -> list[dict[str, Any]]:
        parsed_messages = []
        for idx, msg in enumerate(self.messages, 1):
            try:
                if isinstance(msg, dict):
                    if not all(key in msg for key in ("role", "content")):
                        error_message = f"Message {idx} missing required fields 'role' and/or 'content'"
                        raise ValueError(error_message)
                    parsed_messages.append(msg)
                elif isinstance(msg, str):
                    parsed_messages.append({"role": "user", "content": msg})
                else:
                    error_message = f"Message {idx} must be string or dict with 'role' and 'content'"
                    raise TypeError(error_message)
            except Exception as e:
                error_message = f"Error parsing message {idx}: {e!s}"
                raise ValueError(error_message) from e
        return parsed_messages

    async def manage_memory_response(self) -> Data:
        try:
            self.validate_inputs()
            client = AsyncMemoryClient(api_key=self.api_key) if self.async_mode else MemoryClient(api_key=self.api_key)
            response = None

            if self.operation == "Add":
                messages = self.parse_messages()
                payload = {
                    "messages": messages,
                    "user_id": self.mem0_user_id,
                    "agent_id": self.agent_id,
                    "app_id": self.app_id,
                    "run_id": self.session_id or self.graph.session_id,
                    "infer": self.infer,
                }
                self.log(f"Adding memory with payload: {payload}")
                result = client.add(**payload)
                response = await result if asyncio.iscoroutine(result) else result

            elif self.operation == "Update":
                if not self.messages:
                    error_message = "Messages are required for updating a memory."
                    raise ValueError(error_message)
                message = self.messages[0] if isinstance(self.messages, list) else self.messages
                self.log(f"Updating memory ID {self.memory_id} with message: {message}")
                result = client.update(memory_id=self.memory_id, data=message)
                response = await result if asyncio.iscoroutine(result) else result

            elif self.operation == "Get":
                self.log(f"Getting memory ID {self.memory_id}")
                result = client.get(memory_id=self.memory_id)
                response = await result if asyncio.iscoroutine(result) else result

            elif self.operation == "Delete":
                self.log(f"Deleting memory ID {self.memory_id}")
                result = client.delete(memory_id=self.memory_id)
                response = await result if asyncio.iscoroutine(result) else result

            if response:
                data = Data(text=f"Operation {self.operation} completed successfully.", data=response)
                self.status = data
                return data

            data = Data(text="Error: No response received", data={"error": "No response received"})
            self.status = data
        except (ValueError, TypeError) as e:
            error_data = Data(
                text=f"Error: {e!s}",
                code=500,
                details=str(e),
            )
            self.status = error_data
            return error_data
        else:
            return self.status
