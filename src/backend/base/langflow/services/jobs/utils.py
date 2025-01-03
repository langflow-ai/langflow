from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import contextlib

    with contextlib.suppress(ImportError):
        from celery import Celery


def get_celery_worker_status(app: "Celery"):
    i = app.control.inspect()
    availability = app.control.ping()
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
