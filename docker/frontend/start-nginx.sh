#!/bin/sh
set -e

# Define writable directory for the final config
CONFIG_DIR="/tmp/nginx"
mkdir -p $CONFIG_DIR

# Check and set environment variables
if [ -z "$BACKEND_URL" ]; then
  BACKEND_URL="$1"
fi
if [ -z "$FRONTEND_PORT" ]; then
  FRONTEND_PORT="$2"
fi
if [ -z "$FRONTEND_PORT" ]; then
  FRONTEND_PORT="80"
fi
if [ -z "$LANGFLOW_MAX_FILE_SIZE_UPLOAD" ]; then
  LANGFLOW_MAX_FILE_SIZE_UPLOAD="1"
fi
if [ -z "$LANGFLOW_PROXY_READ_TIMEOUT" ]; then
  LANGFLOW_PROXY_READ_TIMEOUT="60"
fi
if [ -z "$BACKEND_URL" ]; then
  echo "BACKEND_URL must be set as an environment variable or as first parameter. (e.g. http://localhost:7860)"
  exit 1
fi

# Export variables for envsubst
export BACKEND_URL FRONTEND_PORT LANGFLOW_MAX_FILE_SIZE_UPLOAD LANGFLOW_PROXY_READ_TIMEOUT

# Use envsubst to substitute environment variables in the template
envsubst '${BACKEND_URL} ${FRONTEND_PORT} ${LANGFLOW_MAX_FILE_SIZE_UPLOAD} ${LANGFLOW_PROXY_READ_TIMEOUT}' < /etc/nginx/conf.d/default.conf.template > $CONFIG_DIR/default.conf

# Start nginx with the new configuration
exec nginx -c $CONFIG_DIR/default.conf -g 'daemon off;'