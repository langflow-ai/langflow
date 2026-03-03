"""Tests for Agent Pydantic schemas."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.agents.schema import (
    AgentCreate,
    AgentRead,
    AgentUpdate,
)
from pydantic import ValidationError


class TestAgentCreate:
    """Tests for AgentCreate validation."""

    def test_should_create_with_minimal_fields(self):
        schema = AgentCreate(name="My Agent")
        assert schema.name == "My Agent"
        assert schema.system_prompt == "You are a helpful assistant."
        assert schema.tool_components == []

    def test_should_create_with_all_fields(self):
        schema = AgentCreate(
            name="Full Agent",
            description="A complete agent",
            system_prompt="Be concise.",
            tool_components=["CalculatorComponent"],
            icon="bot",
        )
        assert schema.name == "Full Agent"
        assert schema.description == "A complete agent"
        assert schema.tool_components == ["CalculatorComponent"]

    def test_should_reject_empty_name(self):
        with pytest.raises(ValidationError):
            AgentCreate(name="")

    def test_should_reject_name_exceeding_max_length(self):
        with pytest.raises(ValidationError):
            AgentCreate(name="x" * 256)

    def test_should_accept_name_at_max_length(self):
        schema = AgentCreate(name="x" * 255)
        assert len(schema.name) == 255

    def test_should_default_description_to_none(self):
        schema = AgentCreate(name="Agent")
        assert schema.description is None


class TestAgentUpdate:
    """Tests for AgentUpdate validation — all fields optional."""

    def test_should_allow_empty_update(self):
        schema = AgentUpdate()
        dump = schema.model_dump(exclude_unset=True)
        assert dump == {}

    def test_should_allow_partial_update(self):
        schema = AgentUpdate(name="New Name")
        dump = schema.model_dump(exclude_unset=True)
        assert dump == {"name": "New Name"}

    def test_should_reject_empty_name_when_provided(self):
        with pytest.raises(ValidationError):
            AgentUpdate(name="")


class TestAgentRead:
    """Tests for AgentRead response schema."""

    def test_should_validate_from_dict(self):
        data = {
            "id": uuid4(),
            "name": "Agent",
            "description": None,
            "system_prompt": "Hello",
            "tool_components": ["Calc"],
            "icon": None,
            "user_id": uuid4(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        schema = AgentRead.model_validate(data)
        assert schema.name == "Agent"
        assert schema.tool_components == ["Calc"]

    def test_should_support_from_attributes(self):
        # Simulates ORM mode (from_attributes=True)
        assert AgentRead.model_config.get("from_attributes") is True
