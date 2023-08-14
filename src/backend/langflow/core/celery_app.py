from celery import Celery


def make_celery(app_name: str):
    celery_app = Celery(app_name)
    celery_app.config_from_object("langflow.core.celeryconfig")
    celery_app.conf.task_routes = {"langflow.worker.tasks.*": {"queue": "langflow"}}
    return celery_app


celery_app = make_celery("langflow")
