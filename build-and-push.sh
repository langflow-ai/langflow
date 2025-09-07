#!/bin/bash

# Build and Push Langflow Docker Image to Docker Hub
# Usage: ./build-and-push.sh [your-dockerhub-username]

set -e

# Default Docker Hub username (change this to your username)
DOCKERHUB_USERNAME=${1:-"yourusername"}
IMAGE_NAME="langflow"
TAG="latest"

echo "🔨 Building Docker image..."
docker build -f Dockerfile.simple -t ${IMAGE_NAME}:${TAG} .

echo "🏷️  Tagging image for Docker Hub..."
docker tag ${IMAGE_NAME}:${TAG} ${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${TAG}

echo "🔐 Please make sure you're logged in to Docker Hub..."
echo "If not logged in, run: docker login"

echo "📤 Pushing to Docker Hub..."
docker push ${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${TAG}

echo "✅ Successfully pushed ${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${TAG}"
echo "🐳 You can now pull it with: docker pull ${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${TAG}"
