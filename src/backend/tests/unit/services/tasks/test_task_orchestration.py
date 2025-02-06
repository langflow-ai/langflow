import asyncio
import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient
from langflow.services.database.models.task.model import TaskCreate, TaskUpdate
from langflow.services.deps import get_db_service, get_event_bus_service, get_settings_service
from langflow.services.task_orchestration.service import TaskOrchestrationService


@pytest.fixture
async def task_orchestration_service(client: AsyncClient):  # noqa: ARG001
    settings_service = get_settings_service()
    db_service = get_db_service()
    event_bus_service = get_event_bus_service()
    service = TaskOrchestrationService(settings_service, db_service, event_bus_service)
    await service.start()
    yield service
    await service.stop()
    # Cleanup: Cancel all running tasks related to the event bus
    tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await event_bus_service.disconnect()


@pytest.mark.asyncio
async def test_create_task(task_orchestration_service: TaskOrchestrationService):
    flow_id = uuid.uuid4()
    create_data = TaskCreate(
        title="Test Task",
        description="A test task description",
        author_id=flow_id,
        assignee_id=flow_id,
        category="test",
        state="initial",
    )

    created_task = await task_orchestration_service.create_task(create_data)

    assert created_task.title == "Test Task"
    assert created_task.description == "A test task description"
    assert created_task.author_id == flow_id
    assert created_task.assignee_id == flow_id
    assert created_task.category == "test"
    assert created_task.state == "initial"
    assert created_task.status == "pending"
    assert isinstance(created_task.created_at, datetime)
    assert isinstance(created_task.updated_at, datetime)


@pytest.mark.asyncio
async def test_update_task(task_orchestration_service: TaskOrchestrationService):
    # First, create a task
    flow_id = uuid.uuid4()
    create_data = TaskCreate(
        title="Test Task",
        description="A test task description",
        author_id=flow_id,
        assignee_id=flow_id,
        category="test",
        state="initial",
    )
    created_task = await task_orchestration_service.create_task(create_data)

    # Now, update the task
    update_data = TaskUpdate(status="processing", title="Updated Task")
    updated_task = await task_orchestration_service.update_task(created_task.id, update_data)

    assert updated_task.status == "processing"
    assert updated_task.title == "Updated Task"
    assert updated_task.description == created_task.description
    assert updated_task.author_id == created_task.author_id
    assert updated_task.assignee_id == created_task.assignee_id
    assert updated_task.category == created_task.category
    assert updated_task.state == created_task.state
    assert isinstance(updated_task.updated_at, datetime)
    assert updated_task.updated_at > created_task.updated_at


@pytest.mark.asyncio
async def test_get_task(task_orchestration_service: TaskOrchestrationService):
    # Create a task
    flow_id = uuid.uuid4()
    create_data = TaskCreate(
        title="Test Task",
        description="A test task description",
        author_id=flow_id,
        assignee_id=flow_id,
        category="test",
        state="initial",
    )
    created_task = await task_orchestration_service.create_task(create_data)

    # Get the task
    retrieved_task = await task_orchestration_service.get_task(created_task.id)
    assert retrieved_task.id == created_task.id
    assert retrieved_task.title == created_task.title
    assert retrieved_task.description == created_task.description
    assert retrieved_task.author_id == created_task.author_id
    assert retrieved_task.assignee_id == created_task.assignee_id
    assert retrieved_task.category == created_task.category
    assert retrieved_task.state == created_task.state
    assert retrieved_task.status == created_task.status


@pytest.mark.asyncio
async def test_get_task_not_found(task_orchestration_service):
    # Attempt to get a non-existent task
    with pytest.raises(ValueError, match="Task with id .* not found"):
        await task_orchestration_service.get_task(uuid.uuid4())


@pytest.mark.asyncio
async def test_get_tasks_for_flow(task_orchestration_service: TaskOrchestrationService):
    flow_id = uuid.uuid4()
    # Create a few tasks for the flow
    create_data1 = TaskCreate(
        title="Test Task 1",
        description="A test task description 1",
        author_id=flow_id,
        assignee_id=flow_id,
        category="test",
        state="initial",
    )
    create_data2 = TaskCreate(
        title="Test Task 2",
        description="A test task description 2",
        author_id=flow_id,
        assignee_id=flow_id,
        category="test",
        state="initial",
    )

    await task_orchestration_service.create_task(create_data1)
    await task_orchestration_service.create_task(create_data2)

    tasks = await task_orchestration_service.get_tasks_for_flow(flow_id)
    assert len(tasks) == 2
    assert all(task.author_id == flow_id for task in tasks)
    assert {task.title for task in tasks} == {"Test Task 1", "Test Task 2"}


@pytest.mark.asyncio
async def test_delete_task(task_orchestration_service: TaskOrchestrationService):
    # Create a task
    flow_id = uuid.uuid4()
    create_data = TaskCreate(
        title="Test Task",
        description="A test task description",
        author_id=flow_id,
        assignee_id=flow_id,
        category="test",
        state="initial",
    )
    created_task = await task_orchestration_service.create_task(create_data)

    # Delete the task
    await task_orchestration_service.delete_task(created_task.id)

    # Verify that the task is deleted
    with pytest.raises(ValueError, match="Task with id .* not found"):
        await task_orchestration_service.get_task(created_task.id)


@pytest.mark.asyncio
async def test_delete_task_not_found(task_orchestration_service):
    # Attempt to delete a non-existent task
    with pytest.raises(ValueError, match="Task with id .* not found"):
        await task_orchestration_service.delete_task(uuid.uuid4())
