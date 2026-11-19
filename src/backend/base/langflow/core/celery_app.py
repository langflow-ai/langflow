import time

from asgiref.sync import async_to_sync
from celery import Celery, Task
from celery.exceptions import Reject

from langflow.api.utils.migration_pause import REFUSAL, _maintenance_caller, write_refusal, writing
from langflow.services.task.maintenance import verified_task_caller


class MaintenanceTask(Task):
    """Leave paused work unacknowledged and requeue it without executing its body."""

    abstract = True
    acks_late = True

    def __call__(self, *args, **kwargs):
        caller_id = verified_task_caller(self.request.headers, self.request.id, self.name)
        with writing("task", name=self.name) as admitted:
            refusal = async_to_sync(write_refusal)(caller_id, check_file=False) if admitted else REFUSAL
            if refusal:
                # Requeue the original delivery, without consuming task retries
                # or publishing a replacement that could fail at the broker.
                time.sleep(1)
                raise Reject(refusal, requeue=True)
            token = _maintenance_caller.set(caller_id)
            try:
                # Celery's tracer already installed this delivery's request.
                # Task.__call__ would replace it and lose the id and headers.
                return self.run(*args, **kwargs)
            finally:
                _maintenance_caller.reset(token)


def make_celery(app_name: str, config: str) -> Celery:
    celery_app = Celery(app_name, task_cls=MaintenanceTask)
    celery_app.config_from_object(config)
    celery_app.conf.task_routes = {"langflow.worker.tasks.*": {"queue": "langflow"}}
    return celery_app


celery_app = make_celery("langflow", "langflow.core.celeryconfig")
