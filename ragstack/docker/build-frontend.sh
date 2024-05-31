#!/bin/bash
set -e
VERSION=$1
if [ -z "$VERSION" ]; then
    echo "Usage: $0 <ragstack-ai-langflow pip version>"
    exit 1
fi
RAGSTACK_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"
cd $RAGSTACK_DIR/docker/frontend
echo "Building frontend image"
docker build -t ragstack-ai-langflow-frontend:latest --build-arg RAGSTACK_AI_LANGFLOW_VERSION=$VERSION .
echo "Done ragstack-ai-langflow-frontend:latest"


