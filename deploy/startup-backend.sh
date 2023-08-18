#!/bin/bash

export LANGFLOW_DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

# Your command to start the backend
exec python -m uvicorn --factory langflow.main:create_app --host 0.0.0.0 --port 7860 --log-level ${LOG_LEVEL:-info} --workers -1
