# AI Studio Development Guide

This document provides development setup, Docker configuration, and CI/CD pipeline information for the AI Studio monorepo.

## 🏗️ Monorepo Structure

```
ai-studio/
├── src/
│   ├── backend/                    # Python backend with Langflow
│   └── frontend/                   # React/TypeScript frontend
├── docker/
│   ├── backend/Dockerfile          # Backend container definition
│   └── frontend/Dockerfile         # Frontend container definition
├── azure-pipelines-backend.yml     # Backend CI/CD pipeline
├── azure-pipelines-frontend.yml    # Frontend CI/CD pipeline
├── docker-compose.yml              # Production-like local environment
├── docker-compose.dev.yml          # Development environment
└── docs/                           # Documentation
    ├── DOCKER.md                   # Docker setup guide
    ├── PIPELINES.md                # CI/CD pipeline guide
    └── DEVELOPMENT.md              # This guide
```

## 🚀 Quick Start

### Prerequisites

- **Docker**: Version 24.x+ and Docker Compose
- **Node.js**: Version 20.x+ (for local frontend development)
- **Python**: Version 3.12+ (for local backend development)
- **Git**: For version control

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/autonomizeai/ai-studio.git
cd ai-studio

# Create environment file
cp .env.example .env
# Edit .env with your local configuration
```

### 2. Development Environment

```bash
# Start full development environment
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Verify services are running
docker-compose ps

# View logs
docker-compose logs -f backend frontend
```

**Available Services:**
- 🔧 **Backend API**: http://localhost:7860
- 🎨 **Frontend UI**: http://localhost:3000
- 🗄️ **pgAdmin**: http://localhost:5050 (dev@ai-studio.local / dev_password)
- 📊 **Redis Commander**: http://localhost:8081

### 3. Production-like Environment

```bash
# Start production-like environment
docker-compose up -d

# Access services
# Backend: http://localhost:7860
# Frontend: http://localhost:3000
```

## 🔧 Development Workflow

### Backend Development

**Local Development (without Docker):**
```bash
cd src/backend

# Install dependencies with uv
uv sync

# Activate virtual environment
source .venv/bin/activate

# Run development server
uvicorn langflow.main:create_app --factory --host 0.0.0.0 --port 7860 --reload
```

**Docker Development:**
```bash
# Backend with hot reloading
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up backend

# Run tests
docker-compose exec backend python -m pytest src/backend/tests/

# Run Genesis tests specifically
docker-compose exec backend python -m pytest src/backend/tests/unit/custom/genesis/ -v

# Access backend shell
docker-compose exec backend bash
```

### Frontend Development

**Local Development (without Docker):**
```bash
cd src/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

**Docker Development:**
```bash
# Frontend with hot reloading
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up frontend

# Run tests
docker-compose exec frontend npm test

# Run linting
docker-compose exec frontend npm run lint

# Access frontend shell
docker-compose exec frontend sh
```

### Database Operations

```bash
# Access database
docker-compose exec database psql -U aistudio -d ai_studio

# Run migrations (if applicable)
docker-compose exec backend alembic upgrade head

# Create database backup
docker-compose exec database pg_dump -U aistudio ai_studio > backup.sql
```

## 🧪 Testing

### Backend Tests

```bash
# Run all backend tests
docker-compose exec backend python -m pytest src/backend/tests/ -v

# Run specific test module
docker-compose exec backend python -m pytest src/backend/tests/unit/custom/genesis/ -v

# Run with coverage
docker-compose exec backend python -m pytest --cov=src/backend --cov-report=html
```

### Frontend Tests

```bash
# Run unit tests
docker-compose exec frontend npm run test:unit

# Run E2E tests with Playwright
docker-compose exec frontend npm run test:e2e

# Run type checking
docker-compose exec frontend npm run type-check

# Run linting
docker-compose exec frontend npm run lint
```

### Integration Tests

```bash
# Run full integration test suite
docker-compose exec backend python -m pytest tests/integration/ -v

# Test API endpoints
curl http://localhost:7860/api/v1/health
curl http://localhost:7860/api/v1/all
```

## 🏗️ Build and Deployment

### Local Builds

```bash
# Build backend image
docker build -f docker/backend/Dockerfile -t ai-studio-backend:local .

# Build frontend image
docker build -f docker/frontend/Dockerfile -t ai-studio-frontend:local .

# Build both with docker-compose
docker-compose build
```

### CI/CD Pipelines

The project uses Azure DevOps with dual pipelines:

**Backend Pipeline** (`azure-pipelines-backend.yml`):
- Triggers on: `src/backend/**`, `pyproject.toml`, `uv.lock`
- Stages: Test → Build → Security Scan → Deploy
- Duration: ~15 minutes

**Frontend Pipeline** (`azure-pipelines-frontend.yml`):
- Triggers on: `src/frontend/**`, frontend configs
- Stages: Test → Build → E2E Tests → Security Scan → Deploy
- Duration: ~20 minutes

See [PIPELINES.md](./PIPELINES.md) for detailed pipeline documentation.

## 🔒 Security

### Local Security Scanning

