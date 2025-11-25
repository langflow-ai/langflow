import sys
import os
import time
from unittest.mock import MagicMock

# Add src/backend/base to sys.path
sys.path.append(os.path.abspath("src/backend/base"))

# Mock the service manager to prevent initialization of full backend
mock_manager = MagicMock()
sys.modules["langflow.services.manager"] = mock_manager

try:
    from langflow.services.task.service import TaskService
    from langflow.worker import test_celery
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you have installed 'celery' and 'redis'.")
    sys.exit(1)

def verify_celery_execution():
    print("--- Verifying Celery Execution ---")
    
    # Check if Celery is installed
    try:
        import celery
        print(f"Celery version: {celery.__version__}")
    except ImportError:
        print("CRITICAL: 'celery' package is not installed.")
        print("Run: uv pip install celery")
        return

    # Mock Settings
    settings_service = MagicMock()
    settings_service.settings.celery_enabled = True
    # Ensure these match your actual Redis setup if you want to test real connection
    # settings_service.settings.redis_host = "localhost" 
    # settings_service.settings.redis_port = 6379

    print("Initializing TaskService with celery_enabled=True...")
    task_service = TaskService(settings_service)

    if task_service.backend_name != "celery":
        print(f"FAILED: TaskService is using '{task_service.backend_name}' backend instead of 'celery'.")
        return

    print("TaskService initialized correctly with Celery backend.")
    
    print("\nTo fully test end-to-end execution, you need:")
    print("1. A running Redis server (localhost:6379)")
    print("2. A running Celery worker: celery -A langflow.worker worker --loglevel=info")
    print("\nIf those are running, this script could theoretically launch a task.")
    print("However, since we are mocking the service manager, we can't easily launch a real task here without more setup.")
    print("But the configuration logic is VERIFIED.")

if __name__ == "__main__":
    verify_celery_execution()
