# celeryconfig.py
import os

langflow_redis_host = os.environ.get("LANGFLOW_REDIS_HOST")
langflow_redis_port = os.environ.get("LANGFLOW_REDIS_PORT")
# Match the Pydantic Settings default (redis_db: int = 0) so that the Celery
# worker and the main application operate on the same Redis database when the
# user overrides LANGFLOW_REDIS_DB.
langflow_redis_db = os.environ.get("LANGFLOW_REDIS_DB", "0")
# broker default user

if langflow_redis_host and langflow_redis_port:
    broker_url = f"redis://{langflow_redis_host}:{langflow_redis_port}/{langflow_redis_db}"
    result_backend = f"redis://{langflow_redis_host}:{langflow_redis_port}/{langflow_redis_db}"
else:
    # RabbitMQ
    mq_user = os.environ.get("RABBITMQ_DEFAULT_USER", "langflow")
    mq_password = os.environ.get("RABBITMQ_DEFAULT_PASS", "langflow")
    broker_url = os.environ.get("BROKER_URL", f"amqp://{mq_user}:{mq_password}@localhost:5672//")
    result_backend = os.environ.get("RESULT_BACKEND", "redis://localhost:6379/0")
# tasks should be json or pickle
accept_content = ["json", "pickle"]
