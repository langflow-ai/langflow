# celeryconfig.py
import os

broker_url = os.environ.get("BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("RESULT_BACKEND", "redis://localhost:6379/0")
# tasks should be json or pickle
accept_content = ["json", "pickle"]
