#!/bin/sh
set -e

# Default settings for Langflow
if [ -z "$LANGFLOW_HOST" ]; then
  echo "Warning: LANGFLOW_HOST is not set. Defaulting to 0.0.0.0"
  LANGFLOW_HOST="0.0.0.0"
fi

if [ -z "$LANGFLOW_PORT" ]; then
  echo "Warning: LANGFLOW_PORT is not set. Defaulting to 7860"
  LANGFLOW_PORT=7860
fi

# Set up logging environment
if [ -z "$LANGFLOW_LOG_ENV" ]; then
  echo "Setting container logging mode"
  export LANGFLOW_LOG_ENV="container_json"
fi

# Start with the base command to run the langflow backend
CMD="python -m langflow run --backend-only --port ${LANGFLOW_PORT} --host ${LANGFLOW_HOST}"

# Add any additional arguments passed to script
if [ $# -gt 0 ]; then
  CMD="$CMD $@"
fi

echo "Executing command: $CMD"

# Execute the command
exec $CMD
