# celeryconfig.py
import os

langflow_redis_host = os.environ.get("LANGFLOW_REDIS_HOST")
langflow_redis_port = os.environ.get("LANGFLOW_REDIS_PORT")
# broker default user

if langflow_redis_host and langflow_redis_port:
    broker_url = f"redis://{langflow_redis_host}:{langflow_redis_port}/0"
    result_backend = f"redis://{langflow_redis_host}:{langflow_redis_port}/0"
else:
    # RabbitMQ
    mq_user = os.environ.get("RABBITMQ_DEFAULT_USER", "langflow")
    mq_password = os.environ.get("RABBITMQ_DEFAULT_PASS", "langflow")
    broker_url = os.environ.get("BROKER_URL", f"amqp://{mq_user}:{mq_password}@localhost:5672//")
    result_backend = os.environ.get("RESULT_BACKEND", "redis://localhost:6379/0")
# tasks should be json or pickle
accept_content = ["json", "pickle"]
