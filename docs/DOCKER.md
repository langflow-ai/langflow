# AI Studio Docker Setup Guide

This document provides comprehensive instructions for building, running, and developing AI Studio using Docker containers.

## 📁 Docker Structure

```
ai-studio/
├── docker/
│   ├── backend/
│   │   └── Dockerfile              # Backend container definition
│   └── frontend/
│       └── Dockerfile              # Frontend container definition
├── docker-compose.yml              # Production-like local environment
├── docker-compose.dev.yml          # Development environment overrides
└── docs/
    └── DOCKER.md                   # This documentation
```

## 🚀 Quick Start

### 1. Production-like Local Environment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### 2. Development Environment

```bash
# Start development environment with hot reloading
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Watch development logs
docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f backend frontend
```

## 🐳 Individual Container Builds

### Backend Container

```bash
# Build backend container
docker build -f docker/backend/Dockerfile -t ai-studio-backend:latest .

# Run backend container
docker run -p 7860:7860 \
  -e LANGFLOW_DATABASE_URL=sqlite:///app/data/langflow.db \
  -v $(pwd)/data:/app/data \
  ai-studio-backend:latest
```

### Frontend Container

```bash
# Build frontend container
docker build -f docker/frontend/Dockerfile -t ai-studio-frontend:latest . \
  --build-arg BACKEND_URL=http://localhost:7860

# Run frontend container
docker run -p 3000:3000 \
  -e BACKEND_URL=http://localhost:7860 \
  ai-studio-frontend:latest
```

## 🔧 Container Features

### Backend Container (`docker/backend/Dockerfile`)

**Key Features:**
- **Multi-stage build**: Separate builder and production stages for optimization
- **Security**: Non-root user (`aistudio`), minimal runtime dependencies
- **Python 3.12**: Latest stable Python with uv package manager
- **Health checks**: Built-in health monitoring
- **Volume support**: Persistent data and logs

**Build Arguments:**
- `BUILD_VERSION`: Version tag for the build
- `PYTHON_VERSION`: Python version (default: 3.12)

**Environment Variables:**
- `LANGFLOW_DATABASE_URL`: Database connection string
- `LANGFLOW_CACHE_TYPE`: Cache backend (memory, redis)
- `LANGFLOW_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 7860)

### Frontend Container (`docker/frontend/Dockerfile`)

**Key Features:**
- **Multi-stage build**: Build stage with Node.js + production stage with nginx
- **Security**: Non-root user, minimal attack surface
- **Performance**: Optimized nginx configuration for SPA
- **Build optimization**: Layer caching for faster rebuilds

**Build Arguments:**
- `BACKEND_URL`: API endpoint for backend communication
- `BUILD_VERSION`: Version tag for the build
- `NODE_ENV`: Node environment (default: production)

**Environment Variables:**
- `VITE_BACKEND_URL`: Backend API URL for frontend
- `VITE_BUILD_VERSION`: Build version for frontend display

## 🔄 Development Workflow

### Hot Reloading Setup

The development environment provides hot reloading for both frontend and backend:

**Backend Hot Reloading:**
- Source code mounted as read-only volume
- uvicorn with `--reload` flag
- Automatic restart on Python file changes

**Frontend Hot Reloading:**
- Vite development server with HMR (Hot Module Replacement)
- Source code mounted for live updates
- Automatic browser refresh on file changes

### Development Services

When using `docker-compose.dev.yml`, additional services are available:

- **pgAdmin**: Database management at http://localhost:5050
  - Email: `dev@ai-studio.local`
  - Password: `dev_password`

- **Redis Commander**: Cache management at http://localhost:8081

### Development Commands

```bash
# Install new backend dependencies
docker-compose exec backend uv add package-name

# Install new frontend dependencies
docker-compose exec frontend npm install package-name

# Run backend tests
docker-compose exec backend python -m pytest src/backend/tests/

# Run frontend tests
docker-compose exec frontend npm test

# Access backend shell
docker-compose exec backend bash

# Access frontend shell
docker-compose exec frontend sh

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## 📊 Service Health Monitoring

All services include health checks:

```bash
# Check service health
docker-compose ps

# Detailed health information
docker inspect ai-studio-backend --format='{{.State.Health}}'
docker inspect ai-studio-frontend --format='{{.State.Health}}'
```

