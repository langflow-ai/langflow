#!/bin/bash

export LANGFLOW_DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"


# Your command to start the backend

# If the ENVIRONMENT variable is set to "development", then start the backend in development mode
# else start the backend in production mode with guvicorn
if [ "$ENVIRONMENT" = "development" ]; then
    echo "Starting backend in development mode"
    exec python -m uvicorn --factory langflow.main:create_app --host 0.0.0.0 --port 7860 --log-level ${LOG_LEVEL:-info} --workers 2 --reload
else
    echo "Starting backend in production mode"
    exec langflow run --host 0.0.0.0 --port 7860 --log-level ${LOG_LEVEL:-info} --workers -1 --backend-only
fi

