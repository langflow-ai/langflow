#!/bin/sh

if [ -z "$BACKEND_URL" ]; then
  echo "BACKEND_URL is not set"
  exit 1
fi
sed -i "s|__BACKEND_URL__|$BACKEND_URL|g" /etc/nginx/conf.d/default.conf
cat /etc/nginx/conf.d/default.conf


# Start nginx
exec nginx -g 'daemon off;'
