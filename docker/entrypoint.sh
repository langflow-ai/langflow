#!/usr/bin/env bash
set -euo pipefail

# Resolve runtime networking defaults before rendering configs.
LANGFLOW_HOST="${LANGFLOW_HOST:-0.0.0.0}"
LANGFLOW_PORT="${LANGFLOW_PORT:-7861}"
LANGFLOW_BACKEND_PORT="${LANGFLOW_BACKEND_PORT:-${LANGFLOW_PORT}}"
export LANGFLOW_HOST LANGFLOW_PORT LANGFLOW_BACKEND_PORT

# Render the nginx config with the runtime ports.
ENV_VARS='${NGINX_PORT} ${LANGFLOW_BACKEND_PORT}'
if [ -f /etc/nginx/nginx.conf.template ]; then
  envsubst "${ENV_VARS}" < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
fi

mkdir -p /var/log /var/log/supervisor /var/run/supervisor

exec supervisord -c /etc/supervisor/supervisord.conf