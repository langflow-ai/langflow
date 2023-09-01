from asyncio import Task


class AsyncIOTaskResult:
    def __init__(self, task: Task):
        self._task = task

    @property
    def status(self) -> str:
        if self._task.done():
            return "FAILURE" if self._task.exception() is not None else "SUCCESS"
        return "PENDING"

    @property
    def result(self) -> any:
        return self._task.result() if self._task.done() else None

    def ready(self) -> bool:
        return self._task.done()


def get_celery_worker_status(app):
    i = app.control.inspect()
    availability = i.ping()
    stats = i.stats()
    registered_tasks = i.registered()
    active_tasks = i.active()
    scheduled_tasks = i.scheduled()
    return {
        "availability": availability,
        "stats": stats,
        "registered_tasks": registered_tasks,
        "active_tasks": active_tasks,
        "scheduled_tasks": scheduled_tasks,
    }
