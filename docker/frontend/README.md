# Langflow Frontend Docker Configuration

This directory contains the files necessary to build a production-ready Docker image for the Langflow frontend application. The Docker configuration uses a multi-stage build process for optimal image size and security.

## Files Overview

### 1. `build_and_push_frontend.Dockerfile`

This is the main Dockerfile that defines the multi-stage build process for creating the frontend Docker image.

#### Key Features:

- **Multi-stage build** - Uses a build stage for compiling the React application and a runtime stage for serving it through NGINX
- **Optimized for size** - Removes unnecessary files like source maps in the final build
- **Security focused** - Uses NGINX Unprivileged image for improved security
- **Configurable** - Multiple build arguments and environment variables for customization
- **Health check** - Built-in health check for container orchestration systems

#### Build Stages:

1. **Builder Stage (builder-base)**:
   - Based on Node.js image (currently node:22.14-bookworm-slim)
   - Installs dependencies using npm
   - Builds the React application
   - Optimizes the build output

2. **Runtime Stage (runtime)**:
   - Based on NGINX Unprivileged Alpine image
   - Copies only the built artifacts from the builder stage
   - Sets up configuration templates and startup scripts
   - Configures proper permissions and security settings

#### Detailed Dockerfile Explanation

```dockerfile
# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit
```

This line enables Docker BuildKit features for better caching and performance.

```dockerfile
################################
# BUILDER-BASE
################################
ARG NODE_IMAGE=node:22.14-bookworm-slim
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:alpine3.21-perl
FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS builder-base
```

- Defines build arguments for the Node.js and NGINX images
- The `--platform=$BUILDPLATFORM` ensures the build stage runs on the architecture of the build host (not the target), which optimizes performance for multi-architecture builds
- The `AS builder-base` names this stage for reference in later stages

```dockerfile
# Build arguments
ARG NODE_ENV=production
# Set environment variables
ENV NODE_ENV=${NODE_ENV} \
    NPM_CONFIG_LOGLEVEL=warn
```
- Sets up build arguments and environment variables
- NODE_ENV affects React build optimizations
- NPM_CONFIG_LOGLEVEL reduces npm output verbosity

```dockerfile
# Set the working directory
WORKDIR /frontend

# Copy package files and install dependencies
# This creates a separate layer for dependencies that won't change often
COPY src/frontend/package*.json ./
RUN npm ci --no-audit --no-fund --production=false
```
- Creates a dedicated layer for npm dependencies
- Uses `npm ci` for clean, reproducible dependency installation
- Skips audits and funding messages for faster builds
- `--production=false` ensures dev dependencies are installed (needed for build)

```dockerfile
# Build the frontend
COPY src/frontend ./
RUN npm run build && \
    # Optimize output size by removing unnecessary files
    find build -name "*.map" -delete
```
- Copies the frontend source code
- Runs the build process
- Removes source maps to reduce final image size

```dockerfile
################################
# RUNTIME
################################
FROM ${NGINX_IMAGE} AS runtime
```
- Starts the runtime stage, using the NGINX image defined earlier

```dockerfile
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
```
- Defines default configuration values for the runtime container
- These environment variables are used by the startup script

```dockerfile
# Add metadata
LABEL org.opencontainers.image.title=="Langflow Frontend" \
      org.opencontainers.image.description="Production-ready frontend service for Langflow" \
      org.opencontainers.image.authors=['Langflow Team'] \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.url="https://github.com/langflow-ai/langflow" \
      org.opencontainers.image.source="https://github.com/langflow-ai/langflow"
```
- Adds metadata to the image following OCI (Open Container Initiative) format
- Provides image description, author information, licensing, and source URLs

```dockerfile
# Copy only the build artifacts from builder stage
COPY --from=builder-base --chown=nginx:nginx /frontend/build /usr/share/nginx/html
```
- Copies only the built files from the builder stage
- Uses the `--chown` flag to set proper ownership of files
- This is a key part of the multi-stage build process that reduces image size

