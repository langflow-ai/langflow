#!/bin/sh
set -e
trap 'kill -TERM $PID' TERM INT
if [ -z "$BACKEND_URL" ]; then
  BACKEND_URL="$1"
fi
if [ -z "$FRONTEND_PORT" ]; then
  FRONTEND_PORT="$2"
fi
if [ -z "$FRONTEND_PORT" ]; then
  FRONTEND_PORT="80"
fi
if [ -z "$BACKEND_URL" ]; then
  echo "BACKEND_URL must be set as an environment variable or as first parameter. (e.g. http://localhost:7860)"
  exit 1
fi
echo "BACKEND_URL: $BACKEND_URL"
echo "FRONTEND_PORT: $FRONTEND_PORT"
sed -i "s|__BACKEND_URL__|$BACKEND_URL|g" /etc/nginx/conf.d/default.conf
sed -i "s|__FRONTEND_PORT__|$FRONTEND_PORT|g" /etc/nginx/conf.d/default.conf
cat /etc/nginx/conf.d/default.conf


# Start nginx
exec nginx -g 'daemon off;'
