#!/bin/bash

# Genesis Studio AI Service - Properly configured startup script
# This script ensures all environment variables are loaded before starting Langflow

echo "🚀 Starting Genesis Studio AI Service..."
echo "📂 Working directory: $(pwd)"

# Load environment variables from .env file
echo "🔧 Loading environment variables..."
set -a
source .env
set +a

# Verify key variables are loaded
echo "✅ Environment variables loaded:"
echo "   MODELHUB_URI: ${MODELHUB_URI}"
echo "   MODELHUB_CLLM_MODEL: ${MODELHUB_CLLM_MODEL}"

# Start Langflow with proper configuration
echo "🎯 Starting Langflow server..."
uv run langflow run --port 7860 --host 0.0.0.0 --backend-only