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
if [ -z "$NGINX_PROXY_READ_TIMEOUT" ]; then
  NGINX_PROXY_READ_TIMEOUT="60"
else
  NGINX_PROXY_READ_TIMEOUT="${NGINX_PROXY_READ_TIMEOUT%s}"
  original_input="$NGINX_PROXY_READ_TIMEOUT"
  case "$NGINX_PROXY_READ_TIMEOUT" in
    ''|*[!0-9]*)
      echo "[ERROR] NGINX_PROXY_READ_TIMEOUT: invalid format" >&2
      echo "  Expected: integer number of seconds (e.g., 60 or 60s)" >&2
      echo "  Received: '$original_input'" >&2
      exit 1
      ;;
  esac
  if [ "$NGINX_PROXY_READ_TIMEOUT" -lt 1 ]; then
    echo "[ERROR] NGINX_PROXY_READ_TIMEOUT: value too small" >&2
    echo "  Expected: integer >= 1 (timeout cannot be disabled)" >&2
    echo "  Received: $NGINX_PROXY_READ_TIMEOUT" >&2
    exit 1
  fi
fi
if [ -z "$BACKEND_URL" ]; then
  echo "BACKEND_URL must be set as an environment variable or as first parameter. (e.g. http://localhost:7860)"
  exit 1
fi

# Export variables for envsubst
export BACKEND_URL FRONTEND_PORT LANGFLOW_MAX_FILE_SIZE_UPLOAD NGINX_PROXY_READ_TIMEOUT

# Use envsubst to substitute environment variables in the template
envsubst '${BACKEND_URL} ${FRONTEND_PORT} ${LANGFLOW_MAX_FILE_SIZE_UPLOAD} ${NGINX_PROXY_READ_TIMEOUT}' < /etc/nginx/conf.d/default.conf.template > $CONFIG_DIR/default.conf

# Start nginx with the new configuration
exec nginx -c $CONFIG_DIR/default.conf -g 'daemon off;'