```bash
# Scan for vulnerabilities with Trivy
trivy image ai-studio-backend:local
trivy image ai-studio-frontend:local

# Scan source code for secrets
trivy fs --security-checks secret .

# Run backend security audit
docker-compose exec backend pip-audit

# Run frontend security audit
docker-compose exec frontend npm audit
```

### Security Best Practices

1. **Environment Variables**: Use `.env` files, never commit secrets
2. **Container Security**: Run as non-root users, minimal base images
3. **Dependencies**: Regular updates, vulnerability scanning
4. **Network Security**: Proper network isolation in Docker Compose

## 🐛 Troubleshooting

### Common Issues

**1. Port Conflicts**
```bash
# Check what's using the port
lsof -i :7860
lsof -i :3000

# Use different ports
docker-compose up --scale backend=0
docker run -p 7861:7860 ai-studio-backend:local
```

**2. Permission Issues**
```bash
# Fix volume permissions
sudo chown -R $USER:$USER ./data
sudo chown -R $USER:$USER ./logs

# Reset Docker permissions
docker-compose down -v
docker system prune -a
```

**3. Build Issues**
```bash
# Clean Docker cache
docker system prune -a -f
docker builder prune -a -f

# Rebuild from scratch
docker-compose build --no-cache
```

**4. Database Connection Issues**
```bash
# Reset database
docker-compose down -v
docker-compose up database -d
# Wait for database to be ready, then start other services
```

### Debug Mode

**Backend Debug Mode:**
```bash
# Enable debug logging
export LANGFLOW_LOG_LEVEL=DEBUG
docker-compose up backend

# Python debugger
docker-compose exec backend python -c "import pdb; pdb.set_trace()"
```

**Frontend Debug Mode:**
```bash
# Enable React dev tools
export NODE_ENV=development
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up frontend
```

## 📊 Monitoring and Observability

### Health Checks

```bash
# Check service health
curl http://localhost:7860/api/v1/health
curl http://localhost:3000

# Docker health status
docker-compose ps
docker inspect ai-studio-backend --format='{{.State.Health}}'
```

### Logs

```bash
# View real-time logs
docker-compose logs -f

# View specific service logs
docker-compose logs backend
docker-compose logs frontend

# Export logs for analysis
docker-compose logs > ai-studio.log
```

### Performance Monitoring

```bash
# Monitor resource usage
docker stats

# Check container resource limits
docker inspect ai-studio-backend | grep -i memory
docker inspect ai-studio-backend | grep -i cpu
```

## 🔄 Contribution Guidelines

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "feat: add new feature"

# Push and create PR
git push origin feature/your-feature-name
```

### Code Quality

**Pre-commit Hooks:**
```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

**Backend Code Quality:**
```bash
# Format with ruff
uv run ruff format src/backend/

# Lint with ruff
uv run ruff check src/backend/

# Type checking with mypy
uv run mypy src/backend/
```

**Frontend Code Quality:**
```bash
# Format with Prettier
npm run format

# Lint with ESLint
npm run lint

# Type checking
npm run type-check
```

### Testing Requirements

- ✅ All new features must include tests
- ✅ Maintain >80% test coverage
- ✅ Integration tests for API changes
- ✅ E2E tests for UI changes

### Documentation

- 📝 Update relevant documentation for changes
- 📝 Include inline code comments for complex logic
- 📝 Update API documentation for endpoint changes
- 📝 Add changelog entries for user-facing changes

## 🎯 Helm Chart and Azure DevOps Integration

### Unified Helm Chart Deployment

The project now includes a unified Helm chart for streamlined Kubernetes deployments:

```bash
# Deploy AI Studio with Helm
helm install ai-studio helmcharts/ai-studio/ -n ai-studio --create-namespace

# Deploy with custom values
helm install ai-studio helmcharts/ai-studio/ -f custom-values.yaml

# Update deployment
helm upgrade ai-studio helmcharts/ai-studio/ --set frontend.image.tag=latest
```

### Reorganized Azure DevOps Structure

Azure DevOps pipelines have been reorganized for better maintainability:

```
azure-devops/
├── pipelines/
│   ├── azure-pipelines-backend.yml
│   └── azure-pipelines-frontend.yml
├── templates/
│   ├── docker-build-template.yml
│   └── helm-deploy-template.yml
└── variables/
    └── common.yml
```

For detailed information, see:
- [Helm Chart Guide](./HELM.md) - Complete Helm chart documentation
- [Azure DevOps Guide](./AZURE_DEVOPS.md) - Pipeline organization and deployment

## 📞 Getting Help

### Internal Resources

- **Slack**: #ai-studio-dev for development questions
- **Confluence**: AI Studio Development Wiki
- **Azure DevOps**: Pipeline status and work items

### External Resources

- **Docker Documentation**: https://docs.docker.com/
- **Langflow Documentation**: https://docs.langflow.org/
- **Azure DevOps**: https://docs.microsoft.com/en-us/azure/devops/

### Team Contacts

- **Backend Team**: backend-team@autonomize.ai
- **Frontend Team**: frontend-team@autonomize.ai
- **DevOps Team**: devops-team@autonomize.ai
- **Architecture Team**: architecture-team@autonomize.ai

---

*Last Updated: October 2024*
*Maintained by: AI Studio Development Team*