```dockerfile
# Copy configuration files
COPY --chown=nginx:nginx ./docker/frontend/start-nginx.sh /start-nginx.sh
COPY --chown=nginx:nginx ./docker/frontend/default.conf.template /etc/nginx/conf.d/default.conf.template
```
- Copies the NGINX configuration template and startup script
- Sets proper ownership for security

```dockerfile
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
```

- Temporarily switches to root user to set up directories and permissions
- Creates necessary directories for NGINX operation
- Sets proper ownership for all directories

```dockerfile
# Switch back to the nginx user
USER ${UID}
```

- Switches back to the non-privileged user for security

```dockerfile
# Define the volume for the cache and temp directories
VOLUME [ "/tmp", "/nginx-access-log" ]
```

- Defines Docker volumes for persistent data and logs

```dockerfile
# Health check - only tests Nginx server status, not the backend
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:${FRONTEND_PORT}/nginx_health || exit 1
```

- Configures a container health check
- Tests the NGINX server status endpoint every 30 seconds
- Allows 10 seconds for initial startup before health checks begin

```dockerfile
EXPOSE ${DEFAULT_FRONTEND_PORT}
ENTRYPOINT ["/start-nginx.sh"]
```

- Exposes the frontend port
- Sets the startup script as the container entrypoint

### 2. `default.conf.template`

This is the NGINX configuration template that is used to generate the final NGINX configuration during container startup.

#### Key Features:

- **Environment variable substitution** - Uses environment variables to customize NGINX configuration
- **Security enhancements** - Sets appropriate security headers and access restrictions
- **Performance optimizations** - Includes caching, compression, and performance settings
- **API proxy** - Configures proxy settings for backend API requests
- **Health check endpoints** - Provides health check endpoints for monitoring
- **Cache control** - Optimized caching strategy for different types of assets
- **Error handling** - Custom error pages and error interceptors

#### Detailed Template Explanation

The NGINX configuration template has several important sections:

1. **Main Configuration**:
   ```nginx
   worker_processes auto;
   pid /tmp/nginx.pid;

   events {
       worker_connections ${WORKER_CONNECTIONS};
       multi_accept on;
   }
   ```
   - Sets NGINX to automatically determine the number of worker processes
   - Uses a non-standard PID file location for unprivileged operation
   - Configures event handling with dynamic worker connections

2. **HTTP Configuration**:
   ```nginx
   http {
       include /etc/nginx/mime.types;
       default_type application/octet-stream;
       charset utf-8;

       # Temp paths for unprivileged user
       client_body_temp_path /tmp/client_temp;
       proxy_temp_path       /tmp/proxy_temp;
       fastcgi_temp_path     /tmp/fastcgi_temp;
       uwsgi_temp_path       /tmp/uwsgi_temp;
       scgi_temp_path        /tmp/scgi_temp;
   ```
   - Includes MIME types and sets character encoding
   - Configures temporary paths for the unprivileged user context

3. **Performance Settings**:
   ```nginx
   # Optimize sendfile
   sendfile on;
   tcp_nopush on;
   tcp_nodelay on;

   # Timeouts
   keepalive_timeout 65;
   client_body_timeout ${CLIENT_TIMEOUT};
   client_header_timeout ${CLIENT_TIMEOUT};
   send_timeout 10;
   client_max_body_size ${CLIENT_MAX_BODY_SIZE};

   # Caching settings
   open_file_cache max=1000 inactive=20s;
   open_file_cache_valid 30s;
   open_file_cache_min_uses 2;
   open_file_cache_errors on;
   ```
   - Enables sendfile for efficient file transfers
   - Configures various timeout settings with parameterized values
   - Sets up file caching for better performance

4. **Compression Settings**:
   ```nginx
   # Compression settings
   gzip on;
   gzip_comp_level ${GZIP_COMPRESSION_LEVEL};
   gzip_min_length 256;
   gzip_proxied any;
   gzip_vary on;
   gzip_disable "msie6";
   gzip_types
       application/atom+xml
       application/javascript
       ...
   ```
   - Enables GZIP compression with configurable level
   - Specifies minimum file size for compression
   - Lists all file types that should be compressed

