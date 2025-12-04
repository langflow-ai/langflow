#!/bin/sh
# AI Studio Frontend runtime setup script
# Based on genesis-frontend pattern
set -e

echo "INFO: Starting AI Studio Frontend with runtime environment injection"

# Generate environment variables configuration
echo "INFO: Generating runtime environment configuration..."
/usr/share/nginx/html/env.sh

# Replace base path in index.html
if [ -n "${VITE_APP_PATH}" ]; then
    echo "INFO: Replacing base path with ${VITE_APP_PATH}"
    sed -i "s|/__APP_BASE_PATH__/|${VITE_APP_PATH}|g" /usr/share/nginx/html/index.html
fi
# Validate that required environment variables are set
if [ -z "${VITE_BACKEND_URL:-}" ]; then
    echo "WARNING: VITE_BACKEND_URL not set, using default from .env.example"
fi

echo "INFO: Environment configuration complete"

# Set default values for nginx configuration
if [ -z "${FRONTEND_PORT}" ]; then
    FRONTEND_PORT="3000"
fi

if [ -z "${BACKEND_URL}" ]; then
    BACKEND_URL="${VITE_BACKEND_URL:-http://localhost:7860}"
fi

if [ -z "${LANGFLOW_MAX_FILE_SIZE_UPLOAD}" ]; then
    LANGFLOW_MAX_FILE_SIZE_UPLOAD="100"
fi

# Export variables for envsubst
export FRONTEND_PORT BACKEND_URL LANGFLOW_MAX_FILE_SIZE_UPLOAD

# Create directory for processed nginx configuration
mkdir -p /tmp/nginx

# Process nginx.conf template with environment variables
echo "INFO: Processing nginx configuration with FRONTEND_PORT=${FRONTEND_PORT}"
envsubst '${FRONTEND_PORT} ${BACKEND_URL} ${LANGFLOW_MAX_FILE_SIZE_UPLOAD}' \
    < /usr/share/nginx/html/nginx.conf.template \
    > /tmp/nginx/nginx.conf

# Create required temp directories for non-root nginx
mkdir -p /tmp/client_body /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp
mkdir -p /etc/nginx/extra-conf.d

echo "INFO: Starting nginx server for AI Studio Frontend on port ${FRONTEND_PORT}"

# Start nginx with the processed configuration
exec nginx -c /tmp/nginx/nginx.conf -g "daemon off;"