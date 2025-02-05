import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.core.celery_app import celery_app
from langflow.services.database.models.task.model import TaskCreate
from langflow.services.database.service import DatabaseService
from langflow.services.deps import get_db_service, get_settings_service
from langflow.services.settings.service import SettingsService
from langflow.services.task.consumer import NotificationDispatcher
from langflow.services.task_orchestration.service import TaskNotification, TaskOrchestrationService


@pytest.fixture(autouse=True)
def make_celery_tasks_eager():
    """Pytest fixture to force Celery tasks to run synchronously (eagerly).

    This prevents Celery from trying to connect to the broker during tests.
    With eager mode enabled, calling .delay() will execute the task immediately
    in the local process, and exceptions will be raised inline.
    """
    # Enable eager mode for tasks
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    yield

    # Reset to default behavior if necessary
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


# @pytest.fixture(name="session")
# async def session_fixture(tmp_path):
#     engine = create_async_engine("sqlite+aiosqlite://", connect_args={"check_same_thread": False})
#     async with engine.begin() as conn:
#         await conn.run_sync(SQLModel.metadata.create_all)

#     async_session = AsyncSession(engine)
#     yield async_session
#     await async_session.close()


@pytest.fixture
async def task_orchestration_service():
    settings_service = get_settings_service()
    db_service = get_db_service()
    task_orchestration_service = TaskOrchestrationService(settings_service, db_service)
    await task_orchestration_service.start()
    yield task_orchestration_service
    await task_orchestration_service.stop()


@pytest.mark.asyncio
async def test_create_task(task_orchestration_service):
    with patch("langflow.services.task.consumer.consume_task_celery.delay") as mock_delay:
        task_create = TaskCreate(
            title="Test Task",
            description="This is a test task",
            author_id=uuid4(),
            assignee_id=uuid4(),
            category="test",
            state="initial",
            status="pending",
        )
        task = await task_orchestration_service.create_task(task_create)
        assert task.title == "Test Task"
        assert task.status == "pending"

        mock_delay.assert_called_once_with(task.id)


@pytest.mark.asyncio
async def test_consume_task(task_orchestration_service: TaskOrchestrationService):
    task_create = TaskCreate(
        title="Test Task",
        description="This is a test task",
        author_id=uuid4(),
        assignee_id=uuid4(),
        category="test",
        state="initial",
        status="pending",
    )

    # Patch _schedule_task to prevent automatic consumption in eager mode
    with patch.object(task_orchestration_service, "_schedule_task", return_value=None):
        task = await task_orchestration_service.create_task(task_create)

    # Patch _process_task to simulate processing logic
    with patch.object(task_orchestration_service, "_process_task", return_value={"result": "Success"}):
        await task_orchestration_service.consume_task(task.id)

    updated_task = await task_orchestration_service.get_task(task.id)
    assert updated_task.status == "completed"
    assert updated_task.result == {"result": "Success"}


@pytest.mark.asyncio
async def test_notification_dispatcher():
    """Test that the notification dispatcher correctly processes notifications and triggers flow runs."""
    # Create a mock database service
    mock_db = MagicMock()
    mock_session = MagicMock()
    mock_db.with_session.return_value.__aenter__.return_value = mock_session

    # Create and configure the mock task orchestration service
    task_orchestration_service = MagicMock(spec=TaskOrchestrationService)
    task_orchestration_service.db = mock_db

    # Make exec an AsyncMock to support await
    mock_result = MagicMock()
    mock_result.first.return_value = {"some": "flow_data"}
    mock_session.exec = AsyncMock(return_value=mock_result)

    with patch(
        "langflow.services.task.consumer.get_task_orchestration_service", return_value=task_orchestration_service
    ):
        notification_dispatcher = NotificationDispatcher(poll_interval=0.01)  # Use a short poll interval for tests

        # Test Case 1: Successful notification processing
        notification = TaskNotification(
            task_id="task-id",
            flow_id="flow-id",
            event_type="task_created",
            category="test",
            state="pending",
            status="pending",
            input_request={"some": "input"},
        )

        # Set up get_notifications to return the notification only once
        notifications_responses = [[notification], [], [], [], []]
        task_orchestration_service.get_notifications.side_effect = notifications_responses

        # Patch simple_run_flow_task_celery.delay
        with patch("langflow.services.task.consumer.simple_run_flow_task_celery.delay") as mock_run_flow:
            # Run the dispatcher
            dispatcher_task = asyncio.create_task(notification_dispatcher.run())
            # Let it run for a short while
            await asyncio.sleep(0.05)
            notification_dispatcher.should_stop = True
            await dispatcher_task

            # Verify that simple_run_flow_task_celery was called with the correct arguments
            mock_run_flow.assert_called_once_with(
                flow_data={"some": "flow_data"},
                input_request={"some": "input"},
                stream=False,
            )