5. **Security Headers**:
   ```nginx
   # Security headers
   add_header X-Content-Type-Options nosniff;
   add_header X-XSS-Protection "1; mode=block";
   add_header X-Frame-Options SAMEORIGIN;
   ```
   - Adds important security headers to prevent common attacks
   - Prevents content type sniffing, XSS attacks, and clickjacking

6. **Single-Page Application Handling**:
   ```nginx
   # Handle frontend routes with HTML5 history API
   location / {
       try_files $uri $uri/ /index.html;

       # Handle JS and CSS files with content hashes first
       location ~* "-[a-zA-Z0-9]{8}\.(js|css)$" {
           expires 1y;
           add_header Cache-Control "public, immutable";
       }

       # Cache strategy for other asset files
       location /assets/ {
           expires 30d;
           add_header Cache-Control "public, no-transform";
       }

       # Don't cache HTML
       location ~* \.html$ {
           expires -1;
           add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";
       }
   }
   ```
   - Configures paths to support HTML5 history API routing
   - Sets up aggressive caching for static assets with content hashes
   - Prevents caching of HTML files that may change

7. **API Proxy Configuration**:
   ```nginx
   # API proxy
   location /api {
       proxy_pass ${BACKEND_URL};
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection 'upgrade';
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       proxy_buffering off;
       proxy_cache off;
       proxy_read_timeout 300s;

       # Add error intercept for better debugging
       proxy_intercept_errors on;
       error_page 502 504 = @api_down;
   }

   # API down fallback
   location @api_down {
       default_type application/json;
       return 503 '{"error": "API service unavailable", "status": 503}';
   }
   ```
   - Forwards API requests to the backend service
   - Sets up necessary headers for proper proxy operation
   - Includes WebSocket support via the Upgrade header
   - Provides a custom error handler for API failures

8. **Health Check Endpoints**:
   ```nginx
   # Health check endpoints
   # Frontend-only health check for container health monitoring
   location = /nginx_health {
       access_log off;
       add_header Content-Type application/json;
       return 200 '{"status":"ok","service":"nginx"}';
   }

   # Health check endpoints for the backend service
   location /health_check {
       proxy_pass ${BACKEND_URL};
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   }
   ```
   - Provides a simple health check endpoint for container monitoring
   - Proxies backend health check endpoints
   - Disables logging for health check requests to reduce log volume

9. **Security Restrictions**:
   ```nginx
   # Deny access to hidden files
   location ~ /\. {
       deny all;
       access_log off;
       log_not_found off;
   }

   location ~ ~$ {
       deny all;
       access_log off;
       log_not_found off;
   }
   ```
   - Blocks access to hidden files and directories
   - Prevents access to backup files (ending with ~)
   - Disables logging for these blocked requests

### 3. `start-nginx.sh`

This is the entrypoint script that configures and starts NGINX when the container is launched.

#### Key Features:

- **Dynamic configuration** - Generates NGINX configuration based on environment variables
- **Flexible logging** - Configures logging format (JSON or standard) based on settings
- **Validation** - Validates the generated configuration before starting NGINX
- **Graceful shutdown** - Sets up signal handlers for proper container shutdown
- **Debug mode** - Optional debug output for troubleshooting
- **Filtering** - Option to filter out health check probe logs

#### Detailed Script Explanation

The startup script handles several important tasks:

1. **Initialization and Settings**:
   ```bash
   #!/bin/sh
   set -e

   # Logging function
   log() {
       timestamp=$(date '+%Y-%m-%d %H:%M:%S')
       echo "[$timestamp] $1"
   }

   log "Initializing NGINX configuration"

   # Define writable directory for the final config
   CONFIG_DIR="$(mktemp -d /tmp/nginx.XXXXXX)"
   log "Created temporary configuration directory: $CONFIG_DIR"
   ```
   - Uses `set -e` to exit on any error
   - Sets up logging with timestamps
   - Creates a temporary directory for configuration files

