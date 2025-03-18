# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

################################
# BUILDER-BASE
################################
ARG NODE_IMAGE=node:22.14-bookworm-slim
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:alpine3.21-perl

FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS builder-base

# Set the working directory
WORKDIR /frontend

# Copy package files and install dependencies
# This creates a separate layer for dependencies that won't change often
COPY src/frontend/package*.json ./
RUN npm ci --no-audit --no-fund

# Build the frontend
COPY src/frontend ./
RUN npm run build

################################
# RUNTIME
################################
FROM ${NGINX_IMAGE} AS runtime

ARG DEFAULT_FRONTEND_PORT=8080
ARG UID=10000
ARG GID=10000
ENV FRONTEND_PORT=${DEFAULT_FRONTEND_PORT} \
    DEBUG=false \
    NGINX_LOG_FORMAT=default \
    NGINX_CUSTOM_LOG_FORMAT=""

# Add metadata
LABEL org.opencontainers.image.title=langflow-frontend \
      org.opencontainers.image.authors=['Langflow'] \
      org.opencontainers.image.licenses=MIT \
      org.opencontainers.image.url=https://github.com/langflow-ai/langflow \
      org.opencontainers.image.source=https://github.com/langflow-ai/langflow

# Copy only the build artifacts from builder stage
COPY --from=builder-base --chown=nginx:nginx /frontend/build /usr/share/nginx/html

# Copy configuration files
COPY --chown=nginx:nginx ./docker/frontend/start-nginx.sh /start-nginx.sh
COPY --chown=nginx:nginx ./docker/frontend/default.conf.template /etc/nginx/conf.d/default.conf.template

# Switch to root user to create dir and set permissions
USER root

# Set execute permission
RUN chmod +x /start-nginx.sh && \
    mkdir -p /nginx-access-log && \
    chown -R ${UID}:${GID} /nginx-access-log

# Switch back to the nginx user
USER ${UID}

# Define the volume for the cache and temp directories
VOLUME [ "/tmp"]

EXPOSE ${DEFAULT_FRONTEND_PORT}
ENTRYPOINT ["/start-nginx.sh"]