**Health Check Endpoints:**
- Backend: `http://localhost:7860/api/v1/health`
- Frontend: `http://localhost:3000`
- Database: PostgreSQL connection check
- Cache: Redis ping command

## 🗄️ Data Persistence

### Volumes

**Production Volumes:**
- `postgres_data`: PostgreSQL database files
- `redis_data`: Redis cache data

**Development Volumes:**
- `ai_studio_dev_data`: Backend application data
- `ai_studio_dev_db`: Development database
- `frontend_node_modules`: Frontend dependencies cache

### Backup and Restore

```bash
# Backup database
docker-compose exec database pg_dump -U aistudio ai_studio > backup.sql

# Restore database
docker-compose exec -T database psql -U aistudio ai_studio < backup.sql

# Backup volumes
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .
```

## 🚨 Troubleshooting

### Common Issues

**1. Port Conflicts**
```bash
# Check port usage
netstat -tulpn | grep :7860
netstat -tulpn | grep :3000

# Use different ports
docker-compose up --scale backend=0
docker run -p 7861:7860 ai-studio-backend:latest
```

**2. Permission Issues**
```bash
# Fix volume permissions
sudo chown -R 1001:1001 ./data
sudo chown -R 1001:1001 ./logs
```

**3. Build Issues**
```bash
# Clean build
docker-compose down -v
docker system prune -a -f
docker-compose build --no-cache

# Check build logs
docker-compose build backend 2>&1 | tee build.log
```

**4. Memory Issues**
```bash
# Increase Docker memory limit
# Docker Desktop: Settings > Resources > Memory > 8GB+

# Check container memory usage
docker stats ai-studio-backend ai-studio-frontend
```

### Debugging

**Backend Debugging:**
```bash
# Enable debug mode
export LANGFLOW_LOG_LEVEL=DEBUG
docker-compose up backend

# Access Python debugger
docker-compose exec backend python -c "import pdb; pdb.set_trace()"
```

**Frontend Debugging:**
```bash
# Enable debug mode
export NODE_ENV=development
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up frontend

# Access browser dev tools at http://localhost:3000
```

## 🔒 Security Considerations

### Production Security

1. **Change default passwords** in production environments
2. **Use secrets management** for sensitive environment variables
3. **Enable SSL/TLS** for external-facing services
4. **Regular security updates** of base images
5. **Scan images** for vulnerabilities using tools like Trivy

### Security Scanning

```bash
# Install Trivy
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Scan backend image
trivy image ai-studio-backend:latest

# Scan frontend image
trivy image ai-studio-frontend:latest

# Scan for secrets
trivy fs --security-checks secret .
```

## 📈 Performance Optimization

### Build Optimization

1. **Use .dockerignore** to exclude unnecessary files
2. **Layer caching**: Order Dockerfile instructions for maximum cache efficiency
3. **Multi-stage builds**: Separate build and runtime dependencies
4. **Minimize image size**: Use alpine bases where possible

### Runtime Optimization

1. **Resource limits**: Set appropriate CPU and memory limits
2. **Health checks**: Configure reasonable intervals
3. **Logging**: Use structured logging with appropriate levels
4. **Monitoring**: Implement metrics collection

```yaml
# Example resource limits in docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

## 🔗 Integration with Azure DevOps

The Docker containers are designed to work seamlessly with the Azure DevOps pipelines:

- **Backend Pipeline**: Builds and pushes `ai-studio-backend` image
- **Frontend Pipeline**: Builds and pushes `ai-studio-frontend` image
- **Registry**: Images pushed to Azure Container Registry (ACR)
- **Deployment**: Automated deployment to Azure Container Instances (ACI)

See [PIPELINES.md](./PIPELINES.md) for detailed pipeline documentation.

## 📞 Support

For Docker-related issues:

1. Check the [troubleshooting section](#troubleshooting) above
2. Review container logs: `docker-compose logs`
3. Check resource usage: `docker stats`
4. Consult the [Azure DevOps pipeline logs](./PIPELINES.md#troubleshooting) for CI/CD issues

---

*Last Updated: October 2024*
*Docker Version: 24.x+*
*Docker Compose Version: 3.8+*