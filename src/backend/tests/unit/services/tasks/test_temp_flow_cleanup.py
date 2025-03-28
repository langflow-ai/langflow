from __future__ import annotations

import datetime
from datetime import timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.flow import Flow as FlowTable
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import get_settings_service, get_storage_service, session_scope
from langflow.services.task.temp_flow_cleanup import (
    CleanupWorker,
    cleanup_orphaned_records,
)


@pytest.mark.usefixtures("client")
async def test_cleanup_orphaned_records_no_orphans():
    """Test cleanup when there are no orphaned records."""
    storage_service = get_storage_service()
    flow_id = uuid4()

    async with session_scope() as session:
        # Create a flow and associated message
        flow = FlowTable(
            id=flow_id,
            name="Test Flow",
            data="null",
            updated_at=datetime.datetime.now(timezone.utc),
        )
        message = MessageTable(
            id=uuid4(),
            flow_id=flow_id,
            sender="test_user",
            sender_name="Test User",
            timestamp=datetime.datetime.now(timezone.utc),
            session_id=str(uuid4()),
        )
        session.add(flow)
        session.add(message)
        await session.commit()

    # Write a file for the flow
    await storage_service.save_file(str(flow_id), "test.json", b"test data")

    # Run cleanup
    async with session_scope() as session:
        await cleanup_orphaned_records()

    # Verify message still exists
    async with session_scope() as session:
        message = await session.get(MessageTable, message.id)
        assert message is not None


@pytest.mark.usefixtures("client")
async def test_cleanup_orphaned_records_with_orphans():
    """Test cleanup when there are orphaned records."""
    orphaned_flow_id = uuid4()

    async with session_scope() as session:
        # Create orphaned records without an associated flow
        message = MessageTable(
            id=uuid4(),
            flow_id=orphaned_flow_id,
            sender="test_user",
            sender_name="Test User",
            timestamp=datetime.datetime.now(timezone.utc),
            session_id=str(uuid4()),
        )
        session.add(message)
        await session.commit()

    # Run cleanup
    async with session_scope() as session:
        await cleanup_orphaned_records()

    # Verify orphaned message was deleted
    async with session_scope() as session:
        message = await session.get(MessageTable, message.id)
        assert message is None


@pytest.mark.asyncio
async def test_cleanup_worker_start_stop():
    """Test CleanupWorker start and stop functionality."""
    worker = CleanupWorker()
    await worker.start()
    assert worker._task is not None
    assert not worker._stop_event.is_set()
    await worker.stop()
    assert worker._task is None
    assert worker._stop_event.is_set()


@pytest.mark.asyncio
async def test_cleanup_worker_run_with_exception(caplog):
    """Test CleanupWorker handles exceptions gracefully."""
    settings = get_settings_service().settings
    settings.public_flow_cleanup_interval = 601  # Minimum valid interval
    worker = CleanupWorker()

    # Start worker and let it run briefly
    await worker.start()
    await worker.stop()

    # Check logs for expected messages
    assert any("Started database cleanup worker" in record.message for record in caplog.records)
    assert any("Stopping database cleanup worker" in record.message for record in caplog.records)
