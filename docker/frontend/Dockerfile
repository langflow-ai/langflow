# AI Studio Frontend Dockerfile
# Enhanced for monorepo structure and CI/CD optimization

# Build stage
FROM node:22-alpine AS frontend_build

# Build arguments
ARG BUILD_VERSION
ARG NODE_ENV=production

# Set working directory
WORKDIR /app

# Copy package files first for better layer caching
COPY src/frontend/package.json src/frontend/package-lock.json ./

# Install dependencies
RUN npm ci --silent

# Copy configuration files
COPY src/frontend/tsconfig.json \
     src/frontend/vite.config.mts \
     src/frontend/index.html \
     src/frontend/tailwind.config.mjs \
     src/frontend/postcss.config.js \
     ./

# Copy runtime environment files
COPY src/frontend/.env.example ./
COPY src/frontend/env.sh ./
COPY src/frontend/setup-nginx.sh ./

# Copy source code
COPY src/frontend/src ./src
COPY src/frontend/public ./public

# Set build environment variables (only for build process)
ENV VITE_BUILD_VERSION=$BUILD_VERSION \
    NODE_ENV=$NODE_ENV

# Build the application (no runtime environment variables needed at build time)
RUN npm run build

# Copy runtime scripts to build directory
RUN cp .env.example dist/ && \
    cp env.sh dist/ && \
    cp setup-nginx.sh dist/

# Production stage
FROM nginx:1.25-alpine

# Copy custom nginx configuration
COPY src/frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built application with runtime scripts from build stage
COPY --from=frontend_build /app/dist /usr/share/nginx/html

# Create non-root user for security
RUN addgroup -g 1001 -S aistudio && \
    adduser -S aistudio -u 1001 -G aistudio

# Make runtime scripts executable and set proper ownership
RUN chmod +x /usr/share/nginx/html/env.sh && \
    chmod +x /usr/share/nginx/html/setup-nginx.sh && \
    chmod -R 755 /usr/share/nginx/html/ && \
    chown -R aistudio:aistudio /usr/share/nginx/html/

# Set up nginx permissions for non-root user
RUN chown -R aistudio:aistudio /var/cache/nginx && \
    chown -R aistudio:aistudio /var/log/nginx && \
    chown -R aistudio:aistudio /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R aistudio:aistudio /var/run/nginx.pid

# Switch to non-root user
USER aistudio

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000 || exit 1

# Start nginx with runtime environment setup
CMD ["/usr/share/nginx/html/setup-nginx.sh"]