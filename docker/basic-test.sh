#!/bin/bash
set -e

# Basic smoke test for the frontend and backend

BACKEND_PORT=7860
FRONTEND_PORT=8080
BACKEND_IMAGE=langflow_backend:1.2.0
FRONTEND_IMAGE=langflow_frontend:1.2.0
NETWORK_NAME=langflow_network

# Create network
if ! docker network inspect $NETWORK_NAME > /dev/null 2>&1; then
  echo "Creating network $NETWORK_NAME"
  docker network create $NETWORK_NAME
fi

# Run Backend container
if docker ps -a --format "{{.Names}}" | grep -q "langflow-backend"; then
  echo "Stopping backend container"
  docker stop langflow-backend &> /dev/null || true
  docker rm langflow-backend &> /dev/null || true
fi

docker run -d \
--name langflow-backend \
--network $NETWORK_NAME \
-p ${BACKEND_PORT}:${BACKEND_PORT} \
--sysctl net.ipv6.conf.all.disable_ipv6=1 \
"${BACKEND_IMAGE}"

sleep 5

# Run Frontend container
if docker ps -a --format "{{.Names}}" | grep -q "langflow-frontend"; then
  echo "Stopping frontend container"
  docker stop langflow-frontend &> /dev/null || true
  docker rm langflow-frontend &> /dev/null || true
fi

docker run -d \
--name langflow-frontend \
--network $NETWORK_NAME \
-p ${FRONTEND_PORT}:${FRONTEND_PORT} \
-e BACKEND_URL="http://langflow-backend:${BACKEND_PORT}" \
-e DEBUG=true \
--sysctl net.ipv6.conf.all.disable_ipv6=1 \
"${FRONTEND_IMAGE}"
