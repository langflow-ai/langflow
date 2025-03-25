#!/bin/sh
set -e

# Define writable directory for the final config
CONFIG_DIR="$(mktemp -d /tmp/nginx.XXXXXX)"

# Define default log formats
JSON_LOG_FORMAT="log_format json_logs escape=json '{\"time_local\":\"\$time_local\",\"remote_addr\":\"\$remote_addr\",\"remote_user\":\"\$remote_user\",\"request\":\"\$request\",\"status\":\"\$status\",\"body_bytes_sent\":\"\$body_bytes_sent\",\"http_referer\":\"\$http_referer\",\"http_user_agent\":\"\$http_user_agent\",\"request_time\":\"\$request_time\",\"upstream_response_time\":\"\$upstream_response_time\",\"upstream_addr\":\"\$upstream_addr\",\"upstream_status\":\"\$upstream_status\",\"host\":\"\$host\"}';"
DEFAULT_LOG_FORMAT="log_format main '\$remote_addr - \$remote_user [\$time_local] \"\$request\" \$status \$body_bytes_sent \"\$http_referer\" \"\$http_user_agent\"';"

# Write probe filter if enabled
PROBE_FILTER=""
if [ "$SUPPRESS_PROBE_LOGS" = "true" ]; then
  PROBE_FILTER=$(cat <<'EOF'
map $http_user_agent $loggable {
    default      1;
    ~*kube-probe 0;
}
EOF
)
  LOGGABLE_CONFIG="if=\$loggable"
else
  LOGGABLE_CONFIG=""
fi

# Determine log format based on environment variable
if [ -n "$NGINX_CUSTOM_LOG_FORMAT" ]; then
    LOG_FORMAT_CONF="log_format custom_logs $(printf '%s' "$NGINX_CUSTOM_LOG_FORMAT");"
    ACCESS_LOG_FORMAT="access_log /var/log/nginx/access.log custom_logs $LOGGABLE_CONFIG;"
elif [ "$NGINX_LOG_FORMAT" = "json" ]; then
    LOG_FORMAT_CONF="$JSON_LOG_FORMAT"
    ACCESS_LOG_FORMAT="access_log /var/log/nginx/access.log json_logs $LOGGABLE_CONFIG;"
else
    LOG_FORMAT_CONF="$DEFAULT_LOG_FORMAT"
    ACCESS_LOG_FORMAT="access_log /var/log/nginx/access.log main $LOGGABLE_CONFIG;"
fi

if [ -z "$ERROR_LOG_LEVEL" ]; then
  ERROR_LOG_LEVEL="warn"
fi

# Write logging configuration
echo "$LOG_FORMAT_CONF" > /nginx-access-log/logging.conf

# Add probe filter if enabled
if [ -n "$PROBE_FILTER" ]; then
  echo "$PROBE_FILTER" >> /nginx-access-log/logging.conf
fi

echo "$ACCESS_LOG_FORMAT" >> /nginx-access-log/logging.conf

# Check and set environment variables
if [ -z "$BACKEND_URL" ]; then
  if echo "$1" | grep -Eq "^https?://[a-zA-Z0-9.-]+(:[0-9]+)?(/.*)?$"; then
    BACKEND_URL="$1"
  else
    echo "ERROR: Invalid BACKEND_URL format: $1"
    exit 1
  fi
fi
if [ -z "$FRONTEND_PORT" ]; then
  FRONTEND_PORT="$2"
fi

if [ -z "$BACKEND_URL" ]; then
  echo "ERROR: BACKEND_URL must be set as an environment variable or as first parameter. (e.g. http://localhost:7860)"
  exit 1
fi
# Export variables for envsubst
export BACKEND_URL FRONTEND_PORT LOG_FORMAT ERROR_LOG_LEVEL

# Use envsubst to substitute environment variables in the template
envsubst '${BACKEND_URL} ${FRONTEND_PORT} ${LOG_FORMAT} ${ERROR_LOG_LEVEL}' < /etc/nginx/conf.d/default.conf.template > $CONFIG_DIR/default.conf

if [ "$DEBUG" = "true" ]; then
  echo "NGINX Configuration:"
  cat $CONFIG_DIR/default.conf
  echo "Logging Configuration:"
  cat /nginx-access-log/logging.conf
fi

# Validate the configuration
nginx -t -c $CONFIG_DIR/default.conf || { echo "Invalid NGINX configuration"; exit 1; }

# Basic signal handling for graceful shutdown
trap "echo 'Shutting down NGINX gracefully...'; nginx -s quit; exit 0" TERM INT

# Start nginx with the new configuration
exec nginx -c $CONFIG_DIR/default.conf -g 'daemon off;'
