# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

################################
# BUILDER-BASE
################################

# 1. force platform to the current architecture to increase build speed time on multi-platform builds
FROM --platform=$BUILDPLATFORM node:lts-bookworm-slim AS builder-base
COPY src/frontend /frontend

# PUPPETEER_SKIP_DOWNLOAD: puppeteer (via accessibility-checker, test-only)
# must not download Chrome here - the build env can't fetch it and the
# production image never runs it.
RUN cd /frontend && PUPPETEER_SKIP_DOWNLOAD=true npm install && npm run build

################################
# RUNTIME
################################
# The stale Bookworm tag lacks the OpenSSL fix for CVE-2025-15467.
FROM nginxinc/nginx-unprivileged:1.30.5-trixie@sha256:8f18dedfceea3d7feb98792810c8c9925c985890ade257f2ec1b2f492b4eaebb AS runtime

USER root
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*
USER nginx

LABEL org.opencontainers.image.title=langflow-frontend
LABEL org.opencontainers.image.authors=['Langflow']
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/langflow-ai/langflow
LABEL org.opencontainers.image.source=https://github.com/langflow-ai/langflow

COPY --from=builder-base --chown=nginx /frontend/build /usr/share/nginx/html
COPY --chown=nginx ./docker/frontend/start-nginx.sh /start-nginx.sh
COPY --chown=nginx ./docker/frontend/default.conf.template /etc/nginx/conf.d/default.conf.template
RUN chmod +x /start-nginx.sh
ENTRYPOINT ["/start-nginx.sh"]
