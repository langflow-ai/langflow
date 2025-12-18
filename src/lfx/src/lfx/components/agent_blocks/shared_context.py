"""SharedContext component for multi-agent collaboration.

This component provides a shared key-value store that enables multiple agents
and components to share data within the same flow execution. It's the foundation
for multi-agent patterns like supervisor, sequential teams, and parallel execution.

Usage patterns:
    1. Store shared data that multiple agents need to read:
       SharedContext(key="task_data", operation="set", value=data)

    2. Have agents write their findings:
       SharedContext(key="reviews", operation="append", value=finding)

    3. Aggregate results from multiple agents:
       SharedContext(key="reviews", operation="get")

    4. Use namespaces to isolate different contexts:
       SharedContext(namespace="pr_review", key="diff", operation="get")
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lfx.custom import Component
from lfx.io import BoolInput, DropdownInput, HandleInput, MessageTextInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message


class SharedContextComponent(Component):
    """A shared key-value store for multi-agent collaboration.

    This component enables multiple agents and components to share data within
    the same flow execution. Data is stored in the graph context and persists
    for the duration of the flow run.

    Use this component to:
    - Share task context (e.g., PR diff, document content) with multiple agents
    - Collect findings from multiple specialized agents
    - Enable agent coordination without passing objects between components
    - Build supervisor patterns where a coordinator agent reads aggregated results

    Operations:
    - get: Retrieve a value by key
    - set: Store a value at key (overwrites existing)
    - append: Add to a list at key (creates list if doesn't exist)
    - delete: Remove a key from the context
    - keys: List all keys in the namespace
    - has_key: Check if a key exists

    Example multi-agent flow:
        1. PRFetcher -> SharedContext(key="pr_data", op="set")
        2. CodeReviewAgent reads SharedContext(key="pr_data", op="get")
        3. CodeReviewAgent -> SharedContext(key="reviews", op="append")
        4. TestReviewAgent reads SharedContext(key="pr_data", op="get")
        5. TestReviewAgent -> SharedContext(key="reviews", op="append")
        6. Aggregator reads SharedContext(key="reviews", op="get")

    Event Tracking:
        Operations are logged in the context under 'shared_ctx:_events' as a list of dicts:
        [{"operation": "set", "key": "task_data", "namespace": "", "timestamp": ...}, ...]
        This enables verification that agents actually contacted the shared context.
    """

    display_name = "Shared Context"
    description = "Store and retrieve shared data for multi-agent collaboration."
    icon = "Database"
    category = "agent_blocks"

    # Key for storing operation events in context
    EVENTS_KEY = "shared_ctx:_events"

    inputs = [
        MessageTextInput(
            name="key",
            display_name="Key",
            info="The key to store or retrieve the value. Use descriptive names like 'task_data' or 'agent_findings'.",
            tool_mode=True,
        ),
        DropdownInput(
            name="operation",
            display_name="Operation",
            info="The operation to perform on the shared context.",
            options=["get", "set", "append", "delete", "keys", "has_key"],
            value="get",
            tool_mode=True,
        ),
        HandleInput(
            name="value",
            display_name="Value",
            info="The value to store (for 'set' and 'append' operations). Supports any data type.",
            input_types=["Message", "Data", "DataFrame"],
            required=False,
        ),
        MessageTextInput(
            name="namespace",
            display_name="Namespace",
            info="Optional namespace to isolate context. Use to separate different multi-agent workflows.",
            value="",
            advanced=True,
            tool_mode=True,
        ),
        BoolInput(
            name="default_empty",
            display_name="Default to Empty",
            info="For 'get' operation: return empty value instead of raising error if key doesn't exist.",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="execute"),
    ]

    def _get_full_key(self, key: str) -> str:
        """Get the full key including namespace prefix.

        Args:
            key: The user-provided key

        Returns:
            The full key with namespace prefix if namespace is set
        """
        if self.namespace:
            return f"shared_ctx:{self.namespace}:{key}"
        return f"shared_ctx:{key}"

    def _get_namespace_prefix(self) -> str:
        """Get the namespace prefix for key filtering.

        Returns:
            The prefix used for all keys in this namespace
        """
        if self.namespace:
            return f"shared_ctx:{self.namespace}:"
        return "shared_ctx:"

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value for storage.

        Handles Message, Data, and other types appropriately.

        Args:
            value: The value to serialize

        Returns:
            The serialized value
        """
        if isinstance(value, Message):
            return {"__type__": "Message", "text": value.text, "data": value.data}
        if isinstance(value, Data):
            return {"__type__": "Data", "data": value.data}
        return value

    def _deserialize_value(self, value: Any) -> Any:
        """Deserialize a value from storage.

        Reconstructs Message, Data, and other types.
        Handles lists by deserializing each item.

        Args:
            value: The serialized value

        Returns:
            The deserialized value
        """
        # Handle lists by deserializing each item
        if isinstance(value, list):
            return [self._deserialize_value(item) for item in value]

        if isinstance(value, dict) and "__type__" in value:
            type_name = value["__type__"]
            if type_name == "Message":
                return Message(text=value.get("text", ""), data=value.get("data"))
            if type_name == "Data":
                return Data(data=value.get("data", {}))
        return value

    def _operation_get(self) -> Any:
        """Get a value from the context.

        Returns:
            The stored value, or empty value if key doesn't exist and default_empty is True

        Raises:
            KeyError: If key doesn't exist and default_empty is False
        """
        full_key = self._get_full_key(self.key)

        if full_key not in self.ctx:
            if self.default_empty:
                return None
            msg = f"Key '{self.key}' not found in shared context"
            if self.namespace:
                msg += f" (namespace: '{self.namespace}')"
            raise KeyError(msg)

        return self._deserialize_value(self.ctx[full_key])

    def _operation_set(self) -> Any:
        """Set a value in the context.

        Returns:
            The stored value (for confirmation)
        """
        if self.value is None:
            msg = "Value is required for 'set' operation"
            raise ValueError(msg)

        full_key = self._get_full_key(self.key)
        serialized = self._serialize_value(self.value)
        self.update_ctx({full_key: serialized})

        return self.value

    def _operation_append(self) -> list[Any]:
        """Append a value to a list in the context.

        If the key doesn't exist, creates a new list.
        If the key exists but is not a list, converts it to a list first.

        Returns:
            The updated list
        """
        if self.value is None:
            msg = "Value is required for 'append' operation"
            raise ValueError(msg)

        full_key = self._get_full_key(self.key)
        serialized = self._serialize_value(self.value)

        # Get existing value or create new list
        if full_key in self.ctx:
            existing = self.ctx[full_key]
            if isinstance(existing, list):
                existing.append(serialized)
                self.update_ctx({full_key: existing})
            else:
                # Convert existing value to list and append
                self.update_ctx({full_key: [existing, serialized]})
        else:
            self.update_ctx({full_key: [serialized]})

        # Return deserialized list
        return [self._deserialize_value(item) for item in self.ctx[full_key]]

    def _operation_delete(self) -> bool:
        """Delete a key from the context.

        Returns:
            True if key was deleted, False if key didn't exist
        """
        full_key = self._get_full_key(self.key)

        if full_key in self.ctx:
            del self.ctx[full_key]
            return True
        return False

    def _operation_keys(self) -> list[str]:
        """List all keys in the namespace.

        Returns:
            List of keys (without the namespace prefix)
        """
        prefix = self._get_namespace_prefix()
        return [
            key[len(prefix) :]
            for key in self.ctx
            if key.startswith(prefix) and isinstance(key, str) and key != self.EVENTS_KEY
        ]

    def _operation_has_key(self) -> bool:
        """Check if a key exists in the context.

        Returns:
            True if key exists, False otherwise
        """
        full_key = self._get_full_key(self.key)
        return full_key in self.ctx

    def _record_event(self, operation: str, key: str | None = None) -> None:
        """Record an operation event for tracking and verification.

        Events are stored in the context under EVENTS_KEY and can be retrieved
        using get_events() to verify that agents actually used the shared context.

        Args:
            operation: The operation performed (get, set, append, delete, keys, has_key)
            key: The key involved in the operation (if applicable)
        """
        event = {
            "operation": operation,
            "key": key or "",
            "namespace": self.namespace or "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component_id": self._id,
        }

        # Get or create events list
        if self.EVENTS_KEY not in self.ctx:
            self.ctx[self.EVENTS_KEY] = []

        self.ctx[self.EVENTS_KEY].append(event)

    @classmethod
    def get_events(cls, context: dict) -> list[dict]:
        """Get all recorded events from a context dict.

        Use this in tests to verify that the shared context was actually contacted.

        Args:
            context: The context dict (from graph.context or shared_ctx in tests)

        Returns:
            List of event dicts with operation, key, namespace, timestamp, component_id
        """
        return context.get(cls.EVENTS_KEY, [])

    async def execute(self) -> Any:
        """Execute the specified operation on the shared context.

        Returns:
            The result of the operation:
            - get: The stored value
            - set: The stored value (confirmation)
            - append: The updated list
            - delete: True if deleted, False if key didn't exist
            - keys: List of keys in the namespace
            - has_key: True if key exists, False otherwise
        """
        operations = {
            "get": self._operation_get,
            "set": self._operation_set,
            "append": self._operation_append,
            "delete": self._operation_delete,
            "keys": self._operation_keys,
            "has_key": self._operation_has_key,
        }

        if self.operation not in operations:
            msg = f"Invalid operation: {self.operation}. Valid operations: {list(operations.keys())}"
            raise ValueError(msg)

        # Record the event before executing
        key_for_event = self.key if self.operation not in ("keys",) else None
        self._record_event(self.operation, key_for_event)

        result = operations[self.operation]()

        # Log for debugging
        self.log(f"SharedContext {self.operation}(key='{self.key}'): {type(result).__name__}")

        return result

    async def _get_tools(self) -> list:
        """Get tools for this component with agent-friendly descriptions.

        Returns tool variants optimized for agent use:
        - shared_context_read: Read shared data
        - shared_context_write: Write shared data
        - shared_context_append: Add to a collection
        - shared_context_list: List available data
        """
        from langchain_core.tools import StructuredTool

        tools = []

        # Get tool - for reading shared data
        async def get_value(key: str, namespace: str = "") -> Any:
            """Read a value from the shared context.

            Use this to access data that other agents or components have stored.
            Common keys include 'task_data', 'pr_data', 'findings', 'reviews'.

            Args:
                key: The key to retrieve
                namespace: Optional namespace for isolation

            Returns:
                The stored value, or None if not found
            """
            self.key = key
            self.namespace = namespace
            self.operation = "get"
            return await self.execute()

        tools.append(
            StructuredTool.from_function(
                coroutine=get_value,
                name="shared_context_read",
                description=(
                    "Read shared data from the context. "
                    "Use to access task data, findings from other agents, or any shared information."
                ),
            )
        )

        # Set tool - for writing shared data
        async def set_value(key: str, value: str, namespace: str = "") -> str:
            """Store a value in the shared context.

            Use this to share data with other agents or store your findings.

            Args:
                key: The key to store under
                value: The value to store (will be converted to string)
                namespace: Optional namespace for isolation

            Returns:
                Confirmation of what was stored
            """
            self.key = key
            self.value = value
            self.namespace = namespace
            self.operation = "set"
            await self.execute()
            return f"Stored '{key}' in shared context"

        tools.append(
            StructuredTool.from_function(
                coroutine=set_value,
                name="shared_context_write",
                description="Store data in the shared context. Use to share your findings or data with other agents.",
            )
        )

        # Append tool - for adding to collections
        async def append_value(key: str, value: str, namespace: str = "") -> str:
            """Append a value to a list in the shared context.

            Use this to add your findings to a collection that multiple agents contribute to.

            Args:
                key: The key of the list to append to
                value: The value to append
                namespace: Optional namespace for isolation

            Returns:
                Confirmation with current count of items
            """
            self.key = key
            self.value = value
            self.namespace = namespace
            self.operation = "append"
            result = await self.execute()
            return f"Appended to '{key}'. Collection now has {len(result)} items."

        tools.append(
            StructuredTool.from_function(
                coroutine=append_value,
                name="shared_context_append",
                description=(
                    "Add an item to a shared collection. "
                    "Use to contribute findings to a list that other agents also add to."
                ),
            )
        )

        # Keys tool - for discovering available data
        async def list_keys(namespace: str = "") -> list[str]:
            """List all keys available in the shared context.

            Use this to discover what data has been stored by other agents or components.

            Args:
                namespace: Optional namespace to filter keys

            Returns:
                List of available keys
            """
            self.namespace = namespace
            self.operation = "keys"
            return await self.execute()

        tools.append(
            StructuredTool.from_function(
                coroutine=list_keys,
                name="shared_context_list",
                description="List all available keys in the shared context. Use to discover what data is available.",
            )
        )

        return tools
