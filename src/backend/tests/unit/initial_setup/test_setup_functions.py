import asyncio
import json
from uuid import uuid4

import pytest
from langflow.initial_setup.setup import (
    find_existing_flow,
    get_or_create_default_folder,
    session_scope,
    upsert_flow_from_file,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import FolderRead
from sqlmodel import select


@pytest.mark.usefixtures("client")
async def test_get_or_create_default_folder_creation() -> None:
    """Test that a default project is created for a new user.

    This test verifies that when no default project exists for a given user,
    get_or_create_default_folder creates one with the expected name and assigns it an ID.
    """
    test_user_id = uuid4()
    async with session_scope() as session:
        folder = await get_or_create_default_folder(session, test_user_id)
        assert folder.name == DEFAULT_FOLDER_NAME, "The project name should match the default."
        assert hasattr(folder, "id"), "The project should have an 'id' attribute after creation."


@pytest.mark.usefixtures("client")
async def test_get_or_create_default_folder_idempotency() -> None:
    """Test that subsequent calls to get_or_create_default_folder return the same project.

    The function should be idempotent such that if a default project already exists,
    calling the function again does not create a new one.
    """
    test_user_id = uuid4()
    async with session_scope() as session:
        folder_first = await get_or_create_default_folder(session, test_user_id)
        folder_second = await get_or_create_default_folder(session, test_user_id)
        assert folder_first.id == folder_second.id, "Both calls should return the same folder instance."


@pytest.mark.usefixtures("client")
async def test_get_or_create_default_folder_concurrent_calls() -> None:
    """Test concurrent invocations of get_or_create_default_folder.

    This test ensures that when multiple concurrent calls are made for the same user,
    only one default project is created, demonstrating idempotency under concurrent access.
    """
    test_user_id = uuid4()

    async def get_folder() -> FolderRead:
        async with session_scope() as session:
            return await get_or_create_default_folder(session, test_user_id)

    results = await asyncio.gather(get_folder(), get_folder(), get_folder())
    folder_ids = {folder.id for folder in results}
    assert len(folder_ids) == 1, "Concurrent calls must return a single, consistent folder instance."


# ==================== find_existing_flow Tests ====================


@pytest.mark.usefixtures("client")
async def test_find_existing_flow_by_id() -> None:
    """Test that find_existing_flow finds a flow by its ID."""
    test_user_id = uuid4()
    flow_id = uuid4()

    async with session_scope() as session:
        folder = await get_or_create_default_folder(session, test_user_id)
        flow = Flow(
            id=flow_id,
            name="Test Flow",
            user_id=test_user_id,
            folder_id=folder.id,
            data={},
        )
        session.add(flow)
        await session.flush()

        found = await find_existing_flow(session, flow_id, None)
        assert found is not None, "Should find flow by ID"
        assert found.id == flow_id


@pytest.mark.usefixtures("client")
async def test_find_existing_flow_by_endpoint_name() -> None:
    """Test that find_existing_flow finds a flow by its endpoint name."""
    test_user_id = uuid4()
    flow_id = uuid4()
    endpoint_name = f"test-endpoint-{uuid4()}"

    async with session_scope() as session:
        folder = await get_or_create_default_folder(session, test_user_id)
        flow = Flow(
            id=flow_id,
            name="Test Flow",
            endpoint_name=endpoint_name,
            user_id=test_user_id,
            folder_id=folder.id,
            data={},
        )
        session.add(flow)
        await session.flush()

        found = await find_existing_flow(session, None, endpoint_name)
        assert found is not None, "Should find flow by endpoint name"
        assert found.endpoint_name == endpoint_name


@pytest.mark.usefixtures("client")
async def test_find_existing_flow_by_user_id_and_name() -> None:
    """Test that find_existing_flow finds a flow by (user_id, name) combination.

    This matches the unique_flow_name database constraint.
    """
    test_user_id = uuid4()
    flow_id = uuid4()
    flow_name = f"Unique Flow Name {uuid4()}"

    async with session_scope() as session:
        folder = await get_or_create_default_folder(session, test_user_id)
        flow = Flow(
            id=flow_id,
            name=flow_name,
            user_id=test_user_id,
            folder_id=folder.id,
            data={},
        )
        session.add(flow)
        await session.flush()

        # Search by user_id and name (not by id or endpoint_name)
        found = await find_existing_flow(
            session, flow_id=None, flow_endpoint_name=None, user_id=test_user_id, flow_name=flow_name
        )
        assert found is not None, "Should find flow by (user_id, name) combination"
        assert found.name == flow_name
        assert found.user_id == test_user_id


@pytest.mark.usefixtures("client")
async def test_find_existing_flow_returns_none_when_not_found() -> None:
    """Test that find_existing_flow returns None when no matching flow exists."""
    async with session_scope() as session:
        found = await find_existing_flow(
            session, flow_id=uuid4(), flow_endpoint_name="nonexistent-endpoint", user_id=uuid4(), flow_name="Nonexistent"
        )
        assert found is None, "Should return None when flow does not exist"


# ==================== upsert_flow_from_file Tests ====================


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_creates_new_flow() -> None:
    """Test that upsert_flow_from_file creates a new flow when it doesn't exist."""
    test_user_id = uuid4()
    flow_id = uuid4()
    flow_name = f"New Test Flow {uuid4()}"

    flow_content = json.dumps({
        "id": str(flow_id),
        "name": flow_name,
        "description": "A test flow",
        "data": {"nodes": [], "edges": []},
    })

    async with session_scope() as session:
        await get_or_create_default_folder(session, test_user_id)
        await upsert_flow_from_file(flow_content, str(flow_id), session, test_user_id)

        # Verify the flow was created
        stmt = select(Flow).where(Flow.id == flow_id)
        flow = (await session.exec(stmt)).first()
        assert flow is not None, "Flow should be created"
        assert flow.name == flow_name
        assert flow.user_id == test_user_id


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_updates_existing_flow_by_id() -> None:
    """Test that upsert_flow_from_file updates an existing flow when found by ID."""
    test_user_id = uuid4()
    flow_id = uuid4()

    async with session_scope() as session:
        folder = await get_or_create_default_folder(session, test_user_id)
        # Create initial flow
        initial_flow = Flow(
            id=flow_id,
            name="Initial Name",
            description="Initial description",
            user_id=test_user_id,
            folder_id=folder.id,
            data={},
        )
        session.add(initial_flow)
        await session.flush()

    # Update via upsert
    updated_content = json.dumps({
        "id": str(flow_id),
        "name": "Updated Name",
        "description": "Updated description",
        "data": {"nodes": [{"id": "node1"}], "edges": []},
    })

    async with session_scope() as session:
        await upsert_flow_from_file(updated_content, str(flow_id), session, test_user_id)

        stmt = select(Flow).where(Flow.id == flow_id)
        flow = (await session.exec(stmt)).first()
        assert flow is not None
        assert flow.name == "Updated Name", "Flow name should be updated"
        assert flow.description == "Updated description", "Flow description should be updated"


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_updates_existing_flow_by_name() -> None:
    """Test that upsert_flow_from_file finds and updates a flow by (user_id, name).

    This tests the fix for the K8s race condition where flows are matched
    by the unique_flow_name constraint.
    """
    test_user_id = uuid4()
    original_flow_id = uuid4()
    new_flow_id = uuid4()
    flow_name = f"Same Name Flow {uuid4()}"

    async with session_scope() as session:
        folder = await get_or_create_default_folder(session, test_user_id)
        # Create initial flow
        initial_flow = Flow(
            id=original_flow_id,
            name=flow_name,
            description="Initial description",
            user_id=test_user_id,
            folder_id=folder.id,
            data={},
        )
        session.add(initial_flow)
        await session.flush()

    # Try to upsert with a different ID but same name and user_id
    # This should find the existing flow by (user_id, name) and update it
    updated_content = json.dumps({
        "id": str(new_flow_id),
        "name": flow_name,
        "description": "Updated via name match",
        "data": {"nodes": [], "edges": []},
    })

    async with session_scope() as session:
        await upsert_flow_from_file(updated_content, str(new_flow_id), session, test_user_id)

        # The original flow should be updated (not a new one created)
        stmt = select(Flow).where(Flow.name == flow_name, Flow.user_id == test_user_id)
        flows = (await session.exec(stmt)).all()
        assert len(flows) == 1, "Should only have one flow with this name for this user"
        assert flows[0].description == "Updated via name match"


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_concurrent_calls() -> None:
    """Test that concurrent upsert_flow_from_file calls handle race conditions.

    This simulates the K8s scenario where multiple pods try to insert the same flow.
    """
    test_user_id = uuid4()
    flow_name = f"Concurrent Test Flow {uuid4()}"

    async def upsert_flow(flow_id: str) -> None:
        flow_content = json.dumps({
            "id": flow_id,
            "name": flow_name,
            "description": f"Created by {flow_id}",
            "data": {"nodes": [], "edges": []},
        })
        async with session_scope() as session:
            await get_or_create_default_folder(session, test_user_id)
            await upsert_flow_from_file(flow_content, flow_id, session, test_user_id)

    # Run multiple concurrent upserts with different IDs but the same name
    flow_ids = [str(uuid4()) for _ in range(3)]
    await asyncio.gather(*[upsert_flow(fid) for fid in flow_ids])

    # Verify only one flow exists for this (user_id, name) combination
    async with session_scope() as session:
        stmt = select(Flow).where(Flow.name == flow_name, Flow.user_id == test_user_id)
        flows = (await session.exec(stmt)).all()
        assert len(flows) == 1, f"Should have exactly 1 flow, got {len(flows)}"
