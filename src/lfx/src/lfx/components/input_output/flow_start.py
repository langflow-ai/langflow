import base64
import json
from pathlib import Path
from typing import Any

from lfx.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput
from lfx.io import (
    DropdownInput,
    FileInput,
    MessageTextInput,
    MultilineInput,
    Output,
)
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.utils.constants import (
    MESSAGE_SENDER_AI,
    MESSAGE_SENDER_NAME_USER,
    MESSAGE_SENDER_USER,
)


class FlowStartComponent(Component):
    display_name = "Flow Start"
    name = "FlowStart"
    icon = "play-circle"
    description = "Universal entry point for flows. Choose input type: Chat, JSON, Files, or Webhook."
    documentation = "https://docs.langflow.org/flow-start"
    beta = False

    default_keys = ["input_type", "code", "_type"]

    inputs = [
        DropdownInput(
            name="input_type",
            display_name="Input Type",
            options=["Chat", "JSON", "Files", "Webhook"],
            value="Chat",
            info="Select how this flow receives input.",
            real_time_refresh=True,
            advanced=False,
        ),
        # Chat mode fields (default)
        MultilineInput(
            name="input_value",
            display_name="Input Text",
            value="",
            info="Message to be passed as input.",
            input_types=[],
        ),
        BoolInput(
            name="should_store_message",
            display_name="Store Messages",
            info="Store the message in the history.",
            value=True,
            advanced=True,
        ),
        DropdownInput(
            name="sender",
            display_name="Sender Type",
            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],
            value=MESSAGE_SENDER_USER,
            info="Type of sender.",
            advanced=True,
        ),
        MessageTextInput(
            name="sender_name",
            display_name="Sender Name",
            info="Name of the sender.",
            value=MESSAGE_SENDER_NAME_USER,
            advanced=True,
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID of the chat. If empty, the current session ID parameter will be used.",
            advanced=True,
        ),
        MessageTextInput(
            name="context_id",
            display_name="Context ID",
            info="The context ID of the chat. Adds an extra layer to the local memory.",
            value="",
            advanced=True,
        ),
        FileInput(
            name="files",
            display_name="Files",
            file_types=TEXT_FILE_TYPES + IMG_FILE_TYPES,
            info="Files to be sent with the message.",
            advanced=True,
            is_list=True,
            temp_file=True,
        ),
    ]

    outputs = [Output(display_name="Message", name="message", method="build_chat_message")]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        """Update build config when input_type changes."""
        if field_name == "input_type":
            # Remove all mode-specific fields
            keys_to_remove = [key for key in build_config if key not in self.default_keys]
            for key in keys_to_remove:
                build_config.pop(key, None)

            # Add fields for selected mode
            mode_fields = self._get_fields_for_mode(field_value)
            for field in mode_fields:
                build_config[field.name] = field.to_dict()

        return build_config

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Update outputs when input_type changes."""
        if field_name == "input_type":
            outputs = self._get_outputs_for_mode(field_value)
            frontend_node["outputs"] = outputs
        return frontend_node

    # ========== Helper Methods for Field Management ==========

    def _get_fields_for_mode(self, mode: str) -> list:
        """Return the list of input fields for the selected mode."""
        field_configs = {
            "Chat": self._get_chat_input_fields(),
            "JSON": self._get_json_input_fields(),
            "Files": self._get_files_fields(),
            "Webhook": self._get_webhook_fields(),
        }
        return field_configs.get(mode, [])

    def _get_outputs_for_mode(self, mode: str) -> list[Output]:
        """Return the list of outputs for the selected mode."""
        output_configs = {
            "Chat": [Output(display_name="Message", name="message", method="build_chat_message")],
            "JSON": [
                Output(display_name="Method", name="method", method="get_method"),
                Output(display_name="Headers", name="headers", method="get_headers"),
                Output(display_name="Body", name="body", method="get_body"),
                Output(display_name="Query", name="query", method="get_query"),
                Output(display_name="Path", name="path", method="get_path"),
                Output(display_name="URL", name="url", method="get_url"),
            ],
            "Files": [Output(display_name="Data", name="data", method="build_files_value")],
            "Webhook": [Output(display_name="Data", name="data", method="build_webhook_data")],
        }
        return output_configs.get(mode, [])

    # ========== Field Definitions by Mode ==========

    def _get_chat_input_fields(self) -> list:
        """Fields for Chat Input mode."""
        return [
            MultilineInput(
                name="input_value",
                display_name="Input Text",
                value="",
                info="Message to be passed as input.",
                input_types=[],
            ),
            BoolInput(
                name="should_store_message",
                display_name="Store Messages",
                info="Store the message in the history.",
                value=True,
                advanced=True,
            ),
            DropdownInput(
                name="sender",
                display_name="Sender Type",
                options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],
                value=MESSAGE_SENDER_USER,
                info="Type of sender.",
                advanced=True,
            ),
            MessageTextInput(
                name="sender_name",
                display_name="Sender Name",
                info="Name of the sender.",
                value=MESSAGE_SENDER_NAME_USER,
                advanced=True,
            ),
            MessageTextInput(
                name="session_id",
                display_name="Session ID",
                info="The session ID of the chat. If empty, the current session ID parameter will be used.",
                advanced=True,
            ),
            MessageTextInput(
                name="context_id",
                display_name="Context ID",
                info="The context ID of the chat. Adds an extra layer to the local memory.",
                value="",
                advanced=True,
            ),
            FileInput(
                name="files",
                display_name="Files",
                file_types=TEXT_FILE_TYPES + IMG_FILE_TYPES,
                info="Files to be sent with the message.",
                advanced=True,
                is_list=True,
                temp_file=True,
            ),
        ]

    def _get_json_input_fields(self) -> list:
        """Fields for JSON Input mode."""
        return [
            MultilineInput(
                name="payload",
                display_name="JSON Payload",
                info="Manual JSON payload for testing (will be overridden by actual HTTP request when used via API)",
                value=(
                    '{\n  "method": "POST",\n  "headers": {"Content-Type": "application/json"},'
                    '\n  "body": {"name": "test", "value": 123},\n  "query": {"page": "1"},'
                    '\n  "path": {"id": "456"},\n  "url": "/api/test/456"\n}'
                ),
                advanced=False,
            ),
        ]

    def _get_webhook_fields(self) -> list:
        """Fields for Webhook mode."""
        return [
            MultilineInput(
                name="data",
                display_name="Webhook Data",
                info="Receives payload from external systems via HTTP POST",
                advanced=True,
            ),
            MultilineInput(
                name="curl",
                display_name="cURL Reference",
                info="cURL command reference",
                value="CURL_WEBHOOK",
                advanced=True,
                input_types=[],
            ),
            MultilineInput(
                name="endpoint",
                display_name="Endpoint URL",
                info="Endpoint URL",
                value="BACKEND_URL",
                copy_field=True,
                input_types=[],
            ),
        ]

    def _get_files_fields(self) -> list:
        """Fields for Files mode."""
        return [
            FileInput(
                name="files_value",
                display_name="Files",
                info="Select files to read",
                file_types=TEXT_FILE_TYPES + IMG_FILE_TYPES,
                is_list=True,
            ),
        ]

    # ========== Output Methods: Chat Input Mode ==========

    async def build_chat_message(self) -> Message:
        """Build message for Chat Input mode."""
        # Handle files
        files = getattr(self, "files", None) or []
        if not isinstance(files, list):
            files = [files]
        files = [f for f in files if f is not None and f != ""]

        # Get session ID
        session_id = ""
        if hasattr(self, "session_id") and self.session_id:
            session_id = self.session_id
        elif hasattr(self, "graph") and hasattr(self.graph, "session_id"):
            session_id = self.graph.session_id or ""

        # Create message
        message = await Message.create(
            text=getattr(self, "input_value", ""),
            sender=getattr(self, "sender", MESSAGE_SENDER_USER),
            sender_name=getattr(self, "sender_name", MESSAGE_SENDER_NAME_USER),
            session_id=session_id,
            context_id=getattr(self, "context_id", ""),
            files=files,
        )

        # Store message if enabled
        if session_id and isinstance(message, Message) and getattr(self, "should_store_message", True):
            stored_message = await self.send_message(message)
            message = stored_message

        self.status = message
        return message

    # ========== Output Methods: JSON Input Mode ==========

    def _get_payload_data(self) -> dict:
        """Get payload data from graph context or manual input.

        Priority:
        1. Request data from graph context (injected by /run endpoint)
        2. Manual payload field (for testing in UI)
        """
        # Check graph context first (injected by API endpoint)
        if hasattr(self, "graph") and self.graph is not None:
            context = getattr(self.graph, "context", None)
            if context is not None:
                request_data = context.get("request_data")
                if request_data is not None:
                    return request_data

        # Fall back to manual payload field
        try:
            payload_text = getattr(self, "payload", "{}")
            return json.loads(payload_text)
        except (json.JSONDecodeError, AttributeError):
            return {"method": "GET", "headers": {}, "body": {}, "query": {}, "path": {}, "url": "/"}

    def get_method(self) -> Message:
        """Returns the HTTP method as a Message."""
        data = self._get_payload_data()
        return Message(text=data.get("method", "GET"))

    def get_headers(self) -> Data:
        """Returns request headers as Data."""
        data = self._get_payload_data()
        headers = data.get("headers", {})
        return Data(data=headers)

    def get_body(self) -> Data:
        """Returns request body as Data."""
        data = self._get_payload_data()
        body = data.get("body", {})
        return Data(data=body)

    def get_query(self) -> Data:
        """Returns query parameters as Data."""
        data = self._get_payload_data()
        query = data.get("query", {})
        return Data(data=query)

    def get_path(self) -> Data:
        """Returns path parameters as Data."""
        data = self._get_payload_data()
        path = data.get("path", {})
        return Data(data=path)

    def get_url(self) -> Message:
        """Returns the request URL as a Message."""
        data = self._get_payload_data()
        url = data.get("url", "/")
        return Message(text=url)

    # ========== Output Methods: Webhook Mode ==========

    def build_webhook_data(self) -> Data:
        """Build data for Webhook mode."""
        if not hasattr(self, "data") or not self.data:
            self.status = "No data provided."
            return Data(data={})

        try:
            # Handle newline escaping issues
            my_data = self.data.replace('"\n"', '"\\n"')
            body = json.loads(my_data or "{}")
            message = None
        except json.JSONDecodeError:
            body = {"payload": self.data}
            message = f"Invalid JSON payload. Please check the format.\n\n{self.data}"

        data = Data(data=body)
        if message:
            self.status = message
        else:
            self.status = data
        return data

    # ========== Output Methods: Files Mode ==========

    def build_files_value(self) -> Data:
        """Build output for Files mode - reads file bytes."""
        value = getattr(self, "files_value", None)

        if not value:
            self.status = "No files provided"
            return Data(data={})

        # Ensure value is a list
        files = value if isinstance(value, list) else [value]
        files = [f for f in files if f]

        if not files:
            self.status = "No valid files provided"
            return Data(data={})

        # Read file(s) and return structured data
        if len(files) == 1:
            # Single file - return flat structure
            file_path = files[0]
            try:
                path = Path(file_path)
                if not path.exists():
                    return Data(data={"error": f"File not found - {file_path}"})

                # Read file as bytes and encode as base64
                file_bytes = path.read_bytes()
                file_b64 = base64.b64encode(file_bytes).decode("utf-8")

                self.status = f"Read file: {path.name}"
                return Data(
                    data={
                        "path": str(file_path),
                        "name": path.name,
                        "size": len(file_bytes),
                        "content": file_b64,
                    }
                )
            except OSError as e:
                return Data(data={"error": f"Error reading {file_path}: {e}"})
        else:
            # Multiple files - return array of file objects
            file_data = []
            for file_path in files:
                try:
                    path = Path(file_path)
                    if not path.exists():
                        file_data.append({"path": str(file_path), "error": "File not found"})
                        continue

                    # Read file as bytes and encode as base64
                    file_bytes = path.read_bytes()
                    file_b64 = base64.b64encode(file_bytes).decode("utf-8")

                    file_data.append(
                        {
                            "path": str(file_path),
                            "name": path.name,
                            "size": len(file_bytes),
                            "content": file_b64,
                        }
                    )
                except OSError as e:
                    file_data.append({"path": str(file_path), "error": str(e)})

            self.status = f"Read {len(file_data)} file(s)"
            return Data(data={"files": file_data})
