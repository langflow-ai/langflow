from celery import Celery

celery_app = Celery(
    "langflow", broker="redis://queue:6379/0", backend="redis://queue:6379/0"
)
# command: celery -A langflow.worker.celery_app worker --loglevel=INFO
celery_app.conf.task_routes = {"langflow.worker.tasks.*": {"queue": "langflow"}}
