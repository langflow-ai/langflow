import asyncio
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from apscheduler.job import Job
from sqlalchemy import StaticPool, create_engine
from sqlmodel import Session, SQLModel

from langflow.services.database.models.task.model import Task, TaskCreate
from langflow.services.database.service import DatabaseService
from langflow.services.settings.service import SettingsService
from langflow.services.task.consumer import TaskConsumer
from langflow.services.task_orchestration.service import TaskNotification, TaskOrchestrationService


@pytest.fixture
def client():
    pass


@pytest.fixture(name="session")
def session_fixture(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
async def task_orchestration_service(tmp_path):
    settings_service = SettingsService.initialize()

    db_service = DatabaseService(settings_service)
    db_service.database_url = f"sqlite:///{tmp_path}/test.db"
    db_service.recreate_engine()
    SQLModel.metadata.create_all(db_service.engine)

    task_orchestration_service = TaskOrchestrationService(settings_service, db_service)
    await task_orchestration_service.start()
    yield task_orchestration_service
    await task_orchestration_service.stop()


@pytest.mark.asyncio
async def test_create_task(task_orchestration_service):
    task_create = TaskCreate(
        title="Test Task",
        description="This is a test task",
        author_id=uuid4(),
        assignee_id=uuid4(),
        category="test",
        state="initial",
        status="pending",
    )
    task = task_orchestration_service.create_task(task_create)
    assert task.title == "Test Task"
    assert task.status == "pending"

    job = task_orchestration_service.scheduler.get_job(str(task.id))
    assert isinstance(job, Job)


@pytest.mark.asyncio
async def test_consume_task(task_orchestration_service):
    task_create = TaskCreate(
        title="Test Task",
        description="This is a test task",
        author_id=uuid4(),
        assignee_id=uuid4(),
        category="test",
        state="initial",
        status="pending",
    )
    task = task_orchestration_service.create_task(task_create)

    with patch.object(task_orchestration_service, "_process_task", return_value={"result": "Success"}):
        await task_orchestration_service.consume_task(task.id)

    updated_task = task_orchestration_service.get_task(task.id)
    assert updated_task.status == "completed"
    assert updated_task.result == {"result": "Success"}


@pytest.mark.asyncio
async def test_task_consumer():
    task_orchestration_service = MagicMock(spec=TaskOrchestrationService)
    task_consumer = TaskConsumer()
    task_consumer.task_orchestration_service = task_orchestration_service

    notification = TaskNotification(
        task_id="task-id",
        flow_id="flow-id",
        event_type="task_created",
        category="test",
        state="pending",
        status="pending",
    )
    task_orchestration_service.get_notifications.return_value = [notification]
    task_orchestration_service.get_task.return_value = Task(id="task-id", title="Test Task")

    async def consume_tasks(should_stop):
        await task_consumer.run()

    task = asyncio.create_task(consume_tasks(False))
    await asyncio.sleep(0.1)
    task_consumer.should_stop = True
    await task

    task_orchestration_service.scheduler.add_job.assert_called_once_with(
        task_orchestration_service.consume_task, args=["task-id"]
    )
