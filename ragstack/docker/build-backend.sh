#!/bin/bash
set -e
RAGSTACK_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"
cd $RAGSTACK_DIR/docker/backend
echo "Building backend image"
docker build -t ragstack-ai-langflow-backend:latest -f Dockerfile ../../..
echo "Done ragstack-ai-langflow-backend:latest "