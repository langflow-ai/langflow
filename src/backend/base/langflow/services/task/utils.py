from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import contextlib

    with contextlib.suppress(ImportError):
        from celery import Celery

from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.actor.model import Actor
from langflow.services.database.models.task.model import Task, TaskCreate


def get_celery_worker_status(app: "Celery") -> dict[str, Any]:
    """Get celery worker status."""
    inspect = app.control.inspect()

    availability = inspect.ping()
    stats = inspect.stats()
    registered_tasks = inspect.registered()
    active_tasks = inspect.active()
    scheduled_tasks = inspect.scheduled()

    return {
        "availability": availability,
        "stats": stats,
        "registered_tasks": registered_tasks,
        "active_tasks": active_tasks,
        "scheduled_tasks": scheduled_tasks,
    }


async def create_task_with_actors(session: AsyncSession, task_data: TaskCreate) -> Task:
    """Create a task with either User or Flow as author/assignee.

    This function handles the creation of Actor records for the task's author and assignee,
    whether they are Users or Flows.

    Args:
        session: The database session
        task_data: The task data, which may include direct User/Flow references

    Returns:
        The created Task
    """
    # Create or get Actor for author
    author_actor_id = None
    if task_data.author_id:
        author_actor_id = task_data.author_id
    elif task_data.user_author_id:
        author_actor = await Actor.create_from_user(session, task_data.user_author_id)
        author_actor_id = author_actor.id
    elif task_data.flow_author_id:
        author_actor = await Actor.create_from_flow(session, task_data.flow_author_id)
        author_actor_id = author_actor.id

    # Create or get Actor for assignee
    assignee_actor_id = None
    if task_data.assignee_id:
        assignee_actor_id = task_data.assignee_id
    elif task_data.user_assignee_id:
        assignee_actor = await Actor.create_from_user(session, task_data.user_assignee_id)
        assignee_actor_id = assignee_actor.id
    elif task_data.flow_assignee_id:
        assignee_actor = await Actor.create_from_flow(session, task_data.flow_assignee_id)
        assignee_actor_id = assignee_actor.id

    # Create the task
    task = Task(
        title=task_data.title,
        description=task_data.description,
        attachments=task_data.attachments,
        author_id=author_actor_id,
        assignee_id=assignee_actor_id,
        category=task_data.category,
        state=task_data.state,
        status=task_data.status,
        cron_expression=task_data.cron_expression,
    )

    session.add(task)
    await session.commit()
    await session.refresh(task)

    return task


async def get_task_with_entities(session: AsyncSession, task_id: UUID) -> dict[str, Any] | None:
    """Get a task with its author and assignee entities.

    Args:
        session: The database session
        task_id: The ID of the task to retrieve

    Returns:
        A dictionary containing the task and its resolved author and assignee entities,
        or None if the task doesn't exist
    """
    # Get the task
    task = await session.get(Task, task_id)
    if not task:
        return None

    # Get the author and assignee entities
    author_entity = await task.get_author_entity(session)
    assignee_entity = await task.get_assignee_entity(session)

    # Get the entity types
    author_type = task.author.entity_type if task.author else None
    assignee_type = task.assignee.entity_type if task.assignee else None

    return {
        "task": task,
        "author_entity": author_entity,
        "author_type": author_type,
        "assignee_entity": assignee_entity,
        "assignee_type": assignee_type,
    }