2. **Logging Configuration**:
   ```bash
   # Define default log formats
   JSON_LOG_FORMAT="log_format json_logs escape=json '{\"time_local\":\"\\$time_local\",\"remote_addr\":\"\\$remote_addr\",...}';"
   DEFAULT_LOG_FORMAT="log_format main '\\$remote_addr - \\$remote_user [\\$time_local] \"\\$request\" \\$status \\$body_bytes_sent \"\\$http_referer\" \"\\$http_user_agent\"';"

   # Write probe filter if enabled
   PROBE_FILTER=""
   if [ "${SUPPRESS_PROBE_LOGS:-true}" = "true" ]; then
     log "Configuring probe filter to suppress health check logs"
     cat > /tmp/probe_filter.conf << 'ENDFILTER'
   map $http_user_agent $loggable {
       default                     1;
       ~*kube-probe                0;
   }
   ENDFILTER
     PROBE_FILTER="$(cat /tmp/probe_filter.conf)"
     LOGGABLE_CONFIG="if=\\$loggable"
   else
     log "Probe filtering disabled, all requests will be logged"
     LOGGABLE_CONFIG=""
   fi
   ```
   - Defines standard and JSON log formats
   - Optionally sets up filtering to reduce noise from health check probes
   - Uses heredoc to create a filter configuration

3. **Log Format Selection**:
   ```bash
   # Determine log format based on environment variable
   if [ -n "$NGINX_CUSTOM_LOG_FORMAT" ]; then
       log "Using custom log format"
       LOG_FORMAT_CONF="log_format custom_logs $(printf '%s' "$NGINX_CUSTOM_LOG_FORMAT");"
       ACCESS_LOG_FORMAT="access_log /var/log/nginx/access.log custom_logs $LOGGABLE_CONFIG;"
   elif [ "${NGINX_LOG_FORMAT:-default}" = "json" ]; then
       log "Using JSON log format"
       LOG_FORMAT_CONF="$JSON_LOG_FORMAT"
       ACCESS_LOG_FORMAT="access_log /var/log/nginx/access.log json_logs $LOGGABLE_CONFIG;"
   else
       log "Using default log format"
       LOG_FORMAT_CONF="$DEFAULT_LOG_FORMAT"
       ACCESS_LOG_FORMAT="access_log /var/log/nginx/access.log main $LOGGABLE_CONFIG;"
   fi
   ```
   - Selects log format based on environment variables
   - Supports custom formats, JSON, and standard formats
   - Applies probe filtering to the selected format

4. **Backend URL Validation**:
   ```bash
   # Check and set environment variables
   if [ -z "$BACKEND_URL" ]; then
     if [ -n "$1" ] && echo "$1" | grep -Eq "^https?://[a-zA-Z0-9.-]+(:[0-9]+)?(/.*)?$"; then
       BACKEND_URL="$1"
       log "Using BACKEND_URL from command line argument: $BACKEND_URL"
     else
       log "ERROR: Invalid BACKEND_URL format: $1"
       exit 1
     fi
   fi

   # Set defaults for configurable values
   FRONTEND_PORT="${FRONTEND_PORT:-${2:-8080}}"
   CLIENT_MAX_BODY_SIZE="${CLIENT_MAX_BODY_SIZE:-10m}"
   GZIP_COMPRESSION_LEVEL="${GZIP_COMPRESSION_LEVEL:-5}"
   CLIENT_TIMEOUT="${CLIENT_TIMEOUT:-12}"
   WORKER_CONNECTIONS="${WORKER_CONNECTIONS:-1024}"

   if [ -z "$BACKEND_URL" ]; then
     log "ERROR: BACKEND_URL must be set as an environment variable or as first parameter. (e.g. http://localhost:7860)"
     exit 1
   fi
   ```
   - Validates the backend URL format
   - Sets default values for configuration variables
   - Shows a clear error message if backend URL is missing

