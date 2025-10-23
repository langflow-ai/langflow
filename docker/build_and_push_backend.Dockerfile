# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

ARG LANGFLOW_IMAGE=ghcr.io/langflow-ai/langflow:latest
FROM ${LANGFLOW_IMAGE}
ENV LANGFLOW_IMAGE=${LANGFLOW_IMAGE}


RUN rm -rf /app/.venv/langflow/frontend

CMD ["python", "-m", "langflow", "run", "--host", "0.0.0.0", "--port", "7860", "--backend-only"]
