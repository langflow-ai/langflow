# Testing Redis + Celery Setup

This guide explains how to verify that your Redis and Celery configuration is working correctly.

## Prerequisites

1.  **Install Dependencies**: You must have `celery` and `redis` installed.
    ```bash
    uv pip install celery redis
    ```

2.  **Redis Server**: Ensure you have a Redis server running.
    ```bash
    # If using Homebrew on Mac
    brew services start redis
    # Or run directly
    redis-server
    ```

## Step-by-Step Verification

### 1. Configure Environment
Enable Celery in your environment variables. You can add this to your `.env` file or export it.

```bash
export LANGFLOW_CELERY_ENABLED=true
export LANGFLOW_REDIS_HOST=localhost
export LANGFLOW_REDIS_PORT=6379
```

### 2. Start the Celery Worker
Open a new terminal tab, navigate to the backend directory, and start the worker.

```bash
cd src/backend/base
# Make sure your virtual environment is active
celery -A langflow.worker worker --loglevel=info
```
*You should see the Celery startup banner and logs indicating it is connected to Redis.*

### 3. Run the Backend
In your main terminal, start the backend.

```bash
make backend
```
*Ensure `LANGFLOW_CELERY_ENABLED=true` is set when running this.*

### 4. Verify Task Execution
To verify that tasks are actually being offloaded to Celery:
1.  Look at the **Celery Worker logs**.
2.  Trigger an action in Langflow (like building a flow).
3.  You should see tasks being received and processed in the Celery worker terminal.

## Troubleshooting

-   **ModuleNotFoundError: No module named 'celery'**: Run `uv pip install celery`.
-   **Connection Refused**: Check if Redis is running and the host/port are correct.
-   **Tasks not appearing in worker**: Ensure `LANGFLOW_CELERY_ENABLED` is actually `true`. You can check the backend logs during startup.
