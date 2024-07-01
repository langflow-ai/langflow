# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

ARG LANGFLOW_IMAGE
FROM $LANGFLOW_IMAGE

RUN rm -rf /app/.venv/langflow/frontend
CMD ["--backend-only"]
