"""Security tests for flow access control and cross-account protection.

These tests validate that the token scope security fixes prevent
unauthorized access to flows between different user accounts.
"""

import uuid

import pytest
from fastapi import HTTPException
from langflow.api.security import (
    get_flow_with_ownership,
    get_flow_with_ownership_by_name_or_id,
    get_public_flow_by_name_or_id,
)
from langflow.services.database.models.flow.model import AccessTypeEnum, Flow
from langflow.services.database.models.user.model import User


class TestFlowAccessSecurity:
    """Test suite for flow access security."""

    @pytest.mark.asyncio
    async def test_get_flow_with_ownership_valid_owner(self, session, created_user, created_flow):
        """Test that flow owner can access their own flow."""
        flow = await get_flow_with_ownership(session, created_flow.id, created_user.id)
        assert flow.id == created_flow.id
        assert flow.user_id == created_user.id

    @pytest.mark.asyncio
    async def test_get_flow_with_ownership_invalid_owner(self, session, created_flow):
        """Test that non-owner cannot access flow."""
        # Create another user
        other_user = User(username="other_user", email="other@test.com")
        session.add(other_user)
        await session.commit()
        await session.refresh(other_user)

        # Try to access flow as different user
        with pytest.raises(HTTPException) as exc_info:
            await get_flow_with_ownership(session, created_flow.id, other_user.id)
        assert exc_info.value.status_code == 404
        assert "Flow not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_flow_with_ownership_nonexistent_flow(self, session, created_user):
        """Test that nonexistent flow raises 404."""
        fake_flow_id = uuid.uuid4()
        with pytest.raises(HTTPException) as exc_info:
            await get_flow_with_ownership(session, fake_flow_id, created_user.id)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_flow_by_name_or_id_with_uuid(self, session, created_user, created_flow):
        """Test access by UUID with ownership validation."""
        flow = await get_flow_with_ownership_by_name_or_id(session, str(created_flow.id), created_user.id)
        assert flow.id == created_flow.id

    @pytest.mark.asyncio
    async def test_get_flow_by_name_or_id_with_endpoint_name(self, session, created_user, created_flow):
        """Test access by endpoint name with ownership validation."""
        # Set endpoint name
        created_flow.endpoint_name = "test_endpoint"
        session.add(created_flow)
        await session.commit()

        flow = await get_flow_with_ownership_by_name_or_id(session, "test_endpoint", created_user.id)
        assert flow.id == created_flow.id

    @pytest.mark.asyncio
    async def test_get_flow_by_endpoint_name_cross_account_blocked(self, session, created_flow):
        """Test that cross-account access by endpoint name is blocked."""
        # Create another user
        other_user = User(username="other_user", email="other@test.com")
        session.add(other_user)
        await session.commit()
        await session.refresh(other_user)

        # Set endpoint name
        created_flow.endpoint_name = "test_endpoint"
        session.add(created_flow)
        await session.commit()

        # Try to access by endpoint name as different user
        with pytest.raises(HTTPException) as exc_info:
            await get_flow_with_ownership_by_name_or_id(session, "test_endpoint", other_user.id)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_public_flow_access_by_any_user(self, session, created_flow):
        """Test that public flows can be accessed by any user."""
        # Create another user
        other_user = User(username="other_user", email="other@test.com")
        session.add(other_user)
        await session.commit()
        await session.refresh(other_user)

        # Make flow public
        created_flow.access_type = AccessTypeEnum.PUBLIC
        created_flow.endpoint_name = "public_endpoint"
        session.add(created_flow)
        await session.commit()

        # Access public flow by UUID
        flow = await get_public_flow_by_name_or_id(session, str(created_flow.id))
        assert flow.id == created_flow.id

        # Access public flow by endpoint name
        flow = await get_public_flow_by_name_or_id(session, "public_endpoint")
        assert flow.id == created_flow.id

    @pytest.mark.asyncio
    async def test_private_flow_not_accessible_as_public(self, session, created_flow):
        """Test that private flows cannot be accessed via public flow function."""
        # Ensure flow is private
        created_flow.access_type = AccessTypeEnum.PRIVATE
        created_flow.endpoint_name = "private_endpoint"
        session.add(created_flow)
        await session.commit()

        # Try to access private flow as public
        with pytest.raises(HTTPException) as exc_info:
            await get_public_flow_by_name_or_id(session, str(created_flow.id))
        assert exc_info.value.status_code == 404

        with pytest.raises(HTTPException) as exc_info:
            await get_public_flow_by_name_or_id(session, "private_endpoint")
        assert exc_info.value.status_code == 404


# Fixtures for testing
@pytest.fixture
async def created_user(session):
    """Create a test user."""
    user = User(username="test_user", email="test@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def created_flow(session, created_user):
    """Create a test flow owned by test user."""
    flow = Flow(
        name="Test Flow",
        user_id=created_user.id,
        data={"nodes": [], "edges": []},
        access_type=AccessTypeEnum.PRIVATE,
    )
    session.add(flow)
    await session.commit()
    await session.refresh(flow)
    return flow


@pytest.fixture
async def session():
    """Database session fixture."""
    # This would be provided by your existing test setup
    # The actual implementation depends on your test configuration


@pytest.fixture
async def client():
    """HTTP client fixture."""
    # This would be provided by your existing test setup
    # The actual implementation depends on your test configuration