@pytest.mark.asyncio
async def test_internal_celery_worker_management():
    """Test that the internal Celery worker is properly managed when external_celery is False."""
    settings_service = SettingsService.initialize()
    settings_service.settings.external_celery = False

    db_service = DatabaseService(settings_service)
    service = TaskOrchestrationService(settings_service, db_service)

    # Patch asyncio.create_subprocess_exec to simulate a dummy celery worker process

    with patch("asyncio.create_subprocess_exec") as mock_create:
        dummy_proc = AsyncMock()
        dummy_proc.stdout = AsyncMock()
        dummy_proc.stderr = AsyncMock()
        dummy_proc.wait = AsyncMock(return_value=0)
        # Simulate that the process is running (returncode is None)
        dummy_proc.returncode = None
        mock_create.return_value = dummy_proc

        await service.start()

        # Before stopping, terminate should not have been called
        dummy_proc.terminate.assert_not_called()

        await service.stop()

        dummy_proc.terminate.assert_called_once()
        dummy_proc.wait.assert_called_once()


@pytest.mark.asyncio
async def test_external_celery_worker_ping():
    """Test that the service properly pings external Celery worker when external_celery is True."""
    settings_service = SettingsService.initialize()
    settings_service.settings.external_celery = True

    db_service = DatabaseService(settings_service)
    service = TaskOrchestrationService(settings_service, db_service)

    with patch("langflow.core.celery_app.celery_app.control.ping", return_value=[{"worker1": "pong"}]) as mock_ping:
        await service.start()
        mock_ping.assert_called_once_with(timeout=5.0)


@pytest.mark.asyncio
async def test_get_task(task_orchestration_service: TaskOrchestrationService):
    # Create a task using the service
    task_create = TaskCreate(
        title="Get Task Test",
        description="Test get_task",
        author_id=uuid4(),
        assignee_id=uuid4(),
        category="get_test",
        state="pending",
        status="pending",
    )
    task = await task_orchestration_service.create_task(task_create)
    fetched = await task_orchestration_service.get_task(task.id)
    assert fetched.id == task.id
    assert fetched.title == task.title

    # Test that passing an invalid id raises error
    non_existing_id = uuid4()
    with pytest.raises(ValueError, match=f"Task with id {non_existing_id} not found"):
        await task_orchestration_service.get_task(non_existing_id)


@pytest.mark.asyncio
async def test_get_tasks_for_flow(task_orchestration_service: TaskOrchestrationService):
    # Create multiple tasks with the same flow_id
    common_flow_id = uuid4()
    tasks_created = []

    # Create 3 tasks
    for i in range(3):
        task_create = TaskCreate(
            title=f"Task {i}",
            description="Test tasks for flow",
            assignee_id=uuid4(),
            category="flow_test",
            state="pending",
            status="pending",
            author_id=common_flow_id,
        )
        task = await task_orchestration_service.create_task(task_create)
        tasks_created.append(task)

    tasks_for_flow = await task_orchestration_service.get_tasks_for_flow(common_flow_id)
    assert len(tasks_for_flow) == 3
    for task in tasks_for_flow:
        assert task.author_id == common_flow_id


