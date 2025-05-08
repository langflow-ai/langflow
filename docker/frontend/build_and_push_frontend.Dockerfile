# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

################################
# BUILDER-BASE
################################
ARG NODE_IMAGE=node:22.14-bookworm-slim
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:alpine3.21-perl
FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS builder-base

# Build arguments
ARG NODE_ENV=production
# Set environment variables
ENV NODE_ENV=${NODE_ENV} \
    NPM_CONFIG_LOGLEVEL=warn

# Set the working directory
WORKDIR /frontend

# Copy package files and install dependencies
# This creates a separate layer for dependencies that won't change often
COPY src/frontend/package*.json ./
RUN npm ci --no-audit --no-fund --production=false

# Build the frontend
COPY src/frontend ./
RUN npm run build && \
    # Optimize output size by removing unnecessary files
    find build -name "*.map" -delete

################################
# RUNTIME
################################
FROM ${NGINX_IMAGE} AS runtime

# Build arguments
ARG DEFAULT_FRONTEND_PORT=8080
ARG UID=10000
ARG GID=10000

# Set environment variables
ENV FRONTEND_PORT=${DEFAULT_FRONTEND_PORT} \
    DEBUG=false \
    NGINX_LOG_FORMAT=default \
    NGINX_CUSTOM_LOG_FORMAT="" \
    ERROR_LOG_LEVEL=warn \
    CLIENT_MAX_BODY_SIZE=10m \
    GZIP_COMPRESSION_LEVEL=5 \
    CLIENT_TIMEOUT=12 \
    WORKER_CONNECTIONS=1024 \
    SUPPRESS_PROBE_LOGS=true

# Add metadata
LABEL org.opencontainers.image.title=="Langflow Frontend" \
      org.opencontainers.image.description="Production-ready frontend service for Langflow" \
      org.opencontainers.image.authors=['Langflow Team'] \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.url="https://github.com/langflow-ai/langflow" \
      org.opencontainers.image.source="https://github.com/langflow-ai/langflow"


# Copy only the build artifacts from builder stage
COPY --from=builder-base --chown=${UID}:${GID} /frontend/build /usr/share/nginx/html

# Copy configuration files
COPY --chown=${UID}:${GID} ./docker/frontend/start-nginx.sh /start-nginx.sh
COPY --chown=${UID}:${GID} ./docker/frontend/default.conf.template /etc/nginx/conf.d/default.conf.template

# Switch to root user to create dir and set permissions
USER root

# Set execute permission
RUN chmod +x /start-nginx.sh && \
    mkdir -p /nginx-access-log && \
    chown -R ${UID}:${GID} /nginx-access-log  && \
    # Create temporary directories with proper permissions
    mkdir -p /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp && \
    chown -R ${UID}:${GID} /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp && \
    # Create extra config directory
    mkdir -p /etc/nginx/extra-conf.d && \
    chown -R ${UID}:${GID} /etc/nginx/extra-conf.d

# Switch back to the nginx user
USER ${UID}

# Define the volume for the cache and temp directories
VOLUME [ "/tmp", "/nginx-access-log" ]

# Health check - only tests Nginx server status, not the backend
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:${FRONTEND_PORT}/nginx_health || exit 1


EXPOSE ${DEFAULT_FRONTEND_PORT}
ENTRYPOINT ["/start-nginx.sh"]
