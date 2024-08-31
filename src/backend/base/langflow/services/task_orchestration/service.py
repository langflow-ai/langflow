# langflow/orchestrator/task_orchestrator.py

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import UUID

from diskcache import Cache, Deque
from loguru import logger
from pydantic import BaseModel, field_validator
from sqlmodel import select

from langflow.services.base import Service
from langflow.services.database.models.subscription.model import Subscription
from langflow.services.database.models.task.model import Task, TaskCreate, TaskRead, TaskUpdate

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService
    from langflow.services.settings.service import SettingsService


class TaskNotification(BaseModel):
    task_id: str
    flow_id: str
    event_type: str
    category: str
    state: str
    status: str

    @field_validator("task_id", "flow_id", mode="before")
    @classmethod
    def validate_str(cls, value: str) -> str:
        try:
            return str(value)
        except ValueError:
            raise ValueError(f"Invalid UUID: {value}")


class TaskOrchestrationService(Service):
    name = "task_orchestration_service"

    def __init__(
        self,
        settings_service: "SettingsService",
        db_service: "DatabaseService",
    ):
        cache_dir = Path(settings_service.settings.config_dir) / "task_orchestrator"
        self.cache = Cache(cache_dir)
        self.notification_queue = Deque(directory=f"{cache_dir}/notifications")
        self.db: DatabaseService = db_service

    def create_task(self, task_create: TaskCreate) -> TaskRead:
        task = Task.model_validate(task_create, from_attributes=True)
        with self.db.with_session() as session:
            session.add(task)
            session.commit()
            session.refresh(task)

        task_read = TaskRead.model_validate(task, from_attributes=True)
        self._notify(task_read, "task_created")
        return task_read

    def update_task(self, task_id: UUID | str, task_update: TaskUpdate) -> TaskRead:
        with self.db.with_session() as session:
            task = session.exec(select(Task).where(Task.id == task_id)).first()
            if not task:
                raise ValueError(f"Task with id {task_id} not found")

            for key, value in task_update.model_dump(exclude_unset=True).items():
                setattr(task, key, value)

                session.commit()
                session.refresh(task)

        task_read = TaskRead.model_validate(task, from_attributes=True)
        self._notify(task_read, "task_updated")
        return task_read

    def get_task(self, task_id: str) -> TaskRead:
        with self.db.with_session() as session:
            task = session.exec(select(Task).where(Task.id == task_id)).first()
            if not task:
                raise ValueError(f"Task with id {task_id} not found")
        return TaskRead.model_validate(task, from_attributes=True)

    def get_tasks_for_flow(self, flow_id: str) -> List[TaskRead]:
        with self.db.with_session() as session:
            tasks = session.exec(select(Task).where(Task.flow_id == flow_id)).all()
        return [TaskRead.model_validate(task, from_attributes=True) for task in tasks]

    def delete_task(self, task_id: str) -> None:
        with self.db.with_session() as session:
            task = session.exec(select(Task).where(Task.id == task_id)).first()
            if not task:
                raise ValueError(f"Task with id {task_id} not found")
            session.delete(task)
            session.commit()

    def _notify(self, task: TaskRead, event_type: str) -> None:
        # Notify author
        self._add_notification(task, event_type, task.author_id)

        # Notify assignee
        self._add_notification(task, event_type, task.assignee_id)

        # Notify subscribers
        with self.db.with_session() as session:
            subscriptions = session.exec(
                select(Subscription).filter(
                    ((Subscription.category == task.category) & (Subscription.state == task.state))
                    | ((Subscription.category.is_(None)) & (Subscription.state.is_(None)))
                )
            ).all()

        for subscription in subscriptions:
            self._add_notification(task, event_type, subscription.flow_id)

    def _add_notification(self, task: TaskRead, event_type: str, flow_id: str) -> None:
        notification = TaskNotification(
            task_id=task.id,
            flow_id=flow_id,
            event_type=event_type,
            category=task.category,
            state=task.state,
            status=task.status,
        )
        self.notification_queue.append(notification.model_dump())

    def get_notifications(self) -> List[TaskNotification]:
        notifications = []
        while self.notification_queue:
            notifications.append(TaskNotification(**self.notification_queue.popleft()))
        return notifications

    def subscribe_flow(
        self, flow_id: str, event_type: str, category: Optional[str] = None, state: Optional[str] = None
    ) -> None:
        subscription = Subscription(flow_id=flow_id, event_type=event_type, category=category, state=state)
        with self.db.with_session() as session:
            session.add(subscription)
            session.commit()

    def unsubscribe_flow(
        self, flow_id: str, event_type: str, category: Optional[str] = None, state: Optional[str] = None
    ) -> None:
        with self.db.with_session() as session:
            query = session.exec(
                select(Subscription).where(Subscription.flow_id == flow_id, Subscription.event_type == event_type)
            )
            if category:
                query = query.filter(Subscription.category == category)
            if state:
                query = query.filter(Subscription.state == state)
            query.delete()
            session.commit()

    def consume_task(self, task_id: str | UUID) -> None:
        task = self.get_task(str(task_id))
        if task.status != "pending":
            raise ValueError(f"Task {task_id} is not in pending status")

        # Update task status to "processing"
        self.update_task(task_id, TaskUpdate(status="processing", state=task.state))

        try:
            # Perform task processing logic here
            # For example, you might call a specific function based on the task category
            result = self._process_task(task)

            # Update task with result and set status to "completed"
            self.update_task(task_id, TaskUpdate(status="completed", state=task.state, result=result))
        except Exception as e:
            # If an error occurs, update task status to "failed"
            self.update_task(task_id, TaskUpdate(status="failed", state=task.state, result={"error": str(e)}))

    def _process_task(self, task: TaskRead) -> Dict:
        # Implement task processing logic based on task category
        # This is a placeholder implementation
        logger.info(f"Processing task {task.id}")
        return {"result": "Task processed successfully"}
