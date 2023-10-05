#!/bin/sh

# Replace the placeholder with the actual value
sed -i "s|__BACKEND_URL__|$BACKEND_URL|g" /etc/nginx/conf.d/default.conf


# Start nginx
exec nginx -g 'daemon off;'
