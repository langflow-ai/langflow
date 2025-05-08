#!/bin/sh
set -e

log() {
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1"
}

# Default settings for Langflow
if [ -z "$LANGFLOW_HOST" ]; then
  log "WARNING: LANGFLOW_HOST is not set. Defaulting to 0.0.0.0"
  LANGFLOW_HOST="0.0.0.0"
fi

if [ -z "$LANGFLOW_PORT" ]; then
  log "WARNING: LANGFLOW_PORT is not set. Defaulting to 7860"
  LANGFLOW_PORT=7860
fi

# Validate port is a number
if ! echo "$LANGFLOW_PORT" | grep -q '^[0-9]\+$'; then
    log "ERROR: LANGFLOW_PORT must be a number"
    exit 1
fi

# Set up logging environment
if [ -z "$LANGFLOW_LOG_ENV" ]; then
  log "Setting container logging mode"
  export LANGFLOW_LOG_ENV="container_json"
fi

# Start with the base command to run the langflow backend
CMD="python -m langflow run --backend-only --port ${LANGFLOW_PORT} --host ${LANGFLOW_HOST}"

# Add any additional arguments passed to script
if [ $# -gt 0 ]; then
  CMD="$CMD $@"
fi

log "Executing command: $CMD"

# Execute the command
exec $CMD
