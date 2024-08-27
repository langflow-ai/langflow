# celeryconfig.py
import os

mq_user = os.environ.get("RABBITMQ_DEFAULT_USER", "langflow")
mq_password = os.environ.get("RABBITMQ_DEFAULT_PASS", "langflow")
# RabbitMQ
broker_url = os.environ.get("BROKER_URL", f"amqp://{mq_user}:{mq_password}@localhost:5672//")
result_backend = os.environ.get("RESULT_BACKEND", "redis://localhost:6379/0")
# tasks should be json or pickle
accept_content = ["json"]
