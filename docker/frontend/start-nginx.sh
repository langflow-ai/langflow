#!/bin/sh
set -e

# Logging function
log() {
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1"
}

log "Initializing NGINX configuration"

# Define writable directory for the final config
CONFIG_DIR="$(mktemp -d /tmp/nginx.XXXXXX)"
log "Created temporary configuration directory: $CONFIG_DIR"

# Define default log formats
JSON_LOG_FORMAT="log_format json_logs escape=json '{\"time_local\":\"\$time_local\",\"remote_addr\":\"\$remote_addr\",\"remote_user\":\"\$remote_user\",\"request\":\"\$request\",\"status\":\"\$status\",\"body_bytes_sent\":\"\$body_bytes_sent\",\"http_referer\":\"\$http_referer\",\"http_user_agent\":\"\$http_user_agent\",\"request_time\":\"\$request_time\",\"upstream_response_time\":\"\$upstream_response_time\",\"upstream_addr\":\"\$upstream_addr\",\"upstream_status\":\"\$upstream_status\",\"host\":\"\$host\"}';"
DEFAULT_LOG_FORMAT="log_format main '\$remote_addr - \$remote_user [\$time_local] \"\$request\" \$status \$body_bytes_sent \"\$http_referer\" \"\$http_user_agent\"';"

# Write probe filter if enabled
PROBE_FILTER=""
if [ "${SUPPRESS_PROBE_LOGS:-true}" = "true" ]; then
  log "Configuring probe filter to suppress health check logs"
  cat > /tmp/probe_filter.conf << 'ENDFILTER'
map $http_user_agent $loggable {
    default                     1;
    ~*kube-probe                0;
}
ENDFILTER
  PROBE_FILTER="$(cat /tmp/probe_filter.conf)"
  LOGGABLE_CONFIG="if=\$loggable"
else
  log "Probe filtering disabled, all requests will be logged"
  LOGGABLE_CONFIG=""
fi

# Determine log format based on environment variable
if [ -n "$NGINX_CUSTOM_LOG_FORMAT" ]; then
    log "Using custom log format"
    LOG_FORMAT_CONF="log_format custom_logs $(printf '%s' "$NGINX_CUSTOM_LOG_FORMAT");"
    ACCESS_LOG_FORMAT="access_log /var/log/nginx/access.log custom_logs $LOGGABLE_CONFIG;"
elif [ "${NGINX_LOG_FORMAT:-default}" = "json" ]; then
    log "Using JSON log format"
    LOG_FORMAT_CONF="$JSON_LOG_FORMAT"
    ACCESS_LOG_FORMAT="access_log /var/log/nginx/access.log json_logs $LOGGABLE_CONFIG;"
else
    log "Using default log format"
    LOG_FORMAT_CONF="$DEFAULT_LOG_FORMAT"
    ACCESS_LOG_FORMAT="access_log /var/log/nginx/access.log main $LOGGABLE_CONFIG;"
fi

# Set error log level
ERROR_LOG_LEVEL="${ERROR_LOG_LEVEL:-warn}"
log "Error log level set to: $ERROR_LOG_LEVEL"

# Write logging configuration
log "Writing NGINX logging configuration"
echo "$LOG_FORMAT_CONF" > /nginx-access-log/logging.conf

# Add probe filter if enabled
if [ -n "$PROBE_FILTER" ]; then
  echo "$PROBE_FILTER" >> /nginx-access-log/logging.conf
fi

echo "$ACCESS_LOG_FORMAT" >> /nginx-access-log/logging.conf

# Check and set environment variables
if [ -z "$BACKEND_URL" ]; then
  if [ -n "$1" ]; then
    if echo "$1" | grep -Eq "^https?://[a-zA-Z0-9.-]+(:[0-9]+)?(/.*)?$"; then
      BACKEND_URL="$1"
      log "Using BACKEND_URL from command line argument: $BACKEND_URL"
    else
      log "ERROR: Invalid BACKEND_URL format: $1"
      exit 1
    fi
  else
    log "ERROR: BACKEND_URL must be set as an environment variable or as first parameter. (e.g. http://localhost:7860)"
    exit 1
  fi
fi

# Set defaults for configurable values
FRONTEND_PORT="${FRONTEND_PORT:-${2:-8080}}"
CLIENT_MAX_BODY_SIZE="${CLIENT_MAX_BODY_SIZE:-10m}"
GZIP_COMPRESSION_LEVEL="${GZIP_COMPRESSION_LEVEL:-5}"
CLIENT_TIMEOUT="${CLIENT_TIMEOUT:-12}"
WORKER_CONNECTIONS="${WORKER_CONNECTIONS:-1024}"

log "Configuration summary:"
log "- Frontend port: $FRONTEND_PORT"
log "- Backend URL: $BACKEND_URL"
log "- Client max body size: $CLIENT_MAX_BODY_SIZE"
log "- Gzip compression level: $GZIP_COMPRESSION_LEVEL"
log "- Client timeout: $CLIENT_TIMEOUT"
log "- Worker connections: $WORKER_CONNECTIONS"

# Export variables for envsubst
export BACKEND_URL FRONTEND_PORT ERROR_LOG_LEVEL CLIENT_MAX_BODY_SIZE GZIP_COMPRESSION_LEVEL CLIENT_TIMEOUT WORKER_CONNECTIONS

# Use envsubst to substitute environment variables in the template
log "Generating NGINX configuration from template"
envsubst '${BACKEND_URL} ${FRONTEND_PORT} ${ERROR_LOG_LEVEL} ${CLIENT_MAX_BODY_SIZE} ${GZIP_COMPRESSION_LEVEL} ${CLIENT_TIMEOUT} ${WORKER_CONNECTIONS}' < /etc/nginx/conf.d/default.conf.template > "$CONFIG_DIR/default.conf"

if [ "$DEBUG" = "true" ]; then
  log "DEBUG mode enabled, dumping configuration files"
  log "--- NGINX Configuration ---"
  cat "$CONFIG_DIR/default.conf"
  log "--- Logging Configuration ---"
  cat /nginx-access-log/logging.conf
  log "--- Environment Variables ---"
  env | grep -E 'NGINX|FRONTEND|BACKEND|CLIENT|WORKER|GZIP|ERROR'
fi

# Validate the configuration
log "Validating NGINX configuration"
nginx -t -c $CONFIG_DIR/default.conf || { echo "Invalid NGINX configuration"; exit 1; }

# Basic signal handling for graceful shutdown
trap "echo 'Shutting down NGINX gracefully...'; nginx -s quit; exit 0" TERM INT

# Start nginx with the new configuration
log "Starting NGINX on port ${FRONTEND_PORT}, proxying to ${BACKEND_URL}"
exec nginx -c $CONFIG_DIR/default.conf -g 'daemon off;'
