#!/bin/sh
# AI Studio Frontend runtime setup script
# Based on genesis-frontend pattern
set -e

echo "INFO: Starting AI Studio Frontend with runtime environment injection"

# Generate environment variables configuration
echo "INFO: Generating runtime environment configuration..."
/usr/share/nginx/html/env.sh

# Validate that required environment variables are set
if [ -z "${VITE_BACKEND_URL:-}" ]; then
    echo "WARNING: VITE_BACKEND_URL not set, using default from .env.example"
fi

echo "INFO: Environment configuration complete"
echo "INFO: Starting nginx server for AI Studio Frontend"

# Start nginx with the default configuration
exec nginx -g "daemon off;"