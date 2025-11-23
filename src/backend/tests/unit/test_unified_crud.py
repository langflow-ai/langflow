"""Tests for the unified CRUD operations layer."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.schema.message import Message
from langflow.services.database.crud import (
    api_key_crud,
    flow_crud,
    message_crud,
    transaction_crud,
    user_crud,
    variable_crud,
    vertex_build_crud,
)
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.message.model import MessageBase, MessageCreate, MessageTable
from langflow.services.database.models.transactions.model import TransactionBase
from langflow.services.database.models.user.model import User, UserCreate
from langflow.services.database.models.variable.model import Variable
from langflow.services.database.models.vertex_builds.model import VertexBuildBase
from langflow.services.deps import session_scope


@pytest.mark.usefixtures("client")
class TestUnifiedCRUD:
    """Test suite for unified CRUD operations."""

    async def test_message_crud_operations(self, async_session):
        """Test basic CRUD operations for messages."""
        # Create a message
        message_data = MessageBase(
            text="Test message",
            sender="User",
            sender_name="Test User",
            session_id="test_session",
            timestamp=datetime.now(timezone.utc),
        )
        message = await message_crud.create(async_session, obj_in=message_data)
        assert message.text == "Test message"
        assert message.id is not None

        # Get the message
        retrieved = await message_crud.get(async_session, message.id)
        assert retrieved is not None
        assert retrieved.text == "Test message"

        # Update the message
        updated = await message_crud.update(
            async_session, db_obj=retrieved, obj_in={"text": "Updated message", "edit": True}
        )
        assert updated.text == "Updated message"
        assert updated.edit is True

        # Delete the message
        await message_crud.delete(async_session, id=message.id)
        deleted = await message_crud.get(async_session, message.id)
        assert deleted is None

    async def test_message_crud_by_session(self, async_session):
        """Test message retrieval by session ID."""
        session_id = "test_session_123"

        # Create multiple messages with the same session ID
        for i in range(3):
            message_data = MessageBase(
                text=f"Test message {i}",
                sender="User",
                sender_name="Test User",
                session_id=session_id,
                timestamp=datetime.now(timezone.utc),
            )
            await message_crud.create(async_session, obj_in=message_data)

        # Get messages by session ID
        messages = await message_crud.get_by_session_id(async_session, session_id)
        assert len(messages) == 3
        assert all(m.session_id == session_id for m in messages)

        # Clean up
        await message_crud.delete_by_session_id(async_session, session_id)
        remaining = await message_crud.get_by_session_id(async_session, session_id)
        assert len(remaining) == 0

    async def test_flow_crud_operations(self, async_session, logged_in_headers):
        """Test flow CRUD operations."""
        async with session_scope() as session:
            # Get a user for the flow
            users = await user_crud.get_multi(session, limit=1)
            if not users:
                # Create a test user
                user_data = UserCreate(
                    username="test_flow_user",
                    password="testpass123",
                    is_active=True,
                    is_superuser=False,
                )
                from langflow.services.database.models.user.model import User as UserTable

                user = UserTable(**user_data.model_dump(exclude={"password"}))
                user.password = "hashed_password"  # In real scenario, hash the password
                session.add(user)
                await session.commit()
                await session.refresh(user)
            else:
                user = users[0]

            # Create a flow
            flow_data = FlowCreate(
                name="Test Flow",
                description="A test flow",
                data={"nodes": [], "edges": []},
            )
            flow_dict = flow_data.model_dump()
            flow_dict["user_id"] = user.id
            flow = await flow_crud.create(session, obj_in=flow_dict)
            assert flow.name == "Test Flow"
            assert flow.id is not None

            # Get the flow
            retrieved = await flow_crud.get(session, flow.id)
            assert retrieved is not None
            assert retrieved.name == "Test Flow"

            # Get flows by user
            user_flows = await flow_crud.get_by_user_id(session, user.id)
            assert len(user_flows) >= 1
            assert any(f.id == flow.id for f in user_flows)

            # Clean up
            await flow_crud.delete(session, id=flow.id)

    async def test_user_crud_operations(self, async_session):
        """Test user CRUD operations."""
        async with session_scope() as session:
            # Create a user
            user_data = UserCreate(
                username="test_crud_user",
                password="testpass123",
                is_active=True,
                is_superuser=False,
            )
            from langflow.services.database.models.user.model import User as UserTable

            user = UserTable(**user_data.model_dump(exclude={"password"}))
            user.password = "hashed_password"  # In real scenario, hash the password
            session.add(user)
            await session.commit()
            await session.refresh(user)

            # Get user by username
            retrieved = await user_crud.get_by_username(session, "test_crud_user")
            assert retrieved is not None
            assert retrieved.username == "test_crud_user"

            # Get user by ID
            by_id = await user_crud.get(session, user.id)
            assert by_id is not None
            assert by_id.id == user.id

            # Clean up
            await session.delete(user)
            await session.commit()

    async def test_transaction_crud_by_flow(self, async_session):
        """Test transaction retrieval by flow ID."""
        async with session_scope() as session:
            # Get or create a flow for testing
            flows = await flow_crud.get_multi(session, limit=1)
            if flows:
                flow_id = flows[0].id
            else:
                # Create a test flow
                users = await user_crud.get_multi(session, limit=1)
                if users:
                    user_id = users[0].id
                else:
                    pytest.skip("No users available for testing")

                flow = await flow_crud.create(
                    session, obj_in={"name": "Test Flow", "data": {}, "user_id": user_id}
                )
                flow_id = flow.id

            # Create transactions
            for i in range(2):
                transaction_data = TransactionBase(
                    flow_id=flow_id,
                    timestamp=datetime.now(timezone.utc),
                    status="success",
                    source="test",
                    target="test",
                )
                await transaction_crud.create(session, obj_in=transaction_data)

            # Get transactions by flow ID
            transactions = await transaction_crud.get_by_flow_id(session, flow_id)
            assert len(transactions) >= 2

            # Clean up
            await transaction_crud.delete_by_flow_id(session, flow_id)

    async def test_vertex_build_crud_by_flow(self, async_session):
        """Test vertex build retrieval by flow ID."""
        async with session_scope() as session:
            # Get or create a flow for testing
            flows = await flow_crud.get_multi(session, limit=1)
            if flows:
                flow_id = flows[0].id
            else:
                # Create a test flow
                users = await user_crud.get_multi(session, limit=1)
                if users:
                    user_id = users[0].id
                else:
                    pytest.skip("No users available for testing")

                flow = await flow_crud.create(
                    session, obj_in={"name": "Test Flow", "data": {}, "user_id": user_id}
                )
                flow_id = flow.id

            # Create vertex builds
            vertex_id = str(uuid4())
            for i in range(2):
                build_data = VertexBuildBase(
                    id=vertex_id,
                    flow_id=flow_id,
                    timestamp=datetime.now(timezone.utc),
                    data={},
                    artifacts={},
                )
                await vertex_build_crud.create(session, obj_in=build_data)

            # Get vertex builds by flow ID
            builds = await vertex_build_crud.get_by_flow_id(session, flow_id)
            assert len(builds) >= 1

            # Clean up
            await vertex_build_crud.delete_by_flow_id(session, flow_id)


@pytest.mark.usefixtures("client")
async def test_crud_imports():
    """Test that all CRUD instances are properly initialized."""
    assert message_crud is not None
    assert transaction_crud is not None
    assert vertex_build_crud is not None
    assert flow_crud is not None
    assert user_crud is not None
    assert api_key_crud is not None
    assert variable_crud is not None

    # Test that they have the expected methods
    assert hasattr(message_crud, "get")
    assert hasattr(message_crud, "create")
    assert hasattr(message_crud, "update")
    assert hasattr(message_crud, "delete")
    assert hasattr(message_crud, "get_by_session_id")
    assert hasattr(message_crud, "get_by_flow_id")