5. **Configuration Generation**:
   ```bash
   # Export variables for envsubst
   export BACKEND_URL FRONTEND_PORT ERROR_LOG_LEVEL CLIENT_MAX_BODY_SIZE GZIP_COMPRESSION_LEVEL CLIENT_TIMEOUT WORKER_CONNECTIONS

   # Use envsubst to substitute environment variables in the template
   log "Generating NGINX configuration from template"
   envsubst '${BACKEND_URL} ${FRONTEND_PORT} ${ERROR_LOG_LEVEL} ${CLIENT_MAX_BODY_SIZE} ${GZIP_COMPRESSION_LEVEL} ${CLIENT_TIMEOUT} ${WORKER_CONNECTIONS}' < /etc/nginx/conf.d/default.conf.template > "$CONFIG_DIR/default.conf"
   ```
   - Exports variables for environment substitution
   - Uses `envsubst` to generate the final configuration
   - Creates the configuration in a temporary directory

6. **Debug Mode**:
   ```bash
   if [ "$DEBUG" = "true" ]; then
     log "DEBUG mode enabled, dumping configuration files"
     log "--- NGINX Configuration ---"
     cat "$CONFIG_DIR/default.conf"
     log "--- Logging Configuration ---"
     cat /nginx-access-log/logging.conf
     log "--- Environment Variables ---"
     env | grep -E 'NGINX|FRONTEND|BACKEND|CLIENT|WORKER|GZIP|ERROR'
   fi
   ```
   - Provides detailed information when debug mode is enabled
   - Shows configuration files and environment variables

7. **Validation and Startup**:
   ```bash
   # Validate the configuration
   log "Validating NGINX configuration"
   nginx -t -c $CONFIG_DIR/default.conf || { echo "Invalid NGINX configuration"; exit 1; }

   # Basic signal handling for graceful shutdown
   trap "echo 'Shutting down NGINX gracefully...'; nginx -s quit; exit 0" TERM INT

   # Start nginx with the new configuration
   log "Starting NGINX on port ${FRONTEND_PORT}, proxying to ${BACKEND_URL}"
   exec nginx -c $CONFIG_DIR/default.conf -g 'daemon off;'
   ```
   - Validates the configuration before starting
   - Sets up signal handlers for graceful shutdown
   - Starts NGINX in foreground mode with the generated configuration

## Environment Variables

The frontend container can be configured using the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | (required) | URL of the backend API (e.g., `http://backend:7860`) |
| `FRONTEND_PORT` | `8080` | Port on which NGINX will listen |
| `DEBUG` | `false` | Enable debug mode for additional logging |
| `NGINX_LOG_FORMAT` | `default` | Log format (`default` or `json`) |
| `NGINX_CUSTOM_LOG_FORMAT` | - | Custom log format definition |
| `ERROR_LOG_LEVEL` | `warn` | NGINX error log level |
| `CLIENT_MAX_BODY_SIZE` | `10m` | Maximum client request body size |
| `GZIP_COMPRESSION_LEVEL` | `5` | GZIP compression level (1-9) |
| `CLIENT_TIMEOUT` | `12` | Client timeout in seconds |
| `WORKER_CONNECTIONS` | `1024` | Maximum number of worker connections |
| `SUPPRESS_PROBE_LOGS` | `true` | Whether to suppress health check probe logs |

## Building the Image

### Using Makefile Commands

Langflow provides several convenient Makefile commands for building the frontend image:

#### 1. Standard Build

```bash
# Build frontend Docker image (depends on base image first)
make dockerfile_build_fe
```

#### 2. Multi-architecture Build (ARM64/AMD64)

```bash
# Build for multiple architectures
make docker_build_frontend_multiarch

# Build specifically for ARM64 and load locally
make docker_build_frontend_arm
```

The commands above will build the image with the tag `langflow_frontend:{VERSION}` where `{VERSION}` is extracted from the project's pyproject.toml file.

## Volume Mounts

The container defines the following volumes:

- `/tmp` - For temporary files
- `/nginx-access-log` - For NGINX access logs

## Security Considerations

- The image runs as a non-root user (UID 10000, GID 10000)
- Security headers are configured in NGINX
- Access to sensitive files and directories is restricted
- The container does not require privileged access

## Performance Optimizations

- Caching headers for static assets
- GZIP compression for appropriate file types
- Tuned NGINX parameters for performance
- Optimized file serving for single-page applications
