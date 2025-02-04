from celery import Celery


def make_celery(app_name: str, config: str) -> Celery:
    celery_app = Celery(app_name)
    celery_app.config_from_object(config)
    celery_app.conf.task_routes = {
        "langflow.services.task.consumer.consume_task_celery": {"queue": "langflow"},
        "langflow.worker.simple_run_flow_task_celery": {"queue": "langflow"},
    }
    celery_app.conf.imports = ["langflow.services.task.consumer", "langflow.worker"]
    return celery_app


celery_app = make_celery("langflow", "langflow.core.celeryconfig")
