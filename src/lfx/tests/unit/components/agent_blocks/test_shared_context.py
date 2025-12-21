"""Tests for SharedContextComponent."""

from unittest.mock import MagicMock

import pytest
from lfx.components.agent_blocks.shared_context import SharedContextComponent
from lfx.schema.data import Data
from lfx.schema.message import Message


class TestSharedContextComponent:
    """Tests for SharedContextComponent functionality."""

    def _create_component_with_context(self, **kwargs) -> SharedContextComponent:
        """Create a component with a mock graph context."""
        component = SharedContextComponent(**kwargs)
        mock_vertex = MagicMock()
        mock_vertex.graph = MagicMock()
        mock_vertex.graph.context = {}
        component._vertex = mock_vertex
        return component

    # === Basic Operations ===

    async def test_set_and_get_string(self):
        """Test setting and getting a string value."""
        component = self._create_component_with_context(key="test_key", operation="set", value="test_value")
        result = await component.execute()
        assert result == "test_value"

        # Get it back
        component = component.set(operation="get")
        result = await component.execute()
        assert result == "test_value"

    async def test_set_and_get_dict(self):
        """Test setting and getting a dictionary value."""
        test_dict = {"name": "PR Review", "status": "pending", "count": 42}
        component = self._create_component_with_context(key="pr_data", operation="set", value=test_dict)
        await component.execute()

        component = component.set(operation="get")
        result = await component.execute()
        assert result == test_dict
        assert result["count"] == 42

    async def test_set_and_get_message(self):
        """Test setting and getting a Message object."""
        msg = Message(text="Hello from agent", data={"sender": "reviewer"})
        component = self._create_component_with_context(key="agent_response", operation="set", value=msg)
        await component.execute()

        component = component.set(operation="get")
        result = await component.execute()
        assert isinstance(result, Message)
        assert result.text == "Hello from agent"
        assert result.data["sender"] == "reviewer"

    async def test_set_and_get_data(self):
        """Test setting and getting a Data object."""
        data = Data(data={"findings": ["issue1", "issue2"], "severity": "high"})
        component = self._create_component_with_context(key="review_data", operation="set", value=data)
        await component.execute()

        component = component.set(operation="get")
        result = await component.execute()
        assert isinstance(result, Data)
        assert result.data["severity"] == "high"
        assert len(result.data["findings"]) == 2

    # === Get Operation Edge Cases ===

    async def test_get_nonexistent_key_with_default_empty(self):
        """Test getting a nonexistent key returns None when default_empty is True."""
        component = self._create_component_with_context(key="nonexistent", operation="get", default_empty=True)
        result = await component.execute()
        assert result is None

    async def test_get_nonexistent_key_raises_error(self):
        """Test getting a nonexistent key raises KeyError when default_empty is False."""
        component = self._create_component_with_context(key="nonexistent", operation="get", default_empty=False)
        with pytest.raises(KeyError, match="not found in shared context"):
            await component.execute()

    # === Append Operation ===

    async def test_append_creates_list(self):
        """Test append creates a new list if key doesn't exist."""
        component = self._create_component_with_context(key="findings", operation="append", value="finding1")
        result = await component.execute()
        assert result == ["finding1"]

    async def test_append_to_existing_list(self):
        """Test append adds to existing list."""
        component = self._create_component_with_context(key="findings", operation="append", value="finding1")
        await component.execute()

        component = component.set(value="finding2")
        result = await component.execute()
        assert result == ["finding1", "finding2"]

        component = component.set(value="finding3")
        result = await component.execute()
        assert result == ["finding1", "finding2", "finding3"]

    async def test_append_converts_non_list_to_list(self):
        """Test append converts existing non-list value to list."""
        component = self._create_component_with_context(key="data", operation="set", value="initial")
        await component.execute()

        component = component.set(operation="append", value="appended")
        result = await component.execute()
        assert result == ["initial", "appended"]

    async def test_append_messages(self):
        """Test appending Message objects to a list."""
        msg1 = Message(text="Review from agent 1")
        msg2 = Message(text="Review from agent 2")

        component = self._create_component_with_context(key="reviews", operation="append", value=msg1)
        await component.execute()

        component = component.set(value=msg2)
        result = await component.execute()

        assert len(result) == 2
        assert all(isinstance(r, Message) for r in result)
        assert result[0].text == "Review from agent 1"
        assert result[1].text == "Review from agent 2"

    # === Delete Operation ===

    async def test_delete_existing_key(self):
        """Test deleting an existing key."""
        component = self._create_component_with_context(key="to_delete", operation="set", value="value")
        await component.execute()

        component = component.set(operation="delete")
        result = await component.execute()
        assert result is True

        # Verify it's gone
        component = component.set(operation="get", default_empty=True)
        result = await component.execute()
        assert result is None

    async def test_delete_nonexistent_key(self):
        """Test deleting a nonexistent key returns False."""
        component = self._create_component_with_context(key="nonexistent", operation="delete")
        result = await component.execute()
        assert result is False

    # === Keys Operation ===

    async def test_keys_empty(self):
        """Test listing keys when context is empty."""
        component = self._create_component_with_context(key="", operation="keys")
        result = await component.execute()
        assert result == []

    async def test_keys_with_data(self):
        """Test listing keys with stored data."""
        component = self._create_component_with_context(key="key1", operation="set", value="val1")
        await component.execute()

        component = component.set(key="key2", value="val2")
        await component.execute()

        component = component.set(key="key3", value="val3")
        await component.execute()

        component = component.set(operation="keys")
        result = await component.execute()
        assert set(result) == {"key1", "key2", "key3"}

    # === Has Key Operation ===

    async def test_has_key_exists(self):
        """Test has_key returns True for existing key."""
        component = self._create_component_with_context(key="exists", operation="set", value="value")
        await component.execute()

        component = component.set(operation="has_key")
        result = await component.execute()
        assert result is True

    async def test_has_key_not_exists(self):
        """Test has_key returns False for nonexistent key."""
        component = self._create_component_with_context(key="nonexistent", operation="has_key")
        result = await component.execute()
        assert result is False

    # === Namespace Isolation ===

    async def test_namespace_isolation(self):
        """Test that namespaces isolate data properly."""
        # Set in namespace A
        component = self._create_component_with_context(key="data", operation="set", value="value_a", namespace="ns_a")
        await component.execute()

        # Set in namespace B
        component = component.set(value="value_b", namespace="ns_b")
        await component.execute()

        # Get from namespace A
        component = component.set(operation="get", namespace="ns_a")
        result = await component.execute()
        assert result == "value_a"

        # Get from namespace B
        component = component.set(namespace="ns_b")
        result = await component.execute()
        assert result == "value_b"

    async def test_namespace_keys_only_shows_namespace(self):
        """Test that keys operation only shows keys from the current namespace."""
        component = self._create_component_with_context(key="key1", operation="set", value="val1", namespace="ns1")
        await component.execute()

        component = component.set(key="key2")
        await component.execute()

        component = component.set(key="key3", namespace="ns2")
        await component.execute()

        # List keys in ns1
        component = component.set(operation="keys", namespace="ns1")
        result = await component.execute()
        assert set(result) == {"key1", "key2"}

        # List keys in ns2
        component = component.set(namespace="ns2")
        result = await component.execute()
        assert result == ["key3"]

    # === Error Handling ===

    async def test_invalid_operation(self):
        """Test that invalid operation raises ValueError."""
        component = self._create_component_with_context(key="test", operation="invalid_op")
        with pytest.raises(ValueError, match="Invalid operation"):
            await component.execute()

    async def test_set_without_value(self):
        """Test that set without value raises ValueError."""
        component = self._create_component_with_context(key="test", operation="set", value=None)
        with pytest.raises(ValueError, match="Value is required"):
            await component.execute()

    async def test_append_without_value(self):
        """Test that append without value raises ValueError."""
        component = self._create_component_with_context(key="test", operation="append", value=None)
        with pytest.raises(ValueError, match="Value is required"):
            await component.execute()

    # === Multi-Agent Simulation ===

    async def test_multi_agent_workflow(self):
        """Simulate a multi-agent PR review workflow."""
        # Agent 1: Store PR data
        component = self._create_component_with_context(
            key="pr_data",
            operation="set",
            value={"title": "Add feature X", "files": ["main.py", "test.py"]},
            namespace="pr_review",
        )
        await component.execute()

        # Agent 2: Read PR data and add review
        component = component.set(operation="get")
        pr_data = await component.execute()
        assert pr_data["title"] == "Add feature X"

        review1 = Message(text="Code looks good, minor style issues", data={"agent": "code_reviewer"})
        component = component.set(key="reviews", operation="append", value=review1)
        await component.execute()

        # Agent 3: Read PR data and add review
        review2 = Message(text="Tests pass, coverage at 85%", data={"agent": "test_reviewer"})
        component = component.set(value=review2)
        await component.execute()

        # Agent 4: Read PR data and add review
        review3 = Message(text="No security issues found", data={"agent": "security_reviewer"})
        component = component.set(value=review3)
        await component.execute()

        # Aggregator: Get all reviews
        component = component.set(operation="get")
        all_reviews = await component.execute()

        assert len(all_reviews) == 3
        agents = [r.data["agent"] for r in all_reviews]
        assert set(agents) == {"code_reviewer", "test_reviewer", "security_reviewer"}

    # === Tool Generation ===

    async def test_get_tools(self):
        """Test that _get_tools returns the expected tool set."""
        component = self._create_component_with_context(key="test", operation="get")
        tools = await component._get_tools()

        tool_names = [t.name for t in tools]
        assert "shared_context_read" in tool_names
        assert "shared_context_write" in tool_names
        assert "shared_context_append" in tool_names
        assert "shared_context_list" in tool_names
        assert len(tools) == 4
