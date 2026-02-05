from __future__ import annotations

import time

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output
from lfx.schema.message import Message
from lfx.services.cache.utils import CacheMiss
from lfx.services.deps import get_shared_component_cache_service


class VariableComponent(Component):
    display_name = "Variable"
    description = "Persistent variable using component cache."
    documentation = "https://docs.langflow.org/components-custom-components"
    icon = "variable"
    name = "Variable"

    inputs = [
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=["Read", "Write", "Create New", "Delete"],
            value="Read",
            info="Read: returns current value. Write: saves and returns new value. Create New: create a new variable. Delete: removes a variable.",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="variable_name",
            display_name="Variable Name",
            info="Select an existing variable.",
            options=[],
            value="",
            combobox=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="new_variable_name",
            display_name="New Variable Name",
            info="Type the name for your new variable.",
            value="",
        ),
        MessageTextInput(
            name="write_value",
            display_name="New Value",
            info="Value to write (only used in Write mode).",
            value="",
            input_types=["Message"],
        ),
        MessageTextInput(
            name="default_value",
            display_name="Default Value",
            info="Returned if variable doesn't exist (Read mode only).",
            value="",
            advanced=True,
        ),
        IntInput(
            name="ttl",
            display_name="TTL (Time To Live)",
            info="Time in seconds before the variable expires. Default is 3600 (1 hour). Set to 0 for no expiration.",
            value=3600,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Value", name="value", method="execute", types=["Message"]),
    ]

    def _get_cache_key(self, var_name: str) -> str:
        """Generate cache key for variable (shared across flows for same user)."""
        user_id = str(self._user_id) if self._user_id else "global"
        return f"var_{user_id}_{var_name}"

    def _get_shared_cache(self):
        """Get shared cache service for persistence."""
        return get_shared_component_cache_service()

    def _get_variable_value(self, cache_data, raise_on_expired=False):
        """Extract value from cache data, checking TTL expiration.

        Args:
            cache_data: The cached data to extract value from
            raise_on_expired: If True, raises ValueError when variable has expired

        Returns:
            The variable value, or None if not found or expired (when raise_on_expired=False)

        Raises:
            ValueError: If variable has expired and raise_on_expired=True
        """
        if isinstance(cache_data, CacheMiss) or cache_data is None:
            return None

        # If it's a simple string (old format), return as is
        if isinstance(cache_data, str):
            return cache_data

        # If it's a dict with metadata (new format)
        if isinstance(cache_data, dict) and "value" in cache_data:
            ttl = cache_data.get("ttl", 0)
            timestamp = cache_data.get("timestamp", 0)

            # Check if TTL is set and if variable has expired
            if ttl > 0:
                current_time = time.time()
                elapsed = current_time - timestamp
                if elapsed > ttl:
                    if raise_on_expired:
                        raise ValueError(f"Variable has expired (TTL: {ttl}s, elapsed: {elapsed:.1f}s)")
                    return None  # Expired

            return cache_data["value"]

        return None

    async def update_build_config(self, build_config: dict, field_value, field_name: str | None = None) -> dict:
        """Update UI based on operation mode and load saved values."""
        # Get operation value
        operation = field_value if field_name == "operation" else self.operation

        # Populate variable name dropdown with existing variables (excluding expired ones)
        user_id = str(self._user_id) if self._user_id else "global"
        prefix = f"var_{user_id}_"
        shared_cache = self._get_shared_cache()

        # Get all variable names for this user (only non-expired)
        variable_names = []
        if hasattr(shared_cache, "_cache"):
            # Create a copy of keys to avoid "dictionary changed size during iteration" error
            cache_keys = list(shared_cache._cache.keys())
            for key in cache_keys:
                if str(key).startswith(prefix):
                    # Check if variable is expired
                    cache_data = shared_cache.get(key)
                    value = self._get_variable_value(cache_data, raise_on_expired=False)

                    # Only add to list if not expired
                    if value is not None:
                        var_name = str(key).replace(prefix, "", 1)
                        variable_names.append(var_name)

        # Sort alphabetically
        variable_names.sort()
        build_config["variable_name"]["options"] = variable_names

        # Show/hide fields based on operation
        if operation == "Create New":
            build_config["variable_name"]["show"] = False
            build_config["new_variable_name"]["show"] = True
        else:
            build_config["variable_name"]["show"] = True
            build_config["new_variable_name"]["show"] = False

        build_config["write_value"]["show"] = operation in ["Write", "Create New"]
        build_config["default_value"]["show"] = operation == "Read"

        # Load current value from cache (only for Read/Write operations)
        if operation in ["Read", "Write"]:
            var_name = str(self.variable_name).strip() if self.variable_name else ""
            if var_name:
                cache_key = self._get_cache_key(var_name)

                # Try to get from shared cache first
                cache_data = shared_cache.get(cache_key)
                current_value = self._get_variable_value(cache_data)

                # Check if value exists and hasn't expired
                if current_value is not None:
                    # Pre-fill with current value
                    if operation == "Write":
                        build_config["write_value"]["value"] = current_value
                    else:
                        build_config["default_value"]["value"] = current_value

        return build_config

    async def execute(self) -> Message:
        """Execute the variable operation (Read, Write, Create New, or Delete)."""
        # Get variable name based on operation
        if self.operation == "Create New":
            var_name = str(self.new_variable_name).strip() if self.new_variable_name else ""
        else:
            var_name = str(self.variable_name).strip() if self.variable_name else ""

        if not var_name:
            raise ValueError("Variable name is required.")

        cache_key = self._get_cache_key(var_name)
        shared_cache = self._get_shared_cache()

        if self.operation == "Delete":
            # DELETE operation: remove from cache
            # Check if variable exists
            cache_data = shared_cache.get(cache_key)
            value = self._get_variable_value(cache_data)

            if value is None:
                raise ValueError(f"Variable '{var_name}' does not exist or has expired.")

            # Delete from both caches
            if cache_key in self.cache:
                del self.cache[cache_key]
            shared_cache.delete(cache_key)

            self.status = f"Deleted: {var_name}"
            return Message(text=f"Variable '{var_name}' deleted successfully")

        if self.operation in ["Write", "Create New"]:
            # For Create New operation, check if variable already exists
            if self.operation == "Create New":
                cache_data = shared_cache.get(cache_key)
                existing_value = self._get_variable_value(cache_data)
                if existing_value is not None:
                    raise ValueError(f"Variable '{var_name}' already exists. Use 'Write' operation to update it.")

            # WRITE/CREATE operation: store in cache with metadata
            value_to_store = "" if self.write_value is None else str(self.write_value)
            ttl = self.ttl if hasattr(self, "ttl") and self.ttl else 0

            # Create cache entry with metadata
            cache_entry = {"value": value_to_store, "timestamp": time.time(), "ttl": ttl}

            # Store in both local and shared cache
            self.cache[cache_key] = cache_entry
            shared_cache.set(cache_key, cache_entry)

            action = "Created" if self.operation == "Create New" else "Written"
            self.status = f"{action}: {value_to_store}"
            return Message(text=value_to_store)

        # READ operation: get from cache
        # Try local cache first (faster)
        cache_data = self.cache.get(cache_key)
        try:
            value = self._get_variable_value(cache_data, raise_on_expired=True)
        except ValueError:
            # Variable expired in local cache, try shared cache
            cache_data = shared_cache.get(cache_key)
            value = self._get_variable_value(cache_data, raise_on_expired=True)

        # If not in local cache, try shared cache
        if value is None:
            cache_data = shared_cache.get(cache_key)
            value = self._get_variable_value(cache_data, raise_on_expired=True)

            # Store in local cache for next time if found and not expired
            if value is not None and cache_data is not None:
                self.cache[cache_key] = cache_data

        # If still not found, use default
        if value is None:
            value = self.default_value or ""

        self.status = f"Read: {value}"
        return Message(text=value)
