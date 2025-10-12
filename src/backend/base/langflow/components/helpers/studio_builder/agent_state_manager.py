"""Agent State Manager for Agent Builder workflow state management."""

import json
from typing import Dict, Any, Optional
from datetime import datetime

from langflow.custom.custom_component.component import Component
from langflow.inputs import MessageTextInput, DropdownInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.logging import logger


class AgentStateManager(Component):
    """Tool for managing agent builder workflow state and context."""

    display_name = "Agent State Manager"
    description = "Manage agent builder workflow state and context"
    icon = "save"
    name = "AgentStateManager"
    category = "Helpers"

    # In-memory storage (in production, use Redis or database)
    _memory_store: Dict[str, Any] = {}

    inputs = [
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="Unique identifier for the conversation session",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="operation",
            display_name="Operation",
            info="Operation to perform: store, retrieve, or update",
            options=["store", "retrieve", "update", "clear"],
            value="retrieve",
            tool_mode=True,
        ),
        MessageTextInput(
            name="key",
            display_name="Memory Key",
            info="Key to store/retrieve data (e.g., 'requirements', 'agent_type', 'context')",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="value",
            display_name="Value",
            info="Value to store (required for store/update operations)",
            required=False,
            tool_mode=True,
        ),
        MessageTextInput(
            name="data_type",
            display_name="Data Type",
            info="Type of data: 'json' for structured data, 'text' for strings",
            value="json",
            advanced=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Memory Data", name="data", method="process"),
    ]

    def process(self) -> Data:
        """Process memory operations."""
        try:
            session_key = f"{self.session_id}:{self.key}"

            if self.operation == "store":
                return self._store_data(session_key)
            elif self.operation == "retrieve":
                return self._retrieve_data(session_key)
            elif self.operation == "update":
                return self._update_data(session_key)
            elif self.operation == "clear":
                return self._clear_data(session_key)
            else:
                return Data(data={
                    "error": f"Invalid operation: {self.operation}",
                    "success": False
                })

        except Exception as e:
            logger.error(f"Error in conversation memory: {e}")
            return Data(data={
                "error": str(e),
                "success": False
            })

    def _store_data(self, session_key: str) -> Data:
        """Store data in memory."""
        if not self.value:
            return Data(data={
                "error": "Value is required for store operation",
                "success": False
            })

        # Parse value based on data type
        if self.data_type == "json":
            try:
                parsed_value = json.loads(self.value) if isinstance(self.value, str) else self.value
            except json.JSONDecodeError as e:
                return Data(data={
                    "error": f"Invalid JSON: {str(e)}",
                    "success": False
                })
        else:
            parsed_value = self.value

        # Store with metadata
        self._memory_store[session_key] = {
            "value": parsed_value,
            "timestamp": datetime.now().isoformat(),
            "data_type": self.data_type
        }

        # Also maintain session index
        session_index_key = f"{self.session_id}:_index"
        if session_index_key not in self._memory_store:
            self._memory_store[session_index_key] = []
        if self.key not in self._memory_store[session_index_key]:
            self._memory_store[session_index_key].append(self.key)

        return Data(data={
            "success": True,
            "operation": "store",
            "key": self.key,
            "message": f"Data stored successfully for key: {self.key}"
        })

    def _retrieve_data(self, session_key: str) -> Data:
        """Retrieve data from memory."""
        if session_key not in self._memory_store:
            # Check if requesting session summary
            if self.key == "_summary":
                return self._get_session_summary()

            return Data(data={
                "success": False,
                "value": None,
                "message": f"No data found for key: {self.key}"
            })

        stored_data = self._memory_store[session_key]
        return Data(data={
            "success": True,
            "operation": "retrieve",
            "key": self.key,
            "value": stored_data["value"],
            "timestamp": stored_data["timestamp"],
            "data_type": stored_data["data_type"]
        })

    def _update_data(self, session_key: str) -> Data:
        """Update existing data in memory."""
        if not self.value:
            return Data(data={
                "error": "Value is required for update operation",
                "success": False
            })

        if session_key not in self._memory_store:
            # If doesn't exist, store instead
            return self._store_data(session_key)

        # Parse value based on data type
        if self.data_type == "json":
            try:
                parsed_value = json.loads(self.value) if isinstance(self.value, str) else self.value
            except json.JSONDecodeError as e:
                return Data(data={
                    "error": f"Invalid JSON: {str(e)}",
                    "success": False
                })
        else:
            parsed_value = self.value

        # Update with new timestamp
        old_value = self._memory_store[session_key]["value"]
        self._memory_store[session_key] = {
            "value": parsed_value,
            "timestamp": datetime.now().isoformat(),
            "data_type": self.data_type,
            "previous_value": old_value
        }

        return Data(data={
            "success": True,
            "operation": "update",
            "key": self.key,
            "message": f"Data updated successfully for key: {self.key}",
            "previous_value": old_value
        })

    def _clear_data(self, session_key: str) -> Data:
        """Clear data from memory."""
        if self.key == "_all":
            # Clear all data for the session
            keys_to_remove = [k for k in self._memory_store.keys() if k.startswith(f"{self.session_id}:")]
            for key in keys_to_remove:
                del self._memory_store[key]

            return Data(data={
                "success": True,
                "operation": "clear",
                "message": f"All data cleared for session: {self.session_id}",
                "keys_cleared": len(keys_to_remove)
            })
        else:
            # Clear specific key
            if session_key in self._memory_store:
                del self._memory_store[session_key]
                # Update index
                session_index_key = f"{self.session_id}:_index"
                if session_index_key in self._memory_store and self.key in self._memory_store[session_index_key]:
                    self._memory_store[session_index_key].remove(self.key)

                return Data(data={
                    "success": True,
                    "operation": "clear",
                    "key": self.key,
                    "message": f"Data cleared for key: {self.key}"
                })
            else:
                return Data(data={
                    "success": False,
                    "message": f"No data found to clear for key: {self.key}"
                })

    def _get_session_summary(self) -> Data:
        """Get a summary of all data stored for the session."""
        session_data = {}
        session_prefix = f"{self.session_id}:"

        for key, value in self._memory_store.items():
            if key.startswith(session_prefix) and not key.endswith(":_index"):
                clean_key = key.replace(session_prefix, "")
                session_data[clean_key] = value

        return Data(data={
            "success": True,
            "operation": "summary",
            "session_id": self.session_id,
            "keys": list(session_data.keys()),
            "data": session_data,
            "total_keys": len(session_data)
        })