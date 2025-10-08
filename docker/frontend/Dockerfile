# AI Studio Frontend Dockerfile
# Enhanced for monorepo structure and CI/CD optimization

# Build stage
FROM node:20-alpine AS frontend_build

# Build arguments
ARG BACKEND_URL
ARG BUILD_VERSION
ARG NODE_ENV=production

# Set working directory
WORKDIR /app

# Copy package files first for better layer caching
COPY src/frontend/package.json src/frontend/package-lock.json ./

# Install dependencies
RUN npm ci --only=production --silent

# Copy configuration files
COPY src/frontend/tsconfig.json \
     src/frontend/vite.config.mts \
     src/frontend/index.html \
     src/frontend/tailwind.config.mjs \
     src/frontend/postcss.config.js \
     ./

# Copy source code
COPY src/frontend/src ./src
COPY src/frontend/public ./public

# Set environment variables for build
ENV VITE_BACKEND_URL=$BACKEND_URL \
    VITE_BUILD_VERSION=$BUILD_VERSION \
    NODE_ENV=$NODE_ENV

# Build the application
RUN npm run build

# Production stage
FROM nginx:1.25-alpine

# Copy custom nginx configuration
COPY src/frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built application from build stage
COPY --from=frontend_build /app/dist /usr/share/nginx/html

# Copy startup script
COPY src/frontend/start-nginx.sh /start-nginx.sh
RUN chmod +x /start-nginx.sh

# Set runtime environment variables
ENV BACKEND_URL=$BACKEND_URL

# Create non-root user for security
RUN addgroup -g 1001 -S aistudio && \
    adduser -S aistudio -u 1001 -G aistudio && \
    chown -R aistudio:aistudio /var/cache/nginx && \
    chown -R aistudio:aistudio /var/log/nginx && \
    chown -R aistudio:aistudio /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R aistudio:aistudio /var/run/nginx.pid && \
    chown -R aistudio:aistudio /usr/share/nginx/html

# Switch to non-root user
USER aistudio

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000 || exit 1

# Start nginx
CMD ["/start-nginx.sh"]