@pytest.mark.asyncio
async def test_delete_task(task_orchestration_service: TaskOrchestrationService):
    # Create a task, then delete it, then verify that get_task fails
    task_create = TaskCreate(
        title="Delete Task Test",
        description="Test delete_task",
        author_id=uuid4(),
        assignee_id=uuid4(),
        category="delete_test",
        state="pending",
        status="pending",
    )
    task = await task_orchestration_service.create_task(task_create)

    # Delete the task
    await task_orchestration_service.delete_task(task.id)

    # Verify that getting the deleted task raises an error
    with pytest.raises(ValueError, match=f"Task with id {task.id} not found"):
        await task_orchestration_service.get_task(task.id)


@pytest.mark.asyncio
async def test_notification_queue(task_orchestration_service: TaskOrchestrationService):
    """Test adding and retrieving notifications from the queue."""
    # Create a task that will trigger notifications
    task_create = TaskCreate(
        title="Notification Test",
        description="Test notifications",
        author_id=uuid4(),
        assignee_id=uuid4(),
        category="notify_test",
        state="pending",
        status="pending",
    )
    task = await task_orchestration_service.create_task(task_create)

    # Get notifications (should include the one from task creation)
    notifications = task_orchestration_service.get_notifications()
    assert len(notifications) > 0

    # Verify notification contents
    notification = next(n for n in notifications if n.task_id == str(task.id))
    assert notification.category == task.category
    assert notification.state == task.state
    assert notification.status == task.status


@pytest.mark.asyncio
async def test_subscribe_and_unsubscribe_flow(task_orchestration_service: TaskOrchestrationService):
    """Test that subscribing and unsubscribing a flow works correctly."""
    flow_id = uuid4()  # Create a UUID object instead of string
    event_type = "task_created"
    category = "sub_test"
    state = "pending"

    # Subscribe the flow
    await task_orchestration_service.subscribe_flow(str(flow_id), event_type, category, state)

    # Create a task that should trigger a notification for the subscribed flow
    task_create = TaskCreate(
        title="Subscription Test",
        description="Test subscriptions",
        author_id=uuid4(),
        assignee_id=uuid4(),
        category=category,
        state=state,
        status="pending",
    )
    await task_orchestration_service.create_task(task_create)

    # Get notifications and verify the subscribed flow was notified
    notifications = task_orchestration_service.get_notifications()
    assert any(n.flow_id == str(flow_id) for n in notifications)

    # Unsubscribe the flow
    await task_orchestration_service.unsubscribe_flow(str(flow_id), event_type, category, state)

    # Create another task and verify no new notifications for the unsubscribed flow
    task2 = await task_orchestration_service.create_task(task_create)
    new_notifications = task_orchestration_service.get_notifications()
    assert not any(n.flow_id == str(flow_id) and n.task_id == str(task2.id) for n in new_notifications)


@pytest.mark.asyncio
async def test_consume_task_failure(task_orchestration_service: TaskOrchestrationService):
    # Create a task that is expected to fail during processing
    task_create = TaskCreate(
        title="Failing Task",
        description="This task should simulate a failure during processing",
        author_id=uuid4(),
        assignee_id=uuid4(),
        category="fail",
        state="initial",
        status="pending",
    )

    # Prevent immediate scheduling consumption for isolation
    with patch.object(task_orchestration_service, "_schedule_task", return_value=None):
        task = await task_orchestration_service.create_task(task_create)

    # Patch _process_task to simulate a failure in processing and expect an exception due to the simulated failure
    with (
        patch.object(task_orchestration_service, "_process_task", side_effect=Exception("Simulated failure")),
        pytest.raises(Exception, match="Simulated failure"),
    ):
        await task_orchestration_service.consume_task(task.id)

    # Now retrieve the updated task and assert that its status is "failed"
    updated_task = await task_orchestration_service.get_task(task.id)
    assert updated_task.status == "failed"
    # Verify that the error message is included in the result of the task
    assert "Simulated failure" in updated_task.result.get("error", "